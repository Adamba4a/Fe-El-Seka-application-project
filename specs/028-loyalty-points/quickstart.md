# Quickstart: Loyalty Points

**Feature**: [spec.md](./spec.md) | **Contracts**: [contracts/loyalty-points-api.md](./contracts/loyalty-points-api.md)

Validates the feature end-to-end via direct-service-layer scripts against the real local Supabase DB (no OSRM dependency — same approach as Specs 026/027).

## Prerequisites

- Local Supabase stack running (`supabase start`), migrations applied including this feature's new migration.
- `services/api` running locally with `.env` pointed at the local Supabase instance.
- Seed data: one `passenger` profile, one `driver` profile (with an existing `driver_wallets` row), one `admin` profile.

## Scenario 1 — Passenger earns points on ride completion (US1, FR-001)

1. Passenger books and completes a ride with a known fare (e.g. 50.00 EGP).
2. Call `booking_service.complete_ride_bookings(conn, ride_id)` (or trigger via the normal ride-completion path).
3. `GET /api/v1/loyalty/balance` as the passenger → expect `balance == floor(50.00 * loyalty_passenger_earn_points_per_egp_fare)`.
4. `GET /api/v1/loyalty/transactions` → one `ride_completed_earn` entry with matching `booking_id`/`ride_id`.

## Scenario 2 — Passenger redeems points for a capped free ride (US1 scenario 2a, FR-004)

1. Set passenger balance ≥ `loyalty_free_ride_point_cost` (via Scenario 1 or direct seed).
2. Create a booking on a ride whose fare exceeds `loyalty_free_ride_max_fare_egp`, with `loyalty_redemption_catalog_entry_id` set to the `free_ride` entry.
3. Expect: booking succeeds, passenger is charged `fare - loyalty_free_ride_max_fare_egp` (not zero), points deducted by `loyalty_free_ride_point_cost`, a `fulfilled` `loyalty_redemption_requests` row exists with `ride_id`/`booking_id` set.

## Scenario 3 — Driver accumulates and manually redeems car-maintenance credit (US2, FR-002/FR-006, Q1/Q2)

1. Complete several rides for the driver so accumulated distance-fee points reach ≥ `loyalty_car_maintenance_point_cost`.
2. `GET /api/v1/loyalty/balance` as the driver → confirm accumulated balance, confirm it was **not** auto-redeemed (balance stays ≥ threshold until the driver acts — Q2).
3. `POST /api/v1/loyalty/catalog/{car_maintenance_entry_id}/redeem` as the driver → expect `status: "pending"`, points deducted immediately.
4. `GET /api/v1/admin/loyalty/queue` as admin → the request appears.
5. `POST /api/v1/admin/loyalty/queue/{id}/fulfill` → status becomes `fulfilled`, `admin_audit_logs` row written with `redemption_request_id` set.

## Scenario 4 — Instant voucher redemption (US3, clarify answer on instant fulfillment)

1. Seed an `active` `voucher` catalog entry with `fulfillment_mode='instant'`, `audience='both'`.
2. As passenger (or driver) with sufficient balance, `POST /api/v1/loyalty/catalog/{id}/redeem` → expect `status: "fulfilled"` in the same response, no admin step, points deducted.

## Scenario 5 — Admin rejects a manual redemption, points refunded (FR-012)

1. Repeat Scenario 3 steps 1-4 to get a `pending` request.
2. `POST /api/v1/admin/loyalty/queue/{id}/reject` with a reason → status becomes `rejected`.
3. `GET /api/v1/loyalty/balance` as the driver → balance increased back by `points_spent`; `GET /api/v1/loyalty/transactions` shows a `redemption_refund` entry.

## Scenario 6 — Concurrent redemption does not double-spend (NFR-002)

1. Set an account's balance to exactly `point_cost` for some catalog entry.
2. Fire two concurrent `POST .../redeem` requests for that entry.
3. Expect exactly one `200` and one `409 insufficient_points` — verified via the `SELECT ... FOR UPDATE` lock on `loyalty_points_accounts` (data-model.md validation rules).

## Scenario 7 — Sponsored booking cancellation reverses driver points, capped at current balance (FR-014)

Note: the only reachable trigger for `loyalty_service.reverse_points()` in this codebase is
`cancel_booking`'s sponsored-settlement-reversal branch (driver points only). A `completed`
booking can never be cancelled/refunded (`cancel_booking` rejects terminal-status bookings with
`409 booking_terminal`), so passenger `ride_completed_earn` points earned at completion have no
reachable reversal path today — reversing them would require a new post-completion
refund/fraud-flow that doesn't exist anywhere else in this codebase and is out of this feature's
scope. FR-014 is satisfied for the one case the app can actually produce.

1. Driver accumulates enough distance-fee points that most of the balance is spent on a
   `car_maintenance` redemption (Scenario 3), leaving a balance below what a single sponsored
   booking's settlement would credit.
2. Confirm a sponsored-group booking (credits driver points at `_settle_sponsored_booking` time),
   then cancel that same booking while it is still `confirmed` (before the ride completes).
3. Expect balance floors at `0` (never negative) via the `min(points, account["balance"])` clamp in
   `reverse_points`; a `ride_reversal_clawback` transaction is recorded for the amount actually
   clawed back (which may be less than the full original credit).

## Scenario 8 — Dual-role user has separate balances (FR-003, edge case)

1. A profile with both a `passenger` and a `driver` role earns points as a passenger (Scenario 1) and separately as a driver (Scenario 3, step 1).
2. `GET /api/v1/loyalty/balance` as passenger vs. as driver → two independent `loyalty_points_accounts` rows, no pooling.

## Verification commands

```powershell
cd services/api
pytest tests/unit/test_loyalty_service.py tests/integration/test_loyalty_flow.py -v

cd apps/main
pnpm turbo typecheck lint build --filter=main

cd apps/admin
pnpm turbo typecheck lint build --filter=admin
```
