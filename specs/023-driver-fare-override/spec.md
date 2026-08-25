# Feature Specification: Driver Fare Override (Capped)

**Feature Branch**: `023-driver-fare-override`

**Created**: 2026-08-25

**Status**: Draft

**Input**: User description: "Allow drivers to adjust the system-generated fare upward by up to 30% when creating or editing a ride. The system still computes and displays the fair (baseline) price per seat using the existing pricing engine; the driver additionally sees the maximum allowed price (fair price + 30%) and can set any price between the fair price and that max — they cannot go below the fair price or above the max. Both the system-generated fair price and the driver's chosen final price must be persisted (not just the final price), since downstream logic (platform commission, admin auditing, search/matching, price-recommendation model training data) needs the baseline for comparison. This reverses a prior hard rule that drivers cannot override the system fare at all — the new rule is drivers may adjust upward only, within a capped band, with both values visible and stored."

## Business Objective *(mandatory)*

Give drivers limited pricing flexibility — up to 30% above the platform's computed fair price — so they can account for factors the pricing engine doesn't see (comfort, AC, timing convenience), while keeping the platform's fair-price baseline as the anchor for trust, auditing, and future price-recommendation model training.

**Constitutional Domain**: Pricing / Ride Creation (Principle I — Driver-First Route Sharing; Auditability)

**Affected Applications**: Driver App (apps/main), Admin Panel (fare audit visibility)

---

## Clarifications

### Session 2026-08-25

- Q: How should the existing `price_source` column (currently hardcoded to `'system'` on every ride, which also gates the pre-existing destination-edit-lock rule in `ride_service.py`) interact with this feature's new fair-price/final-price fields? → A: Leave `price_source` completely untouched by this feature — it remains `'system'` always; this feature does not read, write, or otherwise interact with it or the destination-edit-lock rule it gates.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Driver sets a price when creating a ride (Priority: P1)

A driver creating a new ride sees the system's fair price per seat and the maximum price they're allowed to charge (fair price + 30%). They choose any price in that range before publishing.

**Why this priority**: This is the core of the feature — without it, nothing changes for the driver.

**Independent Test**: Create a ride as a driver, confirm both the fair price and max price are shown, set a price at the midpoint of the range, publish, and verify the published ride shows that price to passengers.

**Acceptance Scenarios**:

1. **Given** a driver is creating a ride and the system computes a fair price of 50 EGP, **When** the driver reaches the pricing step, **Then** they see "Fair price: 50 EGP" and "Max price: 65 EGP" before choosing a final price.
2. **Given** the driver has seen the fair and max price, **When** they set the price to 60 EGP and publish, **Then** the ride is created with a final price of 60 EGP.
3. **Given** the driver takes no explicit pricing action, **When** they publish the ride, **Then** the final price defaults to the fair price.

---

### User Story 2 - System rejects an out-of-band price (Priority: P1)

A driver attempts to set a price below the fair price or above the maximum, and the system blocks it with a clear explanation of the allowed range.

**Why this priority**: The cap is the entire point of the feature — without enforcement, this is just "drivers can override the fare," which was explicitly rejected as a prior hard rule.

**Independent Test**: Attempt to submit a ride creation/edit request with a price below the fair price and separately above the max; confirm both are rejected server-side with the valid range in the error.

**Acceptance Scenarios**:

1. **Given** a fair price of 50 EGP and max of 65 EGP, **When** a driver (via the app or a direct API call) submits a price of 45 EGP, **Then** the system rejects the request and states the valid range is 50–65 EGP.
2. **Given** the same range, **When** a driver submits a price of 70 EGP, **Then** the system rejects the request and states the valid range is 50–65 EGP.
3. **Given** the same range, **When** a driver submits a price of exactly 50 EGP or exactly 65 EGP, **Then** the request succeeds (boundary values are inclusive).

---

### User Story 3 - Driver adjusts price when editing an existing ride (Priority: P2)

A driver editing a ride they've already published can change the final price, still bounded by the fair/max band computed at edit time.

**Why this priority**: Important for completeness, but rides are edited less often than created, so it's lower priority than the creation flow.

**Independent Test**: Edit a published ride's price to a new value within the current band and confirm it saves; attempt an out-of-band value and confirm it's rejected.

**Acceptance Scenarios**:

1. **Given** a published ride with a fair price of 50 EGP, **When** the driver edits the ride and changes the price to 55 EGP (within band), **Then** the change is saved and reflected to passengers viewing the ride.
2. **Given** an edit that also changes the route (origin/destination/distance), **When** the fair price is recalculated as a result, **Then** the driver sees the updated fair price and max price before confirming the edit.

---

### User Story 4 - Admin sees both fair price and driver's final price (Priority: P3)

An admin reviewing a ride in the admin panel can see the system's fair price alongside the driver's final price, so pricing behavior is auditable.

**Why this priority**: Supports trust/fraud oversight but doesn't block the driver-facing feature from delivering value on its own.

**Independent Test**: As an admin, open a ride detail view and confirm both the fair price and final price (and the markup) are visible.

**Acceptance Scenarios**:

1. **Given** a ride was published with a fair price of 50 EGP and a final price of 60 EGP, **When** an admin views the ride detail page, **Then** both values are shown, along with the 20% markup.

---

### Edge Cases

- What happens when the driver submits a price with fractional EGP (e.g., 55.5)? The system rounds/validates consistent with the existing whole-EGP pricing convention.
- What happens when a route edit lowers the fair price below the driver's previously-set final price, such that the old final price now exceeds the new max? The system MUST re-validate the stored final price against the newly computed band at edit time and require the driver to confirm a new in-band price before saving.
- What happens when the fair price is very small (e.g., 3 EGP), making the 30% markup round to 0 or 1 EGP difference? The max price still applies the same rounding rule as the fair price (nearest whole EGP), even if the resulting band is narrow.
- What happens if a driver calls the ride-creation API directly (bypassing the app UI) with no price field at all? The system defaults the final price to the fair price, matching current no-price-field behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST compute the fair (baseline) price per seat using the existing pricing engine for every ride creation and edit, unchanged from current behavior.
- **FR-002**: System MUST compute a maximum allowed price per seat equal to the fair price plus 30%, rounded to the nearest whole EGP using the same rounding convention as the fair price.
- **FR-003**: The driver-facing ride creation and edit flows MUST display both the fair price and the maximum allowed price before the driver confirms a final price.
- **FR-004**: Drivers MUST be able to set a final price per seat anywhere in the inclusive range [fair price, max price].
- **FR-005**: System MUST reject, server-side, any driver-submitted final price outside [fair price, max price], returning an error that states the valid range. Client-side validation alone is not sufficient.
- **FR-006**: System MUST persist both the fair (baseline) price per seat and the driver's final price per seat as distinct, independently retrievable values for every ride.
- **FR-007**: If a driver does not explicitly set a final price during creation, the system MUST default the final price to the fair price.
- **FR-008**: When a ride edit causes the fair price to be recalculated (e.g., due to a route change) and the ride's existing final price falls outside the newly computed band, the system MUST require the driver to set a new in-band price before the edit can be saved — it MUST NOT silently reprice a ride passengers may have already viewed or booked.
- **FR-009**: Passenger-facing search, ride details, and booking flows MUST display and charge the driver's final price, not the fair price.
- **FR-010**: The admin panel's ride detail view MUST show the fair price, the final price, and the markup percentage for every ride.
- **FR-011**: The platform's existing 20% commission MUST be calculated on the driver's final price (fair price plus any markup), not only on the fair-price cost components — total platform commission revenue scales with what the driver actually charges.

### Key Entities *(include if feature involves data)*

- **Ride**: Gains a persisted fair (baseline) price per seat, distinct from the existing final price per seat that passengers see and pay.
- **Price Band**: A derived, non-persisted range shown at creation/edit time — [fair price, fair price + 30%] — used only for input validation and display, not stored independently of the ride's fair price.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Drivers can view both the fair price and the maximum allowed price at the same step where they currently see the system-generated price, with no added navigation steps.
- **SC-002**: 100% of rides created or edited after this feature ships have both a fair (baseline) price and a final price stored as separate, independently retrievable values.
- **SC-003**: 0% of published rides have a final price outside the [fair price, fair price + 30%] band at any point in time — this is enforced with no exceptions, including via direct API calls.
- **SC-004**: Admins can see a ride's fair price, final price, and markup percentage without consulting any system other than the admin panel.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Price band validation MUST be enforced server-side on every ride create/edit request, independent of and in addition to any client-side UI guardrails.
- **NFR-002**: Max-price computation MUST use the same rounding convention as the existing fair-price calculation (nearest whole EGP), so the displayed band never implies a fractional-EGP price the driver can't actually set.
- **NFR-003**: This feature MUST NOT change how passengers search for or book rides beyond the price they see and pay being the driver's final price — no new passenger-facing steps.

---

## Dependencies *(mandatory)*

- **Internal**: Ride Management domain — ride creation and edit endpoints/services (`services/api/app/api/rides/router.py`, `services/api/app/services/ride_service.py`).
- **Internal**: Pricing engine — `services/api/app/services/pricing_service.py` (`calculate_fare`), which remains the sole source of the fair price.
- **Internal**: Admin Operations domain — ride detail view must be extended to show fair price / markup.
- **Data**: Requires a new persisted column on the ride record for the fair (baseline) price per seat, alongside the existing final price column.

---

## Out-of-Scope

- Changing the underlying fair-price formula itself (the fuel/commission/distance/safety-margin calculation) — that's a separate, already-applied change (fare-split divisor).
- Dynamic or surge pricing beyond the flat +30% cap.
- Passenger-side price negotiation, counter-offers, or bidding.
- Retroactively re-banding or repricing rides published before this feature ships.
- Driver-facing UI treatment (slider vs. numeric input vs. presets) — left to the implementation plan.
- The existing `price_source` column and the destination-edit-lock rule it gates — untouched by this feature (see Clarifications).

---

## Technical Considerations

- `pricing_service.calculate_fare` already returns the fair `per_seat_price_egp`; a new helper deriving `max_price = round(fair_price * 1.30)` should live alongside it so both creation and edit flows use one source of truth.
- `CreateRideRequest` / `EditRideRequest` need an optional final-price field; validation against `[fair_price, max_price]` must happen in `ride_service`, not only in the router or the client, per NFR-001.
- The `rides` table needs a migration adding a `fair_price_per_seat` column (naming TBD in planning) distinct from the existing `price_per_seat` column, which continues to represent the final/effective price.
- The new fair-price column and band validation are independent of the existing `price_source` column — that column stays hardcoded to `'system'` in the ride-creation INSERT exactly as it is today; this feature does not add, change, or branch on any `price_source` value.
- Commission calculation changes from today's `fuel_cost * 20%` (independent of final price) to a formula based on the driver's final price, since FR-011 requires commission to scale with what the driver actually charges — this needs to be worked out precisely in planning (e.g., commission = final_price-equivalent cost basis * 20%, or an added markup-commission term), not just a copy of the existing fair-price commission math.

---

## Assumptions

- Currency remains EGP with whole-number rounding, consistent with current pricing engine behavior.
- The 30% cap applies per seat, matching the platform's existing per-seat pricing model (not a total-ride cap).
- This applies only to rides created or edited after the feature ships — no retroactive repricing of existing published rides.
- This specification intentionally supersedes the prior "drivers cannot override the system fare" rule, per explicit product direction; the new rule is a capped, upward-only override with both values persisted for audit and future price-recommendation model training.
