# Research: Loyalty Points

**Feature**: [spec.md](./spec.md) | **Date**: 2026-09-01

## Decision 1: Generalize the car-maintenance ledger into a role-agnostic points system

**Decision**: Replace `driver_wallets.car_maintenance_savings_egp` + `car_maintenance_rewards` with three new tables — `loyalty_points_accounts`, `loyalty_points_transactions`, `loyalty_redemption_requests` — plus a `loyalty_reward_catalog` table. `car_maintenance_service.py` is refactored into `loyalty_service.py`; `commission_service.deduct_commission()`'s call to `car_maintenance_service.accumulate_and_maybe_grant()` becomes a call to `loyalty_service.award_driver_points()`. The admin car-maintenance queue (`car_maintenance_router.py`, `apps/admin/.../car-maintenance/page.tsx`) is generalized into a loyalty admin queue filtered by catalog entry type.

**Rationale**: Spec's Technical Considerations explicitly requires generalizing rather than duplicating (mirrors Constitution Principle VII: "Duplication of shared functionality is prohibited unless explicitly justified"). The existing car-maintenance mechanics (accumulate → threshold → `PENDING`/`FULFILLED` admin queue, `GREATEST(x-y,0)` clawback floor, no-wallet-mutation-on-fulfill because it's a service not a payout) are the exact shape FR-006/FR-009/FR-014 need — the only real change is that redemption becomes a driver-initiated action (Q2) instead of auto-granted on threshold-crossing, which naturally falls out of unifying car-maintenance into the same "spend points on a catalog entry" flow used by vouchers/free-ride/discount.

**Alternatives considered**: Building a parallel `loyalty_*` system alongside the untouched car-maintenance tables (rejected — spec explicitly forbids this, and it would leave driver points split across two ledgers, breaking FR-013's single auditable ledger requirement).

## Decision 2: Existing PENDING car-maintenance rewards migrate; FULFILLED history stays in the old table

**Decision**: The migration converts each driver's `car_maintenance_savings_egp` 1:1 into a `loyalty_points_accounts` (role='driver') balance (per clarify Q1), and moves existing `status='PENDING'` `car_maintenance_rewards` rows into `loyalty_redemption_requests` (as pending car-maintenance redemptions, `points_spent` = the historical `amount_egp`, since those were always exactly `CAR_MAINTENANCE_THRESHOLD_EGP`). Already-`FULFILLED` reward rows are left in place in `car_maintenance_rewards` as an archival financial record and are not migrated into the new ledger — they represent completed service delivery, not live state.

**Rationale**: Constitution's Data Standards require critical operational history to be preserved; dropping/rewriting historical financial audit rows is riskier than leaving a deprecated table alongside the new one. Only live/actionable state (the balance counter and any still-open request) needs to exist in the new system.

**Alternatives considered**: Migrating full history into `loyalty_points_transactions` as backdated entries (rejected — adds complexity for no functional benefit since nothing reads driver points history from before this feature shipped; the spec's SC/NFRs don't require historical backfill).

## Decision 3: Admin-configurable thresholds are stored headlessly in `platform_settings`, but edited through the existing catalog admin screen — not a new standalone settings page

**Decision**: FR-008a's admin-configurable point costs/rates/caps/percentages are stored as `platform_settings` key/value rows (same table used by `group_domain_blocklist`, `wallet_topup_service`'s Vodafone Cash number, etc.), seeded with defaults via migration and read directly by `loyalty_service.py`. Unlike prior `platform_settings` usages, this feature's spec (clarify-session acceptance scenario 1a) explicitly requires an admin-facing edit surface — "Given an admin is on the loyalty program admin screen, When they update a program-wide setting ... Then the new value takes effect immediately." This is satisfied by extending the **system catalog entries' edit form** (already needed for admin catalog CRUD, US4) with the 2 extra fields each system entry needs beyond `point_cost`: the `free_ride` entry's edit form gains `loyalty_free_ride_max_fare_egp`; the `discount` entry's edit form gains `loyalty_discount_percentage`. No separate generic "Settings" page is built.

**Rationale**: `point_cost` for all three system entries (free_ride, discount, car_maintenance) is a `loyalty_reward_catalog` column, already editable via the catalog CRUD screen required by FR-008. The only settings that don't fit the catalog-entry schema are the free-ride fare cap and discount percentage — surfacing those as extra fields on the same system-entry edit form (rather than a second, parallel settings UI) satisfies "on the loyalty program admin screen" literally, reuses one screen instead of two, and keeps the underlying storage on the same headless `platform_settings` pattern used everywhere else in this codebase (only the read/write plumbing is new, not the storage mechanism).

**Alternatives considered**: A fully separate `apps/admin` "Loyalty Settings" page (rejected — spec's acceptance scenario 1a says "the loyalty program admin screen," singular, implying one screen covers both catalog and settings; a second page would be unrequested extra surface area). Pure headless DB-only editing with no UI at all (rejected — this was the original Decision 3, but it directly contradicts acceptance scenario 1a's explicit UI requirement, which was approved by the user during `/speckit-clarify` and takes precedence).

## Decision 4: Redemption points are deducted at submission time for every redemption type; free-ride/discount apply inline at booking, vouchers/car-maintenance go through the existing PENDING/FULFILLED queue only when `fulfillment_mode='manual'`

**Decision**: All four reward types (`free_ride`, `discount`, `car_maintenance`, `voucher`) share one `loyalty_redemption_requests` row shape with a `status` and a `fulfillment_mode` snapshot copied from the catalog entry at redemption time.
- `free_ride` / `discount`: redeemed **inline during booking creation** (a new optional field on the existing booking-creation request identifies the catalog entry to redeem). Points are deducted and the request is created+resolved as `fulfilled` atomically in the same transaction as the booking, since the "fulfillment" *is* the fare adjustment — there's nothing left for an admin to do.
- Standard `voucher` entries default `fulfillment_mode='instant'` (per clarify answer): redeemed via a dedicated endpoint outside ride-booking context, points deducted and status set to `fulfilled` immediately, no admin step.
- `car_maintenance` and any voucher explicitly flagged `fulfillment_mode='manual'`: redemption creates a `pending` row (points already deducted, per FR-011) that surfaces in the admin queue for `fulfill`/`reject`, generalizing `car_maintenance_service.fulfill_reward()`.

**Rationale**: FR-011 requires deduction at submission time regardless of fulfillment path (prevents double-spend under NFR-002). Keeping free-ride/discount inline with booking creation is the only way to enforce FR-005a (mutual exclusivity with sponsored-ride discounts) at the same point the fare is computed — sponsored-ride logic (Spec 026) already lives in the booking-creation path.

**Alternatives considered**: A separate "reserve then apply" two-step redemption for free-ride/discount (rejected — adds a race window and complexity `SELECT...FOR UPDATE` inline already prevents; not needed since booking creation is already a single transaction).

## Decision 5: New passenger-side points account table (no existing table to extend)

**Decision**: `loyalty_points_accounts` is a brand-new table, `UNIQUE(user_id, role)`, so a dual-role user gets two independent rows (FR-003). This is the only option for passengers since no passenger wallet/balance table exists anywhere in the schema (confirmed: only `driver_wallets` and `wallet_topup_requests` exist, both driver-only).

**Rationale**: Directly required by FR-003 (separate balances per role) — a single `user_id`-keyed table couldn't represent a dual-role user's two independent balances.

**Alternatives considered**: Extending `driver_wallets` with a nullable passenger-points column and adding a new `passenger_wallets` table for symmetry (rejected — `driver_wallets` holds EGP cash balance/reservations unrelated to points, and a role-keyed single table is simpler than two near-duplicate tables).

## Decision 6: Driver point-earning rate stays pegged to the existing 0.3 EGP/km distance-fee mechanism, credited 1:1 as points

**Decision**: No new `platform_settings` key for the driver earn rate — `commission_service.py`'s existing per-seat distance-fee computation (unchanged) is what funds driver points, exactly as it funded `car_maintenance_savings_egp` before. Each EGP of distance fee credits 1 point, consistent with the Q1-resolved 1:1 migration conversion.

**Rationale**: Spec's Assumptions state earning is "proportional to fare/distance," and the distance-fee mechanism is the established, already-correct implementation of that for drivers; re-deriving a separate rate would duplicate logic the Constitution says must not be duplicated.

**Alternatives considered**: A configurable `loyalty_driver_earn_points_per_egp_distance_fee` setting (rejected — over-engineering; the distance fee itself is already the tunable lever via `commission_service.py`'s existing 0.3 EGP/km constant, no second knob needed).

## Decision 7: Passenger point-earning rate is a new configurable `platform_settings` key

**Decision**: `loyalty_passenger_earn_points_per_egp_fare` (default `"1"`) — passenger earns `floor(fare_paid_egp * rate)` points per completed booking, awarded in `booking_service.complete_ride_bookings()`.

**Rationale**: Unlike drivers, passengers have no existing EGP-accumulation mechanism to piggyback on, so this rate needs its own admin-tunable setting per FR-008a.

**Alternatives considered**: Flat points-per-completed-ride regardless of fare (rejected — spec's Assumptions specify "proportional to fare/distance," ruling out a flat rate).

## Decision 8: Testing approach

**Decision**: pytest for backend service/integration tests (`services/api/tests/unit/test_loyalty_service.py`, `services/api/tests/integration/test_loyalty_flow.py`), following the direct-service-layer pattern used for Specs 026/027 since this feature has no OSRM dependency and can be validated against the real local Supabase DB. `pnpm turbo typecheck`/`lint`/`build` for frontend changes in `apps/main` and `apps/admin`.

**Rationale**: Matches established project testing conventions (`project_osrm_not_configured_locally` memory — OSRM unavailable locally, but this feature never calls OSRM, so no blocker).

**Alternatives considered**: None — this is the only testing approach used anywhere in this codebase.

## Decision 9: `notification_event_type` and `admin_audit_logs` extensions follow the established incremental pattern

**Decision**: Add new enum values via `ALTER TYPE public.notification_event_type ADD VALUE IF NOT EXISTS '...'` for `loyalty_points_earned`, `loyalty_redemption_fulfilled`, `loyalty_redemption_rejected`, `loyalty_threshold_reached` (FR-015). Add a nullable `admin_audit_logs.redemption_request_id UUID REFERENCES loyalty_redemption_requests(id)` column, reusing the existing `'approved'`/`'rejected'` `action_type` values (no CHECK constraint change needed, mirroring the `withdrawal_request_id` precedent).

**Rationale**: This is the exact "gotcha" pattern already used for every prior admin-action-mirroring feature in this codebase (car-maintenance, top-up, withdrawal, featured-rides) — both extension points are additive and non-breaking.

**Alternatives considered**: None — deviating from this pattern would be inconsistent with every other admin queue in the codebase.
