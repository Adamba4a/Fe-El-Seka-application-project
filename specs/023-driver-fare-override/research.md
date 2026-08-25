# Phase 0 Research: Driver Fare Override (Capped)

## 1. Max-price computation

**Decision**: Add `MAX_MARKUP_RATE: float = 0.30` and a helper in `pricing_service.py`:

```python
def calculate_max_price(fair_price_per_seat: float) -> float:
    return float(round(fair_price_per_seat * (1 + MAX_MARKUP_RATE)))
```

**Rationale**: `_calc_fee_from_distance` already rounds the fair price with bare `round()` (nearest whole
EGP, banker's rounding). NFR-002 requires the same convention for the max price, so reuse `round()`
rather than `Decimal` quantization — introducing a second rounding rule for one derived number would be
inconsistent and untestable against the existing fair-price behavior.

**Alternatives considered**: Compute the max price with `Decimal`/`ROUND_HALF_UP` (used elsewhere in
`ride_service.py` for money). Rejected — the fair price itself isn't computed that way, and NFR-002
explicitly pins the convention to "the existing fare-price calculation," which is bare `round()`.

## 2. Where the band lives, and validation error shape

**Decision**: `pricing_service.calculate_fare` remains the single source of the fair price. A new field
`max_price_per_seat_egp` is added to `FareEstimateResponse` (computed via `calculate_max_price` from the
existing `per_seat_price_egp`), so both create and edit flows read fair + max from one call. Band
validation (`fair_price <= final_price <= max_price`) is enforced inside `ride_service.create_ride` and
`ride_service.edit_ride`, raising the existing `RideServiceError` pattern with a new code
`price_out_of_band` (400) whose message states the valid range, matching FR-005's "returning an error
that states the valid range."

**Rationale**: `RideServiceError` is already the established validation-error mechanism in this file
(`ride_same_locations`, `ride_departure_past`, `seat_count_invalid`, ...); reusing it keeps the router's
existing `_service_error_response(exc)` handling working unchanged.

**Alternatives considered**: Validating only in the Pydantic request model. Rejected outright by NFR-001
— the band depends on the computed fair price, which isn't known until routing/pricing runs, so it can't
be a static field validator; it must be a service-layer check with access to `calculate_fare`'s result.

## 3. Commission formula — reconciling FR-011 with the existing dual-formula reality

Today there are **two independent commission numbers**, both blind to the driver's price:

- **Reservation at creation** (`ride_service.create_ride`): `max_commission = fuel_cost*0.20 + distance_fee + safety_margin` — a fixed EGP amount, held against the driver's wallet balance regardless of what price they charge.
- **Deduction at completion** (`commission_service.deduct_commission`): `per_seat_commission = (fuel_cost*0.20 + distance_fee + safety_margin) / total_seats`, multiplied by each booking's seat count — again independent of `price_per_seat`.

FR-011 requires commission to scale with the driver's actual final price. The chosen approach extends
both formulas with a **markup commission term**, rather than replacing the existing cost-basis commission
(which funds car-maintenance savings via `distance_fee` — see `car_maintenance_service`, must not be
disturbed):

**Decision**:
```
markup_per_seat = final_price_per_seat - fair_price_per_seat   # >= 0, enforced by the band
markup_commission_per_seat = markup_per_seat * PLATFORM_COMMISSION_RATE   # 0.20

# Reservation at creation (now exact, not a "max" estimate — price is fixed before publish):
total_commission_reserved = (fuel_cost*0.20 + distance_fee + safety_margin) + (markup_per_seat * total_seats * 0.20)

# Deduction at completion, per confirmed booking (seats = booking.seats):
commission_amount = ROUND_HALF_UP(
    (per_seat_commission + markup_commission_per_seat) * seats, 2
)
```

`per_seat_commission` keeps its current meaning (`(fuel_cost*0.20 + distance_fee + safety_margin) /
total_seats`) so the existing car-maintenance accumulation (driven by `distance_fee` alone) is untouched.
`markup_commission_per_seat` is a purely additive term.

**Rationale**: The platform already takes the fuel-cost commission plus 100% of distance fee and safety
margin as revenue on the fair-price baseline. FR-011 says the *existing 20% commission* should also apply
to what the driver charges above that baseline — i.e., the platform doesn't let the driver keep 100% of
the markup either. Applying the same 20% rate to the markup is the minimal, literal reading of FR-011 and
requires no change to the car-maintenance funding mechanism (which is explicitly out of scope here).

Because the final price is chosen and validated at ride *creation* time (not discovered later), the
creation-time reservation can now be **exact** rather than a conservative "max" estimate — there is no
remaining uncertainty to reserve against. The variable/field name `max_commission` in `create_ride` should
be renamed to `total_commission` (or similar) during implementation to reflect this; this is a naming
detail for `/speckit-tasks`, not a behavior change beyond the markup addition itself.

**Alternatives considered**:
- *Apply 20% to the driver's full final-price total instead of only the markup.* Rejected — this would
  double-commission the fair-price baseline (which already funds a 20%-of-fuel-cost commission) and would
  silently change platform revenue on every ride, not just marked-up ones, which is a much bigger change
  than FR-011 asks for.
- *Leave the reservation as a conservative "max" (assume full 30% markup on every ride) instead of the
  driver's actual chosen price.* Rejected — wastes wallet headroom unnecessarily for drivers who don't
  mark up, and the whole point of pricing at creation time is that the final price is already known.

## 4. Edit-time re-banding (FR-008) vs. existing `total_seats` auto-recalculation

`ride_service.edit_ride` currently has a branch (lines ~401–413) that — whenever `total_seats` changes and
`price_source == 'system'` (which is always true, see Clarifications) — silently recalculates the fair
price and **overwrites `price_per_seat` with it**, discarding whatever price was there before. This is the
*only* path that changes `route_distance_km`-derived pricing during an edit, because `destination` edits
are blocked whenever `price_source == 'system'` (i.e., always) — so route distance itself never changes
via edit. This narrows FR-008's "route change recalculation" scenario in practice to **`total_seats`
changes only**.

**Decision**: Replace the silent overwrite with re-validation:
1. On `total_seats` change, recompute `fair_price_per_seat` and the max price exactly as today.
2. Compare the ride's **current final price** (`price_per_seat`) against the **new** band.
3. If it still fits `[new_fair, new_max]`, keep it unchanged (no forced re-entry) — only the persisted
   `fair_price_per_seat` and cost-breakdown columns update.
4. If it falls outside the new band, the edit request MUST also include an explicit
   `final_price_per_seat` that fits the new band, or the whole edit is rejected with `price_out_of_band`
   (same error shape as create). Nothing is silently repriced.

**Rationale**: This is the direct, minimal implementation of FR-008 ("MUST require the driver to set a
new in-band price before the edit can be saved — it MUST NOT silently reprice"). Keeping the price
unchanged when it still fits the new band (rather than always forcing a fresh choice) avoids unnecessary
friction and matches FR-008's wording, which only requires action when the old price is no longer valid.

**Alternatives considered**: Always require the driver to re-confirm final price on any `total_seats`
change, even if the old price still fits. Rejected as unnecessary friction beyond what FR-008 asks for,
and it would regress today's frictionless seat-count edits for drivers who never touched pricing.

## 5. `fair_price_per_seat` persistence — new column vs. derived value

**Decision**: New column `rides.fair_price_per_seat NUMERIC(10,2) NOT NULL`. The existing `price_per_seat`
column keeps its exact current type/semantics and becomes explicitly "the final/effective price" (no
rename — every existing reader of `price_per_seat`, including bookings' price-snapshot logic in
`booking_service.py`, already treats it as the price passengers pay, so no code changes are needed there).

**Rationale**: Matches spec's Key Entities section verbatim ("Ride gains a persisted fair (baseline) price
per seat, distinct from the existing final price per seat"), and SC-002 requires both values to be
"separate, independently retrievable" — a derived-on-read value wouldn't satisfy that for historical rides
whose pricing config may have since changed.

**Backfill for existing rows**: Set `fair_price_per_seat = price_per_seat` for all rows that predate this
migration. Per the spec's Assumptions ("no retroactive repricing of already-published rides") and
Out-of-Scope, existing rides never had a markup, so fair == final is the only correct backfill.

## Summary — all NEEDS CLARIFICATION resolved

No unresolved markers remain in Technical Context or the spec. Proceeding to Phase 1.
