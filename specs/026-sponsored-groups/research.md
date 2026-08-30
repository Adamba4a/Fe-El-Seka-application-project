# Phase 0 Research: Sponsored Groups

All items below were resolved by reading the existing codebase rather than external research — this feature extends established in-repo patterns (Groups/Spec 024, Wallet Top-Up/Spec 018, Driver Fare Override/Spec 023) end to end. No `NEEDS CLARIFICATION` markers remain in the Technical Context.

## 1. Where sponsorship state lives: extend `groups` vs. a new table

**Decision**: Add three columns directly to the existing `groups` table: `is_sponsored BOOLEAN NOT NULL DEFAULT false`, `funded_balance_egp NUMERIC(12,2) NOT NULL DEFAULT 0.00`, `dashboard_contact_user_id UUID REFERENCES profiles(id)`. Add `CHECK (funded_balance_egp >= 0.00)` and `CHECK (NOT is_sponsored OR type IN ('company', 'university'))`.

**Rationale**: `booking_service.create_booking` already locks and reads the `rides`/`groups` chain on the hot booking path (`ride["group_id"]` → membership check). A separate `sponsored_groups` extension table would force a second join (and a second row lock) into that same transaction for every booking on every group-scoped ride, most of which aren't sponsored. Columns on `groups` let the existing single `FOR UPDATE` lock (already needed to safely debit `funded_balance_egp`, see §4) cover both the membership check and the sponsorship check in one round trip. This mirrors how Spec 023 added `fair_price_per_seat` directly onto `rides` rather than a side table.

**Alternatives considered**: New `sponsored_groups(group_id PK, funded_balance_egp, dashboard_contact_user_id)` 1:1 extension table — rejected; adds a join/lock to the booking hot path for no isolation benefit, since sponsorship is a property of the group itself, not a separate lifecycle.

## 2. New ledger entry types

**Decision**: Extend `driver_ledger_entries.type` (Postgres enum `ledger_entry_type`) with three new values: `SPONSORED_RIDE_CREDIT` (driver's net-of-commission credit at sponsored-booking creation, §4), `SPONSORED_RIDE_REVERSAL` (reversal when a sponsored booking is cancelled, §5), `WITHDRAWAL_DEBIT` (driver-initiated withdrawal approved by an admin, §8). Mirror `models/wallet.py`'s `LedgerEntryType(str, Enum)` with the three additions.

**Rationale**: The ledger is append-only and immutable by design (existing `COMMISSION_DEBIT`/`ADMIN_CREDIT`/`ADMIN_DEBIT` never get updated or deleted) — a reversal must be a new opposite-direction row, never an edit to the original credit, so every sponsored money movement stays independently auditable.

**Alternatives considered**: Reuse `ADMIN_CREDIT`/`ADMIN_DEBIT` for sponsored movements — rejected; it would make the company dashboard and admin financial reports unable to distinguish sponsorship-driven wallet activity from manual admin adjustments, defeating the read-only dashboard's purpose (FR-018/019 area of spec).

## 3. `bookings.payment_source` column

**Decision**: Add `payment_source TEXT NOT NULL DEFAULT 'CASH' CHECK (payment_source IN ('CASH', 'SPONSORED'))` to `bookings`, set once at booking-creation time in `create_booking` based on whether the ride's group is sponsored at that instant, and never changed afterward.

**Rationale**: Per the clarification session, sponsorship on a sponsored-group-scoped ride is always automatic and non-optional (no cash alternative) — so a ride is either fully sponsored or fully cash, never mixed, and `payment_source` is fully determined by `rides.group_id` at booking time. Capturing it immutably on the booking row (rather than deriving it live from the group at completion time) means a later change to the group's sponsorship status (e.g., admin turns off sponsorship, or the funded balance is later topped up) can never retroactively reinterpret a historical booking's settlement — `ride_service.complete_ride` needs a stable, point-in-time answer to "was this booking's commission already settled at creation" (see §5), and a live lookup would not give that.

**Alternatives considered**: Derive payment source live from `rides.group_id` + `groups.is_sponsored` at ride-completion time instead of storing it on the booking — rejected; a group's `is_sponsored` flag is designed to be admin-mutable at any time (auto-upgrade per FR-003), so a live check at completion could disagree with what was actually true (and settled) at booking time.

## 4. Booking-time settlement for sponsored bookings

**Decision**: In `booking_service.create_booking`, after the existing group-membership check (lines 111-123) and before the seat-price computation, branch on the ride's sponsoring group. If `groups.is_sponsored` is true for `ride["group_id"]`:
1. Lock the group row (`SELECT ... FROM groups WHERE id = $1 FOR UPDATE`) in the same transaction as the seat claim.
2. Compute `total_seat_price = per_seat_price * seats` (premium pickup/dropoff fees are out of scope — see §7).
3. If `groups.funded_balance_egp < total_seat_price`, reject the booking with 422 `insufficient_funded_balance` (FR-008) — no seats are claimed, mirroring the existing `no_seats_available` failure path.
4. Debit `groups.funded_balance_egp -= total_seat_price`.
5. Compute the driver's net-of-commission credit using the same per-seat formula `commission_service.deduct_commission` already uses (fuel-cost commission + distance fee + safety margin, apportioned per seat over `rides.total_seats`, plus the markup share if `price_per_seat > fair_price_per_seat`), since every input (`fuel_cost_egp`, `distance_fee_egp`, `safety_margin_egp`, `fair_price_per_seat`) is already present on the locked `rides` row.
6. Credit the driver's wallet (`wallet_service.increment_balance`) by the net amount and insert a `SPONSORED_RIDE_CREDIT` ledger entry (`ride_id`, `booking_id`, `note`).
7. Set the new booking's `payment_source = 'SPONSORED'`.

**Rationale**: On this platform, cash for a normal ride passes directly from passenger to driver off-platform — the wallet only tracks the driver's commission liability to the platform. A sponsored ride has no cash handoff at all (the company is paying, not the passenger), so the driver has no other way to receive their earnings for that seat except an explicit wallet credit. Settling per-seat at booking time (rather than waiting for ride completion, like cash bookings) is necessary because a ride can carry a mix of confirmed and later-cancelled bookings over time, and each booking's company-funds debit / driver-credit is a self-contained, immediately final transaction the moment a seat is confirmed sponsored — there's no reason to defer it to ride completion, and deferring it would require carrying per-booking financial state across the ride's whole lifecycle for no benefit.

**Alternatives considered**: Defer sponsored settlement to `ride_service.complete_ride` alongside cash bookings' `deduct_commission` — rejected; would require `complete_ride` to reach back into each sponsored booking's original per-seat price to compute the same commission split, with no benefit over settling immediately, and would leave the driver unpaid for a fully-attended sponsored ride until the driver remembers to mark it complete.

## 5. Ride-completion exemption for sponsored bookings

**Decision**: In `ride_service.complete_ride`, change the `confirmed_bookings` query that feeds `deduct_commission` to filter `AND payment_source = 'CASH'`. `complete_ride_bookings` (which transitions bookings to `completed`) stays unchanged and continues to operate over all confirmed bookings regardless of `payment_source` — only the *commission* pipeline needs to exclude sponsored bookings, since their commission was already settled at creation (§4).

**Rationale**: `commission_service.deduct_commission` already short-circuits (logs and returns) when passed an empty booking list, so a ride with zero cash bookings (i.e., every seat sponsored) naturally results in no `COMMISSION_DEBIT` — no new branching needed inside `commission_service.py` itself. Filtering at the query is the smallest change that prevents double-charging: without it, a sponsored booking's price would be counted a second time toward the ride's total commission base, incorrectly debiting the driver for revenue already fully settled per-seat.

**Alternatives considered**: Have `deduct_commission` itself accept and ignore sponsored bookings — rejected; `commission_service.py` has no reason to know about `payment_source` or groups, and filtering at the query site keeps that module's contract (\"pass me the bookings whose commission I should compute\") unchanged.

## 6. Ride-creation reservation exemption for fully-sponsored rides

**Decision**: In `ride_service.create_ride`, extend the existing group-membership lookup (lines 204-213) to also select `g.is_sponsored`. If the ride's group is sponsored, skip `check_available_balance` / `create_reservation` entirely — no wallet lock, no `commission_reservations` row, and ride creation is not gated on the driver's own wallet balance.

**Rationale**: `create_reservation` exists to guarantee the driver's wallet can cover their worst-case commission liability from cash collected directly from passengers. On a sponsored ride every seat settles independently at booking time via `SPONSORED_RIDE_CREDIT` (§4) — there is no future cash-commission liability against the driver's balance to reserve for, since the driver never collects cash for those seats in the first place. Requiring the driver to have wallet balance just to post a sponsored ride would be actively wrong: it would let a company's own free-ride sponsorship be blocked by the driver's unrelated wallet state.

**Alternatives considered**: Keep computing and reserving `max_commission` as an up-front safety margin even though it's not strictly owed — rejected; it would incorrectly gate ride creation on the driver's wallet balance for a ride where the driver owes nothing until each sponsored booking settles independently, contradicting the sponsorship's purpose (drivers should be able to post sponsored rides with zero wallet balance).

## 7. Premium pickup/dropoff fee scope

**Decision**: Sponsorship covers only the base per-seat price (`total_seat_price` in §4). Premium pickup/dropoff fees, if requested on a sponsored booking, remain unaffected by sponsorship — they are not part of the commission formula (`commission_service.deduct_commission` never references `premium_pickup_fee`/`premium_dropoff_fee`) and are already handled today as a cash amount collected directly by the driver, independent of `payment_source`.

**Rationale**: Since premium fees never flow through the commission/wallet system for cash bookings either, there's nothing to change — the sponsored-vs-cash branch in §4 only needs to touch `total_seat_price`, and `total_price` on the booking row can keep including the fees exactly as it does today for display purposes.

**Alternatives considered**: Extend `funded_balance_egp` debits to cover premium fees too — rejected; not required by any functional requirement, and would entangle a company's sponsorship budget with a per-passenger convenience option the company has no visibility into or control over.

## 8. Withdrawal request table

**Decision**: New `withdrawal_requests` table mirroring `wallet_topup_requests`' shape and RLS pattern in reverse: `id, driver_id, amount_egp, payout_reference, status, rejection_reason, reviewed_by, reviewed_at, ledger_entry_id, created_at, updated_at`. Status is `PENDING → APPROVED | REJECTED` only (no `CANCELLED` state — the spec's withdrawal flow, unlike top-up, has no driver-initiated cancel requirement). `payout_reference` holds the driver-supplied payout destination (e.g., their Vodafone Cash number), analogous to top-up's `payment_reference` but describing where money should go rather than where it came from.

**Rationale**: Directly mirrors the proven, already-shipped Spec 018 admin-review pattern in reverse, satisfying the spec's explicit framing (\"driver withdrawal-request flow mirroring wallet top-up in reverse\") and Principle VII (no duplication of shared functionality — reuse the same reviewed-request shape and admin-queue UI conventions rather than inventing a new one).

**Alternatives considered**: A 4-state machine matching top-up's `CANCELLED` state — rejected; the spec does not require a driver to retract a pending withdrawal request, and adding an unused state/transition would be unjustified complexity.

## 9. One-pending-withdrawal-at-a-time enforcement

**Decision**: DB-enforced via a partial unique index, `uq_withdrawal_one_pending_per_driver ON withdrawal_requests (driver_id) WHERE status = 'PENDING'` — identical mechanism to `wallet_topup_requests`' `uq_topup_one_pending_per_driver`.

**Rationale**: Directly implements FR-011 (one pending request at a time, from clarification #4) with the same race-safe, DB-level guarantee already proven for top-up requests, rather than an application-level check-then-insert that could race under concurrent submission.

**Alternatives considered**: Application-level check only (`SELECT ... WHERE status = 'PENDING'` before insert) — rejected; same TOCTOU race the top-up migration's own comment explicitly calls out avoiding.

## 10. Withdrawal approval balance re-check

**Decision**: Unlike top-up approval (a pure credit, which can never fail against the driver's balance), withdrawal approval is a debit and must re-validate the driver's *available* balance (`balance_egp - reserved_egp`) against the requested `amount_egp` at approval time, under the wallet's row lock — not just at submission time. If insufficient at approval time (e.g., a commission debit or sponsored-ride reversal consumed the balance between submission and review), the approval attempt fails with 409 and the admin must reject the request instead.

**Rationale**: A driver's balance can legitimately shrink between withdrawal submission and admin review (rides complete, commission is debited, sponsored bookings get cancelled/reversed). Approving anyway would let `decrement_balance` push the balance negative for a discretionary payout the driver didn't yet actually have — acceptable for `COMMISSION_DEBIT`/`SPONSORED_RIDE_REVERSAL` (unavoidable platform-side debits, per `decrement_balance`'s existing negative-balance tolerance), but not for a withdrawal the driver is choosing to cash out.

**Alternatives considered**: Lock the requested amount as `reserved_egp` at submission time (mirroring `commission_reservations`) so it's guaranteed available at approval — rejected as unnecessary complexity for the MVP; a driver submitting a withdrawal for more than they'll end up having is a rare edge case adequately handled by a same-transaction re-check and a clear rejection path, without introducing a second reservation subsystem alongside the existing commission one.

## 11. Sponsored-booking cancellation reversal

**Decision**: When a sponsored booking (`payment_source = 'SPONSORED'`) is cancelled, run the exact inverse of §4 in the same transaction as the existing cancellation flow: lock the group row, credit `groups.funded_balance_egp += total_seat_price` back, debit the driver's wallet by the same net amount via `wallet_service.decrement_balance` (already documented as tolerating a negative resulting balance — same tolerance `commission_service` already relies on for cash-ride commission debits), and insert a `SPONSORED_RIDE_REVERSAL` ledger entry referencing the same `booking_id`.

**Rationale**: Implements FR-010 (cancellation reversal) with the append-only ledger design from §2 — the original `SPONSORED_RIDE_CREDIT` entry is never edited, only offset by a new entry, keeping every state transition independently auditable. Allowing the driver's balance to go negative in the rare case they already withdrew the credited amount is consistent with the platform's existing accepted risk for `COMMISSION_DEBIT` and requires no new mitigation for this feature.

**Alternatives considered**: Block cancellation of a sponsored booking whose net credit the driver has already withdrawn — rejected; over-engineered for the MVP and inconsistent with how the rest of the ledger already tolerates negative balances rather than blocking state transitions.

## 12. Dashboard-contact validation

**Decision**: Enforce \"must already be a domain-verified member of the group\" (clarification #3) at the service layer — a new `set_dashboard_contact(group_id, admin_id, user_id)` function checks `group_memberships` for the target user before writing `groups.dashboard_contact_user_id`, at both initial designation and reassignment.

**Rationale**: Matches the exact validation pattern `group_service.transfer_ownership` already uses (look up `group_memberships`, 422 `not_a_group_member` if absent) — this feature reuses that established convention rather than adding a DB trigger or foreign-key-adjacent constraint for a rule that's naturally a service-layer invariant (Principle VII).

**Alternatives considered**: DB trigger validating `dashboard_contact_user_id` against `group_memberships` on every `groups` update — rejected; inconsistent with how `group_service.py` already centralizes every other membership-dependent invariant in Python, not the database.

## 13. Company dashboard placement

**Decision**: The read-only company dashboard lives in `apps/main` (the passenger-facing Next.js app), gated to the signed-in user matching `groups.dashboard_contact_user_id`, not in `apps/admin`. Backend surface: a new `GET /api/groups/{group_id}/sponsorship-dashboard` endpoint on the existing `groups_router` (`/api/groups` prefix), returning `funded_balance_egp`, recent `SPONSORED_RIDE_CREDIT`/`SPONSORED_RIDE_REVERSAL` ledger activity for that group, and member count.

**Rationale**: The dashboard contact is a member of the sponsoring organization using the platform as a passenger, not a platform administrator — `apps/admin` is reserved for Triplyy's own staff (per the constitution's three-app framing). Placing it in `apps/main` alongside the rest of that user's Groups UI (`GroupDetailResponse`, member list) keeps it consistent with how every other group-facing screen is already surfaced.

**Alternatives considered**: Build it in `apps/admin` with per-org login — rejected; would require a whole new authentication audience (org contacts, not Triplyy admins) that doesn't exist and isn't warranted for a read-only summary view.
