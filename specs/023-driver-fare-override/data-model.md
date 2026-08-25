# Phase 1 Data Model: Driver Fare Override (Capped)

## Entity: Ride (`rides` table)

Extends the existing `rides` table (already the source of truth for `price_per_seat`, `fuel_cost_egp`,
`platform_commission_egp`, `distance_fee_egp`, `safety_margin_egp`, `price_source`).

| Field | Type | Notes |
|---|---|---|
| `fair_price_per_seat` | `NUMERIC(10,2) NOT NULL` | **New.** System-computed baseline price per seat, from `pricing_service.calculate_fare`. Set once at creation; recomputed only when `total_seats` changes on edit (§Research #4). Never set directly by a driver. |
| `price_per_seat` | `NUMERIC(10,2) NOT NULL` | **Unchanged column, clarified semantics.** This is the driver's final/effective price per seat — what passengers see and pay (existing behavior, FR-009). Defaults to `fair_price_per_seat` when the driver supplies no price (FR-007). Must satisfy `fair_price_per_seat <= price_per_seat <= max_price_per_seat` at all times (SC-003) — `max_price_per_seat` itself is never stored (§Price Band below). |
| `price_source` | `TEXT` (existing) | **Untouched**, per Clarifications — stays `'system'` on every ride, unrelated to this feature. |

**Validation rules** (enforced in `ride_service`, not the DB — matches how `total_seats` / departure-time
bounds are already enforced):
- `fair_price_per_seat >= 0`
- `price_per_seat` in `[fair_price_per_seat, round(fair_price_per_seat * 1.30)]` inclusive, at both
  creation and edit time.
- On edit, if `total_seats` changes and the recomputed `fair_price_per_seat` moves such that the existing
  `price_per_seat` falls outside the new band, the request must supply a new in-band `price_per_seat` or
  the edit is rejected (`price_out_of_band`, FR-008).

**No state machine change**: `fair_price_per_seat` is not part of the `rides.status` lifecycle
(`scheduled` → `in_progress` → `completed`/`cancelled`); it's set once and only ever recomputed by the
`total_seats`-edit path described above, same lifecycle as the existing pricing columns.

## Derived value: Price Band (not persisted)

- **Definition**: `[fair_price_per_seat, max_price_per_seat]` where
  `max_price_per_seat = round(fair_price_per_seat * 1.30)` (bare `round()`, same convention as fair price).
- **Lifetime**: Computed fresh on every create/edit request and every read where it's displayed (driver
  pricing step, admin detail view). Never stored independently — storing it would risk drifting from
  `fair_price_per_seat` if the rounding constant ever changes.
- **Consumers**: `POST /api/v1/rides` (display before submit + validation), `PATCH /api/v1/rides/{id}`
  (same), admin ride detail (`GET /api/admin/rides/{id}`, display only — no edit capability there).

## Derived value: Markup (admin display only, FR-010)

- `markup_egp = price_per_seat - fair_price_per_seat`
- `markup_percentage = round((markup_egp / fair_price_per_seat) * 100)` when `fair_price_per_seat > 0`
  (guards the edge case in spec's Edge Cases: a very small fair price still produces a defined, if narrow,
  percentage — never divide by zero, since `fair_price_per_seat` is always a positive computed fare).
- Not persisted; computed in the admin router response, same pattern as the rest of
  `admin/rides_router.py`'s hand-built response dicts.

## Migration

New file `supabase/migrations/<YYYYMMDDHHMMSS>_add_fair_price_per_seat.sql` (exact timestamp chosen at
implementation time to avoid colliding with migrations already merged to `main` that this branch, per
`git merge-base`, doesn't yet contain locally):

```sql
ALTER TABLE rides
    ADD COLUMN fair_price_per_seat NUMERIC(10,2);

UPDATE rides
    SET fair_price_per_seat = price_per_seat
    WHERE fair_price_per_seat IS NULL;

ALTER TABLE rides
    ALTER COLUMN fair_price_per_seat SET NOT NULL;
```

Three-step (add nullable → backfill → set NOT NULL) so the migration is safe to run against a table with
existing rows, consistent with how `ALTER TABLE` migrations for new NOT NULL columns are already done
elsewhere in `supabase/migrations/` (e.g. the distance-fee-pricing migration pattern).

## No new entities

"Price Band" is explicitly a derived/non-persisted concept per the spec's Key Entities section — it is
not a database table or a new model class beyond the response fields listed in `contracts/`.
