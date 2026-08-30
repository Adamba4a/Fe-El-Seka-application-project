# Quickstart: Validating Sponsored Groups

Prerequisites: local Supabase stack running with the `026-sponsored-groups` migrations applied, `services/api` running (`uvicorn`), one admin account, one driver account (Driver A), one domain-verified member account (Member B, verified on `acmecorp.com` per Spec 024's domain-verification flow), and Mailpit running for local email capture.

## 1. Auto-upgrade an existing domain group to sponsored (US1)

1. Confirm a non-sponsored `company` group already exists for `acmecorp.com` (from Spec 024's quickstart or Member B's own domain verification).
2. As admin: `POST /api/admin/sponsored-groups` with `{ domain: "acmecorp.com", funded_balance_egp: "5000.00", requested_group_type: "company" }` → expect `200`, the **same** group row now has `is_sponsored: true`, `funded_balance_egp: "5000.00"` — no second group was created.
3. As admin: repeat the same call → expect `409 already_sponsored`.

**Pass condition**: FR-001/002/003, clarification #1 (auto-upgrade-in-place).

## 2. Sponsored booking settles automatically, no cash option (US2)

1. As Driver A: post a ride with `group_id` set to the sponsored group.
2. As Member B: book a seat on that ride via the existing booking endpoint.
3. Check the booking response / DB row: `payment_source` is `SPONSORED`.
4. Check the group: `funded_balance_egp` decreased by exactly the per-seat price.
5. Check Driver A's wallet ledger: a new `SPONSORED_RIDE_CREDIT` entry exists for the net-of-commission amount, and `balance_egp` increased by that amount immediately (before the ride departs or completes).

**Pass condition**: FR-004/005/006/007/009, clarification #2 (always automatic, no cash alternative), research.md §4.

## 3. Insufficient funded balance rejects the booking (FR-008)

1. As admin: create/upgrade a second sponsored group with `funded_balance_egp: "10.00"` (less than one seat's price).
2. As Driver A: post a ride scoped to that group.
3. As a different domain-verified member: attempt to book a seat → expect `422 insufficient_funded_balance`. Confirm the seat was **not** claimed (`booked_seats` unchanged) and no wallet credit was written.

**Pass condition**: FR-008.

## 4. Ride completion does not double-charge the driver (research.md §5/§6)

1. Using the ride from Scenario 2, confirm the driver's ride-creation did **not** create a `commission_reservations` row and did **not** lock any wallet balance (driver can have `balance_egp: 0.00` at ride-creation time and still post the ride).
2. Drive the ride to `in_progress` then `completed` via the existing driver flow.
3. Check the driver's ledger: **no** new `COMMISSION_DEBIT` entry was created for the sponsored booking (it was already settled in Scenario 2) — a ride with only sponsored bookings produces zero `COMMISSION_DEBIT` entries at completion.
4. If the same ride also had a normal cash booking from a non-member passenger... (N/A for a fully group-scoped ride, since only members can book it — cash bookings only apply to non-group-scoped rides, which are entirely unaffected by this feature).

**Pass condition**: research.md §5/§6 (no double-accounting, no wallet-balance gate on sponsored ride creation).

## 5. Sponsored booking cancellation reverses the credit (FR-010)

1. Repeat Scenario 2 to create a new sponsored booking.
2. As Member B: cancel the booking before departure via the existing cancellation endpoint.
3. Check the group: `funded_balance_egp` is restored by the seat price.
4. Check the driver's ledger: a new `SPONSORED_RIDE_REVERSAL` entry exists, offsetting the earlier `SPONSORED_RIDE_CREDIT`; `balance_egp` decreased by the same net amount (allowed to go negative if already withdrawn, per research.md §11 — not expected in this scenario).

**Pass condition**: FR-010.

## 6. Dashboard contact must already be a member (FR-020, clarification #3)

1. As admin: `POST /api/admin/sponsored-groups/{group_id}/dashboard-contact` with a `user_id` who has **not** joined the group → expect `422 not_a_group_member`.
2. As admin: repeat with Member B (already a member) → expect `200`, `dashboard_contact_user_id` set.
3. As Member B: `GET /api/groups/{group_id}/sponsorship-dashboard` → expect `200` with `funded_balance_egp` and recent `SPONSORED_RIDE_CREDIT`/`SPONSORED_RIDE_REVERSAL` activity.
4. As Driver A (not the dashboard contact): repeat step 3 → expect `403`.

**Pass condition**: FR-020, clarification #3.

## 7. One pending withdrawal at a time (FR-011, clarification #4)

1. As Driver A (with sufficient `balance_egp` from Scenario 2): `POST /api/wallet/withdrawals` with `{ amount_egp: "50.00", payout_reference: "01012345678" }` → expect `201`, `status: "PENDING"`.
2. As Driver A: submit a second withdrawal request immediately → expect `409 pending_request_exists`.
3. As admin: `GET /api/admin/withdrawal-requests` → the pending request appears, oldest-first.
4. As admin: `POST /api/admin/withdrawal-requests/{id}/approve` → expect `200`, a new `WITHDRAWAL_DEBIT` ledger entry, `balance_egp` decreased by `50.00`.
5. As Driver A: submit a new withdrawal request now that the first is resolved → expect `201` (no longer blocked).

**Pass condition**: FR-011, clarification #4.

## 8. Withdrawal approval re-checks balance at review time (research.md §10)

1. As Driver A: submit a withdrawal request for the driver's entire available balance.
2. Before the admin reviews it, trigger a `COMMISSION_DEBIT` against Driver A (complete a normal cash ride) that reduces `balance_egp` below the requested amount.
3. As admin: attempt to approve the pending withdrawal → expect `409 insufficient_balance_at_approval`.
4. As admin: reject it instead with a reason → expect `200`, `status: "REJECTED"`.

**Pass condition**: research.md §10.

Refer to `contracts/api.md` for exact request/response shapes and `data-model.md` for the underlying schema.
