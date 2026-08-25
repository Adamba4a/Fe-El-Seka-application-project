# Quickstart: Validating Driver Fare Override

Prerequisites: local dev stack running via `docker compose up --build` (per project convention — do not
run `pnpm dev` / `uvicorn` ad hoc against this feature's endpoints, they need the full stack including
Supabase), with a verified driver account, an active vehicle, and a funded wallet (commission reservation
at creation requires available wallet balance — see `commission_service.check_available_balance`).

All scenarios below map directly to spec.md's acceptance scenarios; run them after implementation to
confirm the feature works end-to-end.

## 1. Create a ride at the fair price (User Story 1, scenario 3)

```
POST /api/v1/rides
{ origin, destination, departure_datetime, total_seats: 2 }   # no final_price_per_seat
```
**Expect**: 201, `ride.price_per_seat == ride.fair_price_per_seat`.

## 2. Create a ride with a valid markup (User Story 1, scenarios 1–2)

```
POST /api/v1/rides
{ ..., final_price_per_seat: <fair_price * 1.2, rounded> }
```
**Expect**: 201, `ride.price_per_seat` equals the submitted value, `ride.fair_price_per_seat` equals the
system-computed baseline, and `ride.price_per_seat <= round(ride.fair_price_per_seat * 1.30)`.

## 3. Reject below-fair and above-max prices (User Story 2, scenarios 1–2)

```
POST /api/v1/rides  { ..., final_price_per_seat: <fair_price - 5> }
POST /api/v1/rides  { ..., final_price_per_seat: <max_price + 5> }
```
**Expect**: both return 400 with `error: "price_out_of_band"` and a message stating the valid range;
neither ride is created.

## 4. Boundary values are inclusive (User Story 2, scenario 3)

```
POST /api/v1/rides  { ..., final_price_per_seat: <exactly fair_price> }
POST /api/v1/rides  { ..., final_price_per_seat: <exactly max_price> }
```
**Expect**: both succeed (201).

## 5. Edit price on a published ride, in-band (User Story 3, scenario 1)

```
PATCH /api/v1/rides/{id}  { final_price_per_seat: <new value within current band> }
```
**Expect**: 200, `price_per_seat` updated, visible to passengers viewing/booking the ride afterward
(confirm via `GET /api/v1/rides/{ride_id}` from the passenger-facing ride-detail path).

## 6. Edit seat count, old price still fits new band

```
PATCH /api/v1/rides/{id}  { total_seats: <new count where old price_per_seat still fits new band> }
```
**Expect**: 200, `fair_price_per_seat` and cost-breakdown columns update; `price_per_seat` is unchanged.

## 7. Edit seat count that pushes the old price out of band (User Story 3, scenario 2 / FR-008)

```
PATCH /api/v1/rides/{id}  { total_seats: <new count where old price_per_seat no longer fits> }
   # without final_price_per_seat
```
**Expect**: 400 `price_out_of_band` — edit is rejected, nothing changes. Retry with an in-band
`final_price_per_seat` included → 200, both `fair_price_per_seat` and `price_per_seat` update together.

## 8. Admin sees fair price, final price, and markup (User Story 4)

```
GET /api/admin/rides/{id}
```
**Expect**: response includes `fair_price_per_seat`, `price_per_seat`, `markup_egp`, `markup_percentage`
matching the ride created in scenario 2.

## 9. Commission scales with markup (FR-011 / Research §3)

Complete a ride created with a markup (scenario 2) through to `completed` status with at least one
confirmed booking. Inspect the resulting `COMMISSION_DEBIT` wallet ledger entry.
**Expect**: deducted amount equals `(fuel_cost*0.20 + distance_fee + safety_margin)/total_seats * seats`
**plus** `(price_per_seat - fair_price_per_seat) * 0.20 * seats` — strictly greater than what the same
ride would have deducted at zero markup.

## 10. Passenger-facing surfaces are unaffected (NFR-003 / FR-009)

Search for the ride, view its detail page, and book a seat as a passenger.
**Expect**: passenger sees and is charged `price_per_seat` (the final price) throughout; no fair price,
band, or markup is ever shown on any passenger-facing screen or response.
