# Feature Specification: Financial System

**Feature Branch**: `011-financial-system`

**Created**: 2026-06-29

**Status**: Draft

**Input**: Phase 8 — Financial System: driver balance ledger, commission deduction (cash-only). Covers driver wallet management, automatic commission deduction on ride completion, admin manual top-up, negative-balance enforcement at ride creation, and an immutable financial audit trail.

---

## Clarifications

### Session 2026-06-29

- Q: Should the minimum required balance threshold for ride creation be a fixed amount (e.g., 50 EGP) or ride-specific? → A: Ride-specific — the driver's balance must be ≥ the maximum commission for that specific ride (`ride.fuel_cost_egp × 0.20`) at the time of creation. This is calculated from the same Phase 5 fare breakdown computed during ride creation. A short ride with a low commission may be allowed even when a longer ride with a higher commission is blocked. No fixed platform-wide threshold is used.
- Q: Should the ADMIN_DEBIT corrective entry be capped at the driver's current wallet balance, or can admin apply an arbitrary debit that takes the balance negative? → A: Capped at current balance — the debit amount MUST NOT exceed the wallet's current balance; the minimum resulting balance after a corrective debit is 0.00 EGP. Prevents accidental deep-negative corrections without requiring a second-approval workflow for MVP.
- Q: What is the correct commission calculation for Phase 8 — is it a configurable % applied to booking.fare_amount_egp, or derived from the Phase 5 fare breakdown? → A: Derived from the Phase 5 fare breakdown — the commission is specifically the platform commission component already embedded in the pricing formula: `fuel_cost × 0.20` for the entire ride, divided proportionally among confirmed bookings at completion. The 20% rate is a fixed system constant (not configurable), identical to the Phase 5 constant. Commission is NOT calculated as a % of the full fare amount, since the full fare also includes fuel cost recovery and safety margin which belong to the driver.
- Q: Should commission deduction at ride completion be proportional (per confirmed booking only) or charged as the full-ride commission regardless of seat fill rate? → A: Proportional — deduct `fuel_cost × 0.20 / seat_count` per confirmed booking that completed. The driver only collected cash commission from passengers who actually rode; charging for empty seats would mean deducting commission on revenue the driver never received.
- Q: Should the ride-specific balance check at creation use a live snapshot only, or should the platform hold/reserve the commission until the ride resolves? → A: Reserve it — when a driver creates a ride, the max commission (`fuel_cost × 0.20`) is immediately reserved against their wallet as a `CommissionReservation`. The driver's available balance (displayed and checked) = `balance_egp − reserved_egp`. On ride completion the reservation is converted to real `COMMISSION_DEBIT` ledger entries (proportional to confirmed bookings); unused reserved amount for empty seats is silently released. On ride cancellation the full reservation is released with no ledger entry. This completely prevents over-commitment across simultaneous rides.

---

## Business Objective *(mandatory)*

Fe El Seka generates revenue by collecting a platform commission from drivers on every completed ride. Passengers pay drivers in cash at pickup — there is no payment gateway. The platform's share is collected by deducting a commission from the driver's pre-loaded wallet balance when the ride is marked complete.

This phase introduces the financial backbone of the platform: a driver wallet that holds a spendable balance, an append-only ledger that records every credit and debit permanently, automatic commission deduction wired into the Phase 7 ride-completion flow, and an admin interface for topping up driver wallets. A commission reservation system ensures that when a driver posts a ride, the platform immediately holds the worst-case commission against their available balance — preventing over-commitment across simultaneous rides. On completion the hold converts to a real deduction; on cancellation it dissolves with nothing charged.

Without this phase, the platform delivers transportation value but has no mechanism to sustain itself financially. Phase 7 ride completion produces no financial consequence; drivers can post unlimited rides without any platform commitment.

**Constitutional Domain**: Financial System / Platform Operations

**Affected Applications**: Main App (driver wallet screen — balance + transaction history); Admin Panel (wallet management — manual top-up, commission rate configuration); FastAPI backend (wallet service, commission engine, balance enforcement gate).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Automatic Commission Deduction on Ride Completion (Priority: P1)

Ahmed completes a ride. At that moment, without any manual action, the platform calculates the commission owed on each confirmed booking and deducts it from his wallet balance in a single atomic operation. His wallet balance immediately reflects the deductions. An immutable ledger entry is created for each commission charge so that every deduction is permanently traceable.

**Why this priority**: This is the platform's core revenue mechanism. Every completed ride must produce a commission record. The deduction is wired into the Phase 7 ride-completion transaction so that no ride can be marked complete without settling the platform's share. All other financial stories are secondary to this foundational flow.

**Independent Test**: Create a ride with 4 seats and `fuel_cost_egp` = 40.00 EGP. Verify a `CommissionReservation` of 8.00 EGP is created and the driver's available balance drops by 8.00 EGP. Then complete the ride with 2 confirmed bookings. Verify: (a) the `CommissionReservation` is deleted; (b) two `COMMISSION_DEBIT` ledger entries of 2.00 EGP each are created (`40.00 × 0.20 / 4`); (c) `balance_egp` decreases by 4.00 EGP; (d) `reserved_egp` decreases by 8.00 EGP (the full reservation is released — 4.00 EGP real deduction + 4.00 EGP released for the 2 empty seats); (e) if the completion transaction is rolled back, no ledger entries are created and the reservation remains intact.

**Acceptance Scenarios**:

1. **Given** a ride in `in_progress` status with 4 total seats, `fuel_cost_egp` = 40.00 EGP, and 2 confirmed bookings (with an existing `CommissionReservation` of 8.00 EGP from ride creation), **When** the driver taps "Complete Ride," **Then** within the same atomic transaction: the ride transitions to `completed`; the booking cascade fires; the `CommissionReservation` is deleted; a `COMMISSION_DEBIT` ledger entry of 2.00 EGP is created for each confirmed booking (`40.00 × 0.20 / 4`); `balance_egp` decreases by 4.00 EGP; `reserved_egp` decreases by 8.00 EGP; the 4.00 EGP reserved for empty seats is silently released back to available balance.
2. **Given** a ride completion that succeeds, **When** the ledger entries are created, **Then** each entry is append-only and cannot be modified or deleted by any application role; the entries include: `driver_id`, `ride_id`, `booking_id`, `amount_egp`, `fuel_cost_egp_snapshot`, `type = COMMISSION_DEBIT`, `created_at`.
3. **Given** a ride with zero confirmed bookings (all pending, cancelled, or never booked), **When** the driver completes the ride, **Then** no `COMMISSION_DEBIT` ledger entries are created; the `CommissionReservation` is deleted and the full reserved amount is released back to available balance; `balance_egp` is unchanged; the ride still transitions to `completed`.
4. **Given** a commission deduction that would make the driver's wallet balance negative, **When** the ride is completed, **Then** the commission is still deducted (the balance may go negative) and the transaction succeeds; the driver's ability to create future rides is then gated by the balance enforcement check (Story 4).
5. **Given** the commission deduction step fails due to a database error, **When** the error occurs, **Then** the entire ride-completion transaction rolls back — the ride remains `in_progress`, no bookings complete, and no ledger entries are created; the driver receives an error response and is prompted to retry.

---

### User Story 2 — Admin Manually Tops Up Driver Wallet (Priority: P2)

The platform has no payment gateway. Drivers pay their platform commitment offline (bank transfer, cash handoff). The admin confirms receipt and credits the driver's wallet through the admin panel. Ahmed's wallet balance increases immediately and an immutable `ADMIN_CREDIT` ledger entry records who topped up, how much, and when.

**Why this priority**: Without a way to add funds, drivers cannot accumulate balance to sustain ride creation. Top-up is how the platform receives money from drivers. It is P2 because commission deduction (P1) is the outflow that must exist first — the top-up is the corresponding inflow mechanism.

**Independent Test**: Log in as admin. Navigate to a driver's wallet in the admin panel. Enter a top-up amount (e.g., 200 EGP) and submit. Verify: the driver's wallet balance increases by exactly 200 EGP; an `ADMIN_CREDIT` ledger entry exists referencing the admin user's ID, the amount, and a timestamp; the driver's wallet screen reflects the new balance without requiring a logout/login.

**Acceptance Scenarios**:

1. **Given** an authenticated admin on a driver's wallet management screen, **When** the admin enters a positive top-up amount and confirms, **Then** the driver's wallet balance increases by exactly that amount and an `ADMIN_CREDIT` ledger entry is created with `created_by` set to the admin's user ID.
2. **Given** an admin attempting to submit a top-up with a zero or negative amount, **When** the form is submitted, **Then** the system rejects the request with a validation error; no ledger entry is created and the wallet balance is unchanged.
3. **Given** any non-admin authenticated user (driver or passenger), **When** they attempt to call the top-up endpoint directly, **Then** the system returns HTTP 403; the wallet balance is unchanged.
4. **Given** an admin topping up a wallet that does not yet exist for a verified driver, **When** the top-up is submitted, **Then** the system creates the wallet record and applies the credit in a single operation; no separate wallet-creation step is required from the admin.
5. **Given** an admin top-up is submitted, **When** the ledger entry is created, **Then** the entry is immutable — no application endpoint can modify or delete it.

---

### User Story 3 — Driver Views Wallet Balance and Transaction History (Priority: P3)

Ahmed opens his wallet screen. He sees two balance figures: his total balance (real money from top-ups minus past deductions) and his available balance (total minus what is currently reserved for his active scheduled rides). Below that, a chronological list shows every transaction — admin credits, commission debits — each with the amount, type, associated ride, and date. He immediately understands how much he can spend and where every EGP went.

**Why this priority**: Financial transparency is a trust requirement for drivers. Without visibility into their balance and ledger, drivers cannot verify charges or plan their activity. P3 because the read-only view does not block any platform operation — the commission and top-up flows work regardless of whether the display exists.

**Independent Test**: With a driver wallet containing at least one `ADMIN_CREDIT`, one `COMMISSION_DEBIT`, and one active `CommissionReservation` (a scheduled ride), open the driver wallet screen. Verify: total balance is displayed; available balance = total balance − reserved amount is displayed separately; each ledger entry is listed with amount, type label ("Commission Charge" / "Balance Top-Up"), associated ride link (for debits), and timestamp; entries are ordered newest-first; the available balance equals the sum of all credits minus the sum of all debits minus the sum of all active reservations.

**Acceptance Scenarios**:

1. **Given** an authenticated driver with an existing wallet and at least one active `CommissionReservation`, **When** they open the wallet screen, **Then** they see: (a) total balance (`balance_egp`) — real money from credits minus real deductions; (b) reserved amount (`reserved_egp`) — total commission held for active scheduled rides; (c) available balance (`balance_egp − reserved_egp`) — what they can actually use to create new rides; and (d) the list of all past ledger entries ordered by `created_at` descending.
2. **Given** a driver's wallet with multiple transaction types, **When** the transaction list is rendered, **Then** each entry displays: transaction type (human-readable label), amount in EGP (signed — credits positive, debits negative), associated ride reference for `COMMISSION_DEBIT` entries, and the timestamp.
3. **Given** a driver who has no wallet record yet (newly onboarded, never topped up), **When** they open the wallet screen, **Then** the system displays a balance of 0.00 EGP and an empty transaction list; no error is shown.
4. **Given** any other authenticated user (passenger, admin), **When** they attempt to access a specific driver's wallet endpoint directly, **Then** the system returns HTTP 403; no financial data is exposed.
5. **Given** a driver with more than 50 ledger entries, **When** the transaction history is loaded, **Then** entries are paginated (50 per page); the driver can navigate to older entries.

---

### User Story 4 — Balance Enforcement at Ride Creation (Priority: P4)

Ahmed has a total balance of 12.00 EGP, but he already has one active scheduled ride with a reserved commission of 8.00 EGP — so his available balance is 4.00 EGP. He tries to post a new ride from Nasr City to Maadi — 22 km, max commission 5.08 EGP. The system checks his available balance (4.00 EGP) against the new ride's commission (5.08 EGP) and rejects it: "Insufficient available balance for this ride. Available: 4.00 EGP. Required: 5.08 EGP." Ahmed tries a shorter route — Nasr City to Downtown, 12 km, commission 2.77 EGP — the system accepts it, creates the ride, and immediately reserves 2.77 EGP, leaving Ahmed with 1.23 EGP available.

**Why this priority**: The reservation system makes over-commitment impossible — a driver cannot post more rides than their balance can cover even if rides complete at full capacity simultaneously. The check is ride-specific so short, affordable rides stay accessible even when a driver's balance is low. P4 because it depends on the balance system (P1–P3), the Phase 5 fare calculation, and the reservation infrastructure.

**Independent Test**: Set a driver's wallet to 10.00 EGP. Create a first ride with `fuel_cost_egp` = 20.00 EGP (reservation = 4.00 EGP). Verify available balance drops to 6.00 EGP. Attempt to create a second ride with `fuel_cost_egp` = 40.00 EGP (commission = 8.00 EGP > 6.00 EGP available). Verify HTTP 422 with the driver's available balance (6.00 EGP) and required commission (8.00 EGP) in the response. Then create a second ride with `fuel_cost_egp` = 25.00 EGP (commission = 5.00 EGP ≤ 6.00 EGP available). Verify it succeeds and available balance drops to 1.00 EGP. Cancel the first ride and verify the 4.00 EGP reservation is released; available balance returns to 5.00 EGP.

**Acceptance Scenarios**:

1. **Given** a driver whose available balance (`balance_egp − reserved_egp`) is less than the maximum commission for the specific ride being created (`fuel_cost_egp × 0.20`), **When** they submit the ride creation request, **Then** the system returns HTTP 422 with `error_code = INSUFFICIENT_WALLET_BALANCE`; no ride is created and no reservation is added; the response body includes the driver's available balance, the required commission for this ride, and a message that a shorter (lower-commission) ride may still be created.
2. **Given** a driver whose available balance is greater than or equal to the max commission for the ride (`fuel_cost_egp × 0.20`), **When** they submit a valid ride creation request, **Then** the ride is created AND a `CommissionReservation` of `fuel_cost_egp × 0.20` is atomically created for this ride; `reserved_egp` increases accordingly; the driver's available balance decreases immediately.
3. **Given** a driver blocked from a long-distance ride due to insufficient available balance, **When** they submit a shorter ride whose commission fits within their available balance, **Then** the shorter ride is accepted and its reservation is created; the system does not block all ride creation, only rides whose commission exceeds available balance.
4. **Given** a driver with no wallet record (effective available balance 0.00 EGP), **When** they attempt to create any ride with a non-zero route, **Then** the system returns HTTP 422 — any valid ride has commission > 0.00 EGP; the driver must be topped up by an admin before creating rides.

---

### Edge Cases

- What if two concurrent ride completions for the same driver fire simultaneously? Each completion deducts commission within its own transaction using a row-level lock on the `driver_wallets` record; the second transaction waits for the first to commit, then applies its own deduction to the updated balance. No double-spend or lost-update anomaly occurs.
- What if the commission rate is changed between ride creation and ride completion? The commission rate applicable at the time of completion is used, and the applied rate is snapshotted in the ledger entry. Drivers are not guaranteed the rate that was active when they posted the ride.
- What if a booking's fare amount is zero (e.g., a free ride posted by the driver)? Commission of 0.00 EGP is calculated; a `COMMISSION_DEBIT` ledger entry is still created for auditability with `amount_egp = 0.00`; the wallet balance is unchanged.
- What if the driver has no wallet record at completion time? The system creates a wallet record with a starting balance of 0.00 EGP and immediately applies the commission debit, resulting in a negative balance; the completion still succeeds.
- What if an admin accidentally enters the wrong top-up amount? Ledger entries are immutable — the incorrect credit cannot be deleted or modified. The admin must issue a correcting `ADMIN_DEBIT` adjustment entry via the same admin interface; both entries remain permanently in the audit trail. The corrective debit is capped at the driver's current balance (FR-014), so if the driver has already spent part of the erroneous credit on commission deductions, only the remaining balance can be recovered via debit.
- What if a driver simultaneously submits two ride creation requests that together would exceed their available balance, but each individually passes the check? The balance check and reservation creation are executed atomically under a row-level lock on `driver_wallets`. The first request commits, reducing available balance. The second request reads the updated available balance and is rejected if it no longer fits. No over-commitment is possible.
- What if a ride is cancelled (by the driver, a system timeout, or an admin) after the `CommissionReservation` was created? The cancellation handler MUST delete the reservation in the same transaction. `reserved_egp` decreases; available balance is fully restored. No ledger entry is created — the reservation was virtual and nothing was ever really charged.
- What if a driver's total balance decreases (from another ride completing and deducting commission) while a different ride is still scheduled with a reservation? The reservation for the scheduled ride remains unchanged. The completion deduction reduces `balance_egp` directly; if the result is that `balance_egp < reserved_egp` (total balance is now less than what is reserved), available balance goes negative. This is a rare but accepted state — the driver had enough available balance when they created each ride; the deductions from concurrent completions caused the imbalance. The scheduled ride is not cancelled; its commission is deducted on completion regardless.

---

## Requirements *(mandatory)*

### Functional Requirements

**Driver Wallet**

- **FR-001**: The system MUST maintain one wallet record per verified driver. A wallet record MUST be created automatically on first credit (admin top-up), first commission deduction, or first ride creation (whichever comes first); no manual wallet-creation step is required.
- **FR-002**: A driver's wallet MUST store two balance values: `balance_egp` (real balance — sum of all credits minus sum of all real debits, derived from the append-only ledger) and `reserved_egp` (sum of all active `CommissionReservation` amounts for rides in `scheduled` or `in_progress` status). The driver's **available balance** = `balance_egp − reserved_egp`. All balance enforcement checks and driver-facing displays MUST use the available balance, not the raw `balance_egp`.
- **FR-003**: The system MUST provide an authenticated endpoint for drivers to retrieve their total balance, reserved amount, available balance, and paginated ledger history (50 entries per page, ordered by `created_at` descending).
- **FR-004**: A driver MUST only be able to access their own wallet data. Requests for another user's wallet MUST be rejected with HTTP 403.

**Commission Deduction**

- **FR-005**: When a ride transitions to `completed` status (Phase 7 FR-018), within the same atomic transaction the system MUST: (a) delete the ride's `CommissionReservation`; (b) create a proportional `COMMISSION_DEBIT` ledger entry for each booking transitioning from `confirmed` to `completed`; (c) decrease `balance_egp` by the sum of real deductions; (d) decrease `reserved_egp` by the full reserved amount (the difference between the reservation and actual deductions for empty seats is silently released). If a ride completes with zero confirmed bookings, step (b) and (c) are skipped — the reservation is still deleted and `reserved_egp` still decreases.
- **FR-006**: Commission deduction is **proportional** — only confirmed bookings that completed generate a deduction. The per-booking commission is: `commission_per_booking = ROUND((ride.fuel_cost_egp × 0.20 + ride.safety_margin_egp) / ride.total_seat_count, 2)`. The platform keeps both the 20% fuel-cost commission and the flat safety margin — the safety margin is platform revenue, not a driver buffer. The 20% rate is the same fixed system constant used in Phase 5 — it is NOT separately configurable in Phase 8. Commission is NOT calculated as a percentage of `booking.fare_amount_egp` (which also includes the driver's fuel cost recovery). A ride where only 2 of 4 seats filled results in 2 commission deduction entries, not the full 4-seat commission.
- **FR-007**: Each commission deduction MUST create an immutable `COMMISSION_DEBIT` ledger entry containing: `driver_id`, `ride_id`, `booking_id`, `amount_egp`, `fuel_cost_egp_snapshot` (the ride's stored fuel cost used in the calculation), `type = COMMISSION_DEBIT`, and `created_at`.
- **FR-008**: The commission deduction MUST be executed within the same database transaction as the Phase 7 ride-completion cascade. If the transaction rolls back for any reason, no commission ledger entries are created and the wallet balance is unchanged.
- **FR-009**: Commission deduction MUST succeed even if it makes the driver's wallet balance negative. A negative balance does not block ride completion; it only blocks future ride creation (FR-015).

**Admin Top-Up**

- **FR-010**: The system MUST provide an admin-only endpoint (`POST /admin/drivers/{driver_id}/wallet/topup`) that credits a specified positive amount (in EGP) to the driver's wallet.
- **FR-011**: Each successful top-up MUST create an immutable `ADMIN_CREDIT` ledger entry containing: `driver_id`, `amount_egp`, `type = ADMIN_CREDIT`, `created_by` (the admin user ID), `note` (optional free-text reason), and `created_at`.
- **FR-012**: Top-up requests with a zero or negative amount MUST be rejected with HTTP 422 before any database write occurs.
- **FR-013**: Only authenticated users with the admin role MUST be permitted to call the top-up endpoint; all other authenticated users MUST receive HTTP 403.

**Admin Adjustment (Corrective Debit)**

- **FR-014**: The system MUST provide an admin-only endpoint (`POST /admin/drivers/{driver_id}/wallet/adjust`) that records a corrective `ADMIN_DEBIT` entry to reverse an erroneous top-up. Like top-up, this creates an immutable ledger entry rather than modifying any existing entry. The requested debit amount MUST NOT exceed the driver's **available balance** (`balance_egp − reserved_egp`) — debiting into reserved funds would silently break active ride reservations. A debit that would reduce `balance_egp` below `reserved_egp` MUST be rejected with HTTP 422 and an error indicating the maximum allowable debit (the current available balance). The minimum resulting available balance after any corrective debit is 0.00 EGP.

**Balance Enforcement at Ride Creation**

- **FR-015**: Before creating a new ride, the system MUST calculate the maximum commission for that specific ride — `max_commission = ROUND(ride.fuel_cost_egp × 0.20 + ride.safety_margin_egp, 2)` — and verify that the driver's **available balance** (`balance_egp − reserved_egp`) is greater than or equal to `max_commission`. The check and the subsequent reservation creation (FR-021) MUST be executed atomically. If the check fails, the system MUST return HTTP 422 with `error_code = INSUFFICIENT_WALLET_BALANCE`; the response body MUST include the driver's available balance, the required `max_commission` for this ride, and a message that a shorter ride with a lower commission may be created instead.
- **FR-016**: There is no fixed platform-wide minimum balance threshold. The balance requirement is ride-specific, checked against available balance (not total balance), and computed fresh for each ride creation attempt. A driver blocked from a long-distance ride may still create a shorter ride whose commission fits within their available balance.
- **FR-017**: If a driver has no wallet record, their effective `balance_egp` and `reserved_egp` are both 0.00 EGP. Since any valid ride has a commission > 0.00 EGP, a driver with no wallet record cannot create any ride until topped up by an admin. The wallet record is created automatically on first ride creation (along with the first reservation) if it does not already exist.

**Commission Rate Configuration**

- **FR-018**: The platform commission rate (20% of fuel cost) is a **fixed system constant** identical to the one used in Phase 5's pricing formula. It MUST NOT be stored as a configurable environment variable or database setting in Phase 8 — it is the same constant defined in Phase 5. Any future change to this constant requires a coordinated update across Phase 5 and Phase 8.
- **FR-019**: The `fuel_cost_egp` value used in the commission calculation MUST be sourced from the ride's stored Phase 5 fare breakdown (`rides.fare_breakdown.fuel_cost_egp`) — the same value that was used to determine the passenger's fare at ride creation. This ensures commission amounts are fully determined at ride creation time and do not change at completion.

**Commission Reservation Lifecycle**

- **FR-021**: When a new ride is successfully created and the available balance check (FR-015) passes, the system MUST atomically create a `CommissionReservation` record for that ride with `reserved_amount_egp = ROUND(ride.fuel_cost_egp × 0.20, 2)` and increment the driver's `wallet.reserved_egp` by the same amount. This reservation reduces the driver's available balance immediately and prevents over-commitment across concurrent ride postings.
- **FR-022**: When a ride transitions to any terminal cancelled state (`cancelled` — whether by the driver, a system rule, or an admin action) the system MUST atomically delete the ride's `CommissionReservation` and decrement `wallet.reserved_egp` by the reservation amount. No ledger entry is created — the reservation was virtual and nothing was charged. This applies regardless of whether the cancellation happens before or after passengers have booked.
- **FR-023**: A ride MUST have at most one active `CommissionReservation` at any time. If a ride is re-priced (not applicable for MVP since fares are non-negotiable per Phase 5 FR-027) or its seat count changes, the reservation amount MUST be recalculated and the wallet's `reserved_egp` adjusted accordingly.

**Ledger Immutability**

- **FR-020**: Ledger entries (`driver_ledger_entries`) MUST be an append-only table. No application endpoint or database role used by the application MUST be granted `UPDATE` or `DELETE` privileges on this table. Entries are written once and never modified.

### Key Entities

- **DriverWallet**: One record per driver. Attributes: `id` (UUID); `driver_id` (UUID, foreign key → users, unique); `balance_egp` (decimal 12,2 — real balance, always consistent with the ledger sum: sum of credits minus sum of debits); `reserved_egp` (decimal 12,2 — sum of all active `CommissionReservation` amounts for this driver's scheduled/in-progress rides; always ≥ 0.00); `available_egp` is a derived value (`balance_egp − reserved_egp`) — never stored separately, always computed; `created_at`; `updated_at`.

- **CommissionReservation**: A temporary hold placed on a driver's available balance when a ride is created. One per ride. Automatically deleted when the ride is completed or cancelled. Attributes: `id` (UUID); `wallet_id` (UUID, foreign key → driver_wallets); `driver_id` (UUID — denormalized); `ride_id` (UUID, unique — one reservation per ride); `reserved_amount_egp` (decimal 10,2 — `fuel_cost_egp × 0.20` at time of ride creation); `created_at`.

- **DriverLedgerEntry**: Immutable financial event record. Attributes: `id` (UUID); `wallet_id` (UUID, foreign key → driver_wallets); `driver_id` (UUID — denormalized for query efficiency); `type` (enum: `COMMISSION_DEBIT`, `ADMIN_CREDIT`, `ADMIN_DEBIT`); `amount_egp` (decimal 10,2 — always positive; the sign is conveyed by `type`); `ride_id` (UUID, nullable — set for `COMMISSION_DEBIT` entries); `booking_id` (UUID, nullable — set for `COMMISSION_DEBIT` entries); `fuel_cost_egp_snapshot` (decimal 10,2, nullable — the ride's stored fuel cost used in the commission calculation, for `COMMISSION_DEBIT` entries — provides full auditability without a separate commission_rate field since the rate is the fixed Phase 5 constant 20%); `created_by` (UUID, nullable — the admin user ID for `ADMIN_CREDIT` / `ADMIN_DEBIT` entries); `note` (text, nullable — optional admin annotation); `created_at` (timestamp, non-nullable).

- **CommissionRate (fixed system constant)**: The platform commission rate is **20% of fuel cost** — the same fixed constant used in Phase 5's pricing formula (`per_seat_price = (fuel_cost + fuel_cost×0.20 + safety_margin) / seat_count`). It is NOT a configurable environment variable or database value in Phase 8. The commission component is already determined at ride creation (when Phase 5 calculates and stores the fare breakdown). Phase 8 reads the stored `fuel_cost_egp` from the ride's fare breakdown to compute the per-booking deduction.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of completed rides with at least one confirmed booking result in a corresponding `COMMISSION_DEBIT` ledger entry created within the same database transaction as ride completion — verified by comparing `rides.completed_at` timestamps against `driver_ledger_entries.created_at` for all completed rides.
- **SC-002**: Commission calculation accuracy — for every `COMMISSION_DEBIT` entry, `amount_egp` equals `ROUND(fuel_cost_egp_snapshot × 0.20 / ride.total_seat_count, 2)` to within ±0.00 EGP (exact match required, not approximation).
- **SC-003**: Zero ledger entries are ever modified or deleted — verified by comparing the ledger row count and checksum at regular intervals; any discrepancy is a critical incident.
- **SC-004**: Admin can complete a driver wallet top-up in under 60 seconds from landing on the driver's wallet management page.
- **SC-005**: 100% of ride creation attempts where the driver's available balance (`balance_egp − reserved_egp`) is less than the ride's max commission are rejected before a ride record or reservation is created.
- **SC-006**: Driver wallet integrity is verifiable at any time: `balance_egp` equals the sum of all `ADMIN_CREDIT` entries minus the sum of all `COMMISSION_DEBIT` and `ADMIN_DEBIT` entries; `reserved_egp` equals the sum of all active `CommissionReservation` amounts; `available_egp = balance_egp − reserved_egp`. Any discrepancy in any of these three equations is a critical integrity incident.
- **SC-008**: 100% of ride cancellations (by driver, system, or admin) result in the associated `CommissionReservation` being deleted and `reserved_egp` being decremented within the same transaction — verified by confirming no orphaned reservations exist for rides in a terminal status.
- **SC-007**: Financial audit trail is complete — every EGP that enters or leaves a driver's wallet has a corresponding immutable ledger entry traceable to a specific action (ride completion, admin top-up, or admin adjustment).

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The commission deduction step within the ride-completion transaction MUST complete within 500ms. If it exceeds this limit, the parent transaction MUST time out and roll back; the ride remains `in_progress`.
- **NFR-002**: The driver wallet balance read endpoint MUST respond within 200ms at p95 under normal load (≤1,000 active users).
- **NFR-003**: All wallet and ledger endpoints MUST require a valid Supabase Auth JWT; unauthenticated requests MUST be rejected with HTTP 401.
- **NFR-004**: Concurrent commission deductions for the same driver wallet (e.g., two rides completing simultaneously) MUST use a pessimistic row-level lock (`SELECT ... FOR UPDATE`) on the `driver_wallets` record to prevent lost-update anomalies. No commission deduction must be lost or double-applied.
- **NFR-005**: The `driver_ledger_entries` table MUST be protected at the database permission level: the application's database role MUST hold `INSERT` and `SELECT` privileges only — `UPDATE` and `DELETE` MUST be revoked. This is enforced in the migration, not only at the API layer.
- **NFR-006**: Wallet balance MUST be stored as a fixed-point decimal type (not floating-point) to prevent rounding errors in financial calculations.
- **NFR-007**: Every wallet write operation (top-up, commission deduction, adjustment) MUST emit a structured log entry containing: operation type, driver ID, amount, associated ride/booking ID (where applicable), admin actor ID (where applicable), duration in milliseconds, and any error details. These logs constitute the operational audit trail alongside the ledger table.
- **NFR-008**: The ride-specific balance check and reservation creation MUST be executed atomically within the same database transaction as the ride insertion, using a `SELECT ... FOR UPDATE` lock on the `driver_wallets` row. The check compares the driver's live available balance (`balance_egp − reserved_egp`) against the ride's max commission. This prevents two concurrent ride creations from both passing the check against a stale available balance — the row lock guarantees each sees the other's reservation before committing.
- **NFR-009**: `CommissionReservation` records MUST be cleaned up atomically with their parent event (ride completion or cancellation). No reservation MUST exist for a ride in `completed` or `cancelled` status. An orphan-detection check (reserved ride is in terminal status) MUST be verifiable programmatically (SC-008).

---

## Dependencies *(mandatory)*

- **Internal**:
  - `010-realtime-transportation` (Phase 7) — the ride-completion endpoint (`POST /rides/{id}/complete`) is the trigger that fires commission deduction. Phase 8 extends Phase 7's completion transaction to include the wallet debit steps. Phase 7 must be deployed before Phase 8 commission logic is active.
  - `009-passenger-experience` (Phase 6) — the `bookings` table stores `fare_amount_egp` per booking, which is the input to the commission calculation (FR-006). Booking status transitions (`confirmed → completed`) are performed by Phase 7's cascade; Phase 8 reads the resulting completed bookings to determine commission amounts.
  - `008-route-intelligence` (Phase 5) — the deterministic pricing engine calculates and stores `fuel_cost_egp` and the full fare breakdown on each ride at creation time. Phase 8 reads `ride.fuel_cost_egp` to compute commission amounts and reservations; it does not recalculate fares.
  - `004-ride-management` (Phase 4) — the ride creation endpoint is extended by Phase 8 to add the balance enforcement gate (FR-015). No new endpoint is created; an additional pre-creation check is inserted into the existing ride creation handler.
  - `003-auth-verification` (Phase 3) — Supabase Auth JWTs identify drivers and admin users. Admin role distinction (used for top-up and adjustment endpoints) relies on the role system established in Phase 3.

- **External**:
  - No external payment gateway or financial API is required for MVP. All financial operations are internal ledger entries.

- **Data**:
  - `rides.fuel_cost_egp` and `rides.total_seat_count` — must be populated on all rides (stored by Phase 5 at ride creation). These are the inputs to every commission calculation and reservation in Phase 8.
  - `rides.status`, `rides.driver_id` — referenced by the commission deduction logic to identify the wallet to debit.
  - Admin user role — the Supabase Auth custom claim or role field established in Phase 3 that distinguishes admin users from drivers and passengers.

---

## Out-of-Scope

- **Digital payment gateway** — no Paymob, Fawry, InstaPay, or card payment integration. Passengers pay drivers in cash; drivers top up their platform wallet via offline payment confirmed manually by admin. Digital payments are a Phase 15 (post-competition) feature.
- **Automated commission collection** — the platform does not deduct commission directly from driver cash or any digital payment at ride time. Commission is deducted from the pre-loaded platform wallet only.
- **Passenger-facing financial features** — passengers have no wallet, no balance, no transaction history, and no financial obligation to the platform in this phase.
- **Financial reporting and analytics** — aggregate revenue reports, commission totals by period, payout summaries, and financial dashboards are Phase 11 (admin operations, post-competition) features.
- **Per-driver commission rate customization** — all drivers pay the same platform-wide commission rate for MVP. Tiered or negotiated rates are deferred.
- **Tax calculation and invoicing** — VAT, income tax reporting, or invoice generation are out of scope for MVP.
- **Refunds** — if a ride is cancelled after a passenger paid in cash, any refund is handled offline between the driver and passenger. The platform does not process or record refunds in this phase.
- **Stripe / Paymob driver wallet top-up** — drivers cannot top up their own wallet through a self-service payment flow. Only admin-initiated top-ups are supported.
- **Multi-currency support** — all financial values are in Egyptian Pounds (EGP) only.
- **Ride completion blocking due to insufficient balance** — commission deduction always succeeds on ride completion even if it makes the wallet negative (FR-009). Balance enforcement only gates future ride creation, not current ride completion.
- **Automated negative-balance alerts** — no automatic notification to the driver or admin when a wallet balance drops below the minimum threshold. Balance status is visible in the admin panel.

---

## Technical Considerations

- The commission deduction MUST be executed inside the Phase 7 ride-completion transaction. This means the Phase 8 wallet service's `deduct_commission()` function is called by the Phase 7 `complete_ride()` handler before the transaction commits — it does not listen to a completion event asynchronously. This tight coupling is intentional: atomicity between ride status, booking status, and ledger is a hard requirement (SC-001, SC-003).
- The `driver_wallets.balance_egp` column is a materialized running total — it is updated in sync with each ledger entry rather than computed on every read. This is a deliberate performance trade-off: reads are O(1) against the wallet row; writes must update both the ledger and the wallet balance in the same transaction. Consistency between the materialized balance and the ledger sum MUST be verified by an integrity check (SC-006).
- Row-level locking (`SELECT ... FOR UPDATE`) on `driver_wallets` during commission deduction and ride-creation balance checks is required to prevent race conditions (NFR-004, NFR-008). This is the same locking strategy used by the Phase 7 notification dispatcher for `notification_events`.
- The `driver_ledger_entries` table MUST be created with a migration that grants only `INSERT` and `SELECT` to the application role and revokes `UPDATE` and `DELETE`. Row Level Security MUST additionally prevent drivers from reading other drivers' ledger entries; passengers MUST have no access. Admin reads all entries for their panel queries.
- The platform commission rate (20% of fuel cost) is the **same fixed constant as Phase 5** — not a separate configurable value in Phase 8. Phase 8 reads `ride.fare_breakdown.fuel_cost_egp` (stored by Phase 5 at ride creation) to compute `commission_per_booking = fuel_cost_egp × 0.20 / seat_count`. No environment variable or database lookup for a commission rate is required; the formula is hardcoded to match Phase 5. The `fuel_cost_egp_snapshot` in each ledger entry provides full auditability.
- The balance check and reservation creation (FR-015, FR-021) are inserted as an additional step in the existing Phase 4 ride-creation handler (`ride_service.py`). The handler acquires a row lock on `driver_wallets`, computes available balance, rejects or proceeds, and — on success — inserts the ride and the `CommissionReservation` in the same transaction. This modifies Phase 4 code but is non-breaking for drivers with sufficient available balance.
- The reservation lifecycle (create → convert or release) means three events must trigger wallet updates: ride creation (FR-021), ride completion (FR-005), and ride cancellation (FR-022). Ride completion is handled inside Phase 7's `complete_ride()` transaction. Ride cancellation (Phase 4/Phase 6 scope) must be extended to call `release_reservation()` in the same cancellation transaction. Both are non-breaking extensions of existing handlers.
- `reserved_egp` on `driver_wallets` is a materialized running total kept in sync with `CommissionReservation` inserts and deletes — it is not computed by summing the reservations table on every read. This is the same O(1) read pattern as `balance_egp`. Both fields MUST be updated atomically with their corresponding reservation or ledger operation.
- Decimal arithmetic MUST use Python's `decimal.Decimal` type (not `float`) for all commission calculations. FastAPI / Pydantic schemas for financial amounts MUST use `Decimal` with explicit `max_digits` and `decimal_places` constraints. PostgreSQL columns MUST use `NUMERIC(12, 2)` (not `FLOAT` or `DOUBLE PRECISION`) for all EGP amounts.
- The admin top-up and adjustment endpoints live in the admin application's FastAPI router (`apps/admin` → `services/api`). They MUST be behind the admin authentication middleware established in Phase 3 and MUST NOT be reachable from the main passenger/driver application.

---

## Assumptions

- **Cash-only for MVP**: Passengers pay drivers directly in cash at pickup. The platform makes no attempt to verify or guarantee that the cash payment occurred. The financial system tracks only platform commission, not passenger fares.
- **Commission rate is the Phase 5 fixed constant (20% of fuel cost)**: The platform commission embedded in every fare is `fuel_cost × 0.20`. This is not configurable in Phase 8 — it is the same fixed constant defined in Phase 5's pricing formula. Phase 8 does not introduce a separate commission rate; it deducts the commission component that was already priced into the passenger's fare at ride creation.
- **Ride-specific balance enforcement with reservation**: There is no fixed platform-wide minimum balance. When a driver creates a ride, the system checks their available balance (`balance_egp − reserved_egp`) against the ride's max commission, then immediately reserves that commission. A driver with a small available balance can still create short-distance rides whose commissions fit. The reservation is held until the ride is completed (converted to a real deduction) or cancelled (released with no charge). This prevents any form of over-commitment across simultaneous rides.
- **Fare amount is set at booking creation**: `bookings.fare_amount_egp` is populated when the passenger creates the booking (Phase 5 pricing engine). Phase 8 reads this value as-is; no re-calculation or adjustment at completion time.
- **Admin role is already established**: Phase 3 (auth-verification) defined the admin user role and the mechanism for identifying admin users via Supabase Auth claims. Phase 8 relies on this without modification.
- **Single commission rate per ride**: All bookings on a given ride are charged the same platform commission rate (the platform-wide rate at time of completion). There is no per-seat, per-route, or per-driver rate differentiation for MVP.
- **No self-serve wallet top-up**: Drivers cannot initiate their own wallet top-up through any in-app flow. They contact the platform operators, arrange offline payment, and the admin credits their wallet. This is an intentional MVP simplification.
- **Ledger currency is EGP**: All financial values are denominated in Egyptian Pounds with two decimal places. No multi-currency conversion is needed.
- **Up to 1,000 active drivers at MVP scale**: The wallet and ledger tables are sized for this scale. No sharding, partitioning, or read-replica strategy is required for the competition MVP.
