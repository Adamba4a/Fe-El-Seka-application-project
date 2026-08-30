# Feature Specification: Sponsored Groups

**Feature Branch**: `026-sponsored-groups`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Sponsored Groups (feature 026-sponsored-groups) — admin-created premium groups where a company or university, with a funded balance, sponsors free rides for members whose verified email domain matches the group. The company's balance is debited the full seat price per booked seat; the driver's wallet is credited the net amount (seat price minus platform commission), with the commission gap captured automatically as Triplyy's revenue — no separate manual commission step. Sponsored bookings skip the normal cash reservation/prepay-buffer machinery entirely since no cash changes hands up front between rider and driver. Drivers withdraw their earned balance (including sponsored-ride earnings) via a new withdrawal-request flow: driver submits an amount and an external mobile-wallet payout number, an admin manually reviews and sends the money outside the platform, then marks it approved, which debits the driver's wallet — mirroring how top-ups already work today, just reversed. A read-only company dashboard (built into the existing passenger-facing web app, not the admin panel) lets a sponsoring organization's designated contact see sponsored ride activity and remaining funded balance. Departed-employee access is mitigated by existing group owner/admin member-removal capability. Builds on top of the existing Groups feature (024) for group membership and domain verification, and on the existing wallet/commission system (adds a new ledger entry type for sponsored-ride credits distinct from normal cash-ride credits)."

## Business Objective *(mandatory)*

Let organizations (companies, universities) fund free rides for their own verified members as an employee/student benefit, giving Triplyy a B2B revenue channel (funded balances) on top of its existing peer-to-peer commission model, while preserving the platform's commission capture automatically on every sponsored ride.

**Constitutional Domain**: Financial System (extends the existing wallet/commission domain established for cash rides) and Ride Grouping (extends Groups, Spec 024, with a sponsored group variant)

**Affected Applications**: Main App (Passenger experience — booking a sponsored ride; Driver experience — receiving sponsored-ride credit and requesting withdrawals; new Company Dashboard view). Admin Panel gains sponsored-group creation/funding and withdrawal-request review. AI services are not affected by this spec.

---

## Clarifications

### Session 2026-08-30

- Q: When an admin tries to create a sponsored group for a domain that already has a non-sponsored group, what should the system do? → A: Auto-upgrade in place — creation attempt on an existing domain automatically converts that existing group to sponsored status (with the entered funded balance) instead of creating a new record; no separate admin action needed.
- Q: For a ride scoped to a sponsored group, can a domain-verified member choose to pay cash instead of using the sponsorship, or does sponsorship always apply automatically? → A: Always automatic — every booking on a sponsored-group-scoped ride draws from the funded balance with no cash option for that ride; if the balance is insufficient the booking is rejected (FR-008), the member cannot opt to pay cash instead.
- Q: Must a sponsored group's designated dashboard contact already be a verified member of that group (at creation and on reassignment), or can an admin designate someone who hasn't joined yet? → A: Must already be a verified member — the contact is picked from the group's existing domain-verified members at both initial designation and reassignment; an admin cannot name someone who hasn't joined yet.
- Q: Can a driver have more than one pending withdrawal request open at the same time? → A: One pending request at a time — a driver must wait for their current pending request to be approved or rejected before submitting another.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin Creates and Funds a Sponsored Group (Priority: P1)

A platform admin sets up a sponsored group for a company that has agreed to fund free rides for its employees, associating the group with the company's verified email domain and recording an initial funded balance.

**Why this priority**: Nothing else in this feature can happen without a sponsored group and a funded balance existing first. This is the foundation every other story depends on.

**Independent Test**: Can be fully tested by having an admin create a sponsored group tied to a domain and set a funded balance, then confirming the balance is visible on the group's record — delivers standalone value (a funded, addressable sponsorship account) even before any booking or dashboard logic exists.

**Acceptance Scenarios**:

1. **Given** an admin creating a sponsored group, **When** they associate it with a company/university email domain and enter an initial funded balance, **Then** the group exists as a sponsored group with that balance and members join it the same way they join a company/university group today (domain-verified email, per Spec 024).
2. **Given** an existing sponsored group, **When** an admin adds additional funds to its balance, **Then** the group's available balance increases immediately and is reflected on the company dashboard.
3. **Given** a domain already associated with a non-sponsored company/university group (Spec 024), **When** an admin attempts to create a sponsored group for that same domain, **Then** the system automatically upgrades the existing group to sponsored status (applying the entered funded balance to it) rather than creating a new record, and never creates two competing groups for the same domain.

---

### User Story 2 - Member Books a Free Sponsored Ride (Priority: P1)

A domain-verified member of a sponsored group books a seat on a ride scoped to that group. Instead of paying cash, the seat price is deducted from the sponsoring organization's funded balance, and the driver is credited their net earnings immediately — no cash reservation or prepay step involved.

**Why this priority**: This is the entire point of the feature — without free sponsored bookings, a funded group balance has no way to reach members. Depends on User Story 1 (a funded sponsored group must exist).

**Independent Test**: Can be fully tested by having a domain-verified member of a funded sponsored group book a seat on a group-scoped ride, then confirming: the company's balance decreases by the full seat price, the driver's wallet increases by the seat price minus commission, and the booking required no payment step from the passenger.

**Acceptance Scenarios**:

1. **Given** a domain-verified member of a sponsored group with sufficient funded balance, **When** they book a seat on a ride scoped to that group, **Then** the booking is confirmed immediately with no cash payment or reservation step, the group's funded balance is debited the full seat price for that seat, and the driver's wallet is credited the seat price minus the platform's standard commission.
2. **Given** a sponsored group whose funded balance is insufficient to cover a requested booking's full seat price, **When** a member attempts to book, **Then** the booking is rejected with a clear message that the organization's funded balance is insufficient, and no partial debit occurs.
3. **Given** a sponsored ride booking, **When** it completes, **Then** the transaction is recorded as a distinct sponsored-ride credit type in the driver's wallet ledger, separate from normal cash-ride credits, so drivers and admins can distinguish sponsored earnings from cash earnings.
4. **Given** a member of a sponsored group, **When** they book a ride that is NOT scoped to their sponsored group (e.g., a general city-wide ride), **Then** the normal cash payment flow applies — sponsorship only covers rides scoped to the sponsoring group.
5. **Given** a sponsored ride booking that is later cancelled (by either party, under the platform's existing cancellation rules), **When** the cancellation is processed, **Then** the company's funded balance is refunded the debited amount and any driver credit already issued for that seat is reversed, consistent with how cash-ride cancellations reverse charges today.

---

### User Story 3 - Driver Withdraws Earned Balance (Priority: P1)

A driver who has accumulated earnings (from sponsored rides, cash rides, or both) wants to convert their wallet balance into real money. They submit a withdrawal request with an amount and an external mobile-wallet number; an admin reviews it, sends the money outside the platform, and marks the request approved, which debits the driver's wallet.

**Why this priority**: Sponsored-ride earnings are only meaningful to a driver if they can eventually be turned into real money. Without a withdrawal path, drivers earn balance they can never cash out. Depends on User Story 2 producing wallet credits worth withdrawing (though the flow also works for existing cash-ride balances).

**Independent Test**: Can be fully tested by having a driver with a positive available wallet balance submit a withdrawal request for an amount at or below that balance, then having an admin approve it and confirming the wallet balance is debited by the approved amount.

**Acceptance Scenarios**:

1. **Given** a driver with a positive available wallet balance, **When** they submit a withdrawal request specifying an amount and a payout mobile-wallet number, **Then** the request is created in a pending state and the requested amount is not yet debited from their wallet.
2. **Given** a driver whose requested withdrawal amount exceeds their available balance (balance minus any reserved amount), **When** they submit the request, **Then** it is rejected immediately with a clear message, consistent with the platform's existing available-balance check used for commission gating.
3. **Given** a pending withdrawal request, **When** an admin reviews it and marks it approved (after manually sending the funds outside the platform), **Then** the driver's wallet balance is debited by the approved amount and the request is marked as completed.
4. **Given** a pending withdrawal request, **When** an admin rejects it (e.g., invalid payout details), **Then** the request is marked rejected, no wallet debit occurs, and the driver is informed.
5. **Given** a driver, **When** they view their withdrawal request history, **Then** they see the status (pending, approved, rejected) and amount of each past request.

---

### User Story 4 - Company Views Sponsorship Dashboard (Priority: P2)

A designated contact for a sponsoring organization logs in and views a read-only dashboard showing their sponsored group's remaining funded balance and a summary of sponsored ride activity (rides taken, amount spent, member participation).

**Why this priority**: Valuable for sponsor trust and renewal decisions, but the core sponsorship mechanics (funding, booking, driver payout) already deliver the feature's value without it — a dashboard is visibility, not a functional dependency. P2, not P1.

**Independent Test**: Can be fully tested by designating a user as a sponsoring organization's dashboard contact, having several sponsored bookings occur, then confirming that contact's dashboard view shows the correct remaining balance and activity summary while a non-designated member cannot access it.

**Acceptance Scenarios**:

1. **Given** a user designated as a sponsoring organization's dashboard contact, **When** they open the company dashboard, **Then** they see the sponsored group's current remaining funded balance and a summary of sponsored rides taken to date (count and total amount spent).
2. **Given** a sponsored group with recent sponsored bookings, **When** the designated contact views the dashboard, **Then** the activity summary reflects those bookings without needing a manual refresh trigger beyond a normal page load.
3. **Given** a member of a sponsored group who is not the designated dashboard contact, **When** they attempt to access the company dashboard, **Then** access is denied.
4. **Given** the company dashboard, **When** the designated contact views it, **Then** all data is read-only — no controls to add funds, remove members, or otherwise modify the sponsorship exist on this dashboard (those remain admin-only, per User Story 1).

---

### User Story 5 - Remove Departed Member's Sponsored Access (Priority: P2)

A group owner or admin removes a member from a sponsored group (e.g., because the person has left the company), immediately cutting off that person's ability to book further free sponsored rides.

**Why this priority**: Important risk mitigation for sponsors (paying for rides for people no longer affiliated with them) but reuses existing Groups (024) member-removal capability rather than introducing new mechanics — lower implementation risk, hence P2.

**Independent Test**: Can be fully tested by removing a member from a sponsored group and confirming they can no longer book rides scoped to that group, while their already-completed bookings remain unaffected.

**Acceptance Scenarios**:

1. **Given** a member of a sponsored group, **When** a group owner or admin removes them, **Then** they immediately lose the ability to book rides scoped to that sponsored group and can no longer draw on its funded balance.
2. **Given** a removed member's already-completed sponsored bookings, **When** they are reviewed after removal, **Then** those historical transactions remain unaffected and continue to appear in the driver's and company's records.

---

### Edge Cases

- What happens when a sponsored group's funded balance runs out mid-booking-flow due to a race between two members booking simultaneously? (Bookings are debited atomically against the current balance; whichever booking is processed first succeeds, the second sees insufficient balance and is rejected per User Story 2, Scenario 2.)
- What happens when a driver requests a withdrawal larger than their available balance right after a sponsored-ride credit that hasn't fully settled? (The available-balance check uses the same real-time balance-minus-reserved formula the platform already uses for commission gating; no separate settlement delay is introduced for sponsored credits.)
- What happens when an admin tries to reduce a sponsored group's funded balance below what has already been committed via still-active reservations? (Not applicable — sponsored bookings do not use the reservation/prepay-buffer mechanism at all; funded balance is debited directly at booking time, so there is no "committed but unspent" state to protect against.)
- What happens to a company's funded balance if a sponsored ride is cancelled after the driver has already withdrawn the corresponding credited earnings? (The company balance is still refunded per User Story 2 Scenario 5; if the driver's wallet cannot be debited because the balance has already been withdrawn, the shortfall is handled as a negative wallet balance the platform can recover from future earnings — consistent with how the platform already tolerates negative balances for commission enforcement.)
- What happens when a sponsoring organization's designated dashboard contact leaves the organization? (An admin can reassign the dashboard-contact designation to a different member, mirroring how group ownership can be reassigned in Spec 024.)
- What happens when a driver with an already-pending withdrawal request tries to submit another before it's reviewed? (The new submission is rejected with a clear message; the driver must wait until the pending request is approved or rejected, per FR-011.)
- What happens when a withdrawal request's payout mobile-wallet number is invalid or unreachable? (Handled by the admin during manual review — the request can be rejected per User Story 3 Scenario 4, and the driver can submit a corrected request.)
- What happens when a non-sponsored company/university group later wants to become sponsored? (An admin can upgrade it in place per User Story 1 Scenario 3, preserving existing membership.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an admin to create a sponsored group associated with a single verified company/university email domain and an initial funded balance, reusing the existing Groups (024) domain-verification membership mechanism for that group.
- **FR-002**: System MUST allow an admin to add funds to an existing sponsored group's balance at any time, with the increase reflected immediately.
- **FR-003**: System MUST prevent more than one sponsored (or non-sponsored) company/university group from existing for the same verified domain; when an admin attempts to create a sponsored group for a domain that already has a non-sponsored group, the system MUST automatically upgrade that existing group to sponsored status (applying the entered funded balance) instead of creating a new, competing record.
- **FR-004**: System MUST allow a domain-verified member of a sponsored group to book a seat on a ride scoped to that group without any cash payment step, provided the group's funded balance covers the seat's full price. Sponsorship applies automatically to every booking on a sponsored-group-scoped ride — the system MUST NOT offer a cash-payment alternative for that ride.
- **FR-005**: System MUST debit a sponsored group's funded balance by the ride's full seat price for each seat booked under that sponsorship, at the time of booking.
- **FR-006**: System MUST credit the driver's wallet with the seat price minus the platform's standard commission for each sponsored seat booked, using the same commission calculation the platform applies to cash rides.
- **FR-007**: System MUST record each sponsored-ride driver credit as a distinct ledger entry type, separate from cash-ride credits, so sponsored and cash earnings are distinguishable in wallet history.
- **FR-008**: System MUST reject a sponsored booking attempt when the group's funded balance is less than the required seat price, with no partial debit, and MUST NOT fall back to charging the passenger cash.
- **FR-009**: System MUST NOT apply the cash-ride reservation/prepay-buffer mechanism (reservation creation, release, or available-balance-for-commission checks tied to that mechanism) to sponsored bookings, since no cash changes hands up front.
- **FR-010**: System MUST reverse both the company's funded-balance debit and the driver's sponsored-ride credit when a sponsored booking is cancelled, consistent with how cash-ride cancellations are reversed today.
- **FR-011**: System MUST allow a driver to submit a withdrawal request specifying a withdrawal amount and an external mobile-wallet payout number, provided the driver has no other withdrawal request already in a pending state; System MUST reject a new submission while one is pending.
- **FR-012**: System MUST reject a withdrawal request whose amount exceeds the driver's available wallet balance (balance minus reserved amount), using the platform's existing available-balance formula.
- **FR-013**: System MUST hold a submitted withdrawal request in a pending state, without debiting the driver's wallet, until an admin approves or rejects it.
- **FR-014**: System MUST debit the driver's wallet by the approved amount only when an admin marks a withdrawal request approved, and MUST leave the wallet untouched when a request is rejected.
- **FR-015**: System MUST let a driver view the status and amount of their own past and pending withdrawal requests.
- **FR-016**: System MUST let an admin view all pending withdrawal requests platform-wide in order to review and act on them.
- **FR-017**: System MUST provide a read-only company dashboard, accessible only to a designated dashboard contact for a sponsored group, showing the group's current remaining funded balance and a summary of sponsored ride activity (count of rides and total amount spent).
- **FR-018**: System MUST deny company-dashboard access to any user other than the designated dashboard contact for that specific sponsored group, including regular members of the same group.
- **FR-019**: System MUST NOT expose any controls to add funds, modify membership, or otherwise change sponsorship state on the company dashboard — those actions remain admin-only.
- **FR-020**: System MUST let an admin designate and reassign a sponsored group's dashboard contact only to an existing domain-verified member of that group; an admin MUST NOT be able to designate a person who has not yet joined the group.
- **FR-021**: System MUST continue to honor existing Groups (024) member-removal capability for sponsored groups, immediately preventing a removed member from booking further sponsored rides while leaving their already-completed sponsored bookings unaffected.
- **FR-022**: System MUST require organization-email verification (Spec 025) for any user before they can book any ride, including sponsored rides. National ID identity verification (Spec 021) MUST NOT be required for this or any other action (legal constraint) — org-email verification is the sole trust-floor gate.

### Key Entities *(include if feature involves data)*

- **Sponsored Group**: A company/university group (extends the Group entity from Spec 024) that carries a funded balance, available to cover the full seat price of rides its domain-verified members book within it.
- **Sponsored Ride Credit**: A distinct wallet ledger entry type recording a driver's net earnings (seat price minus commission) from a sponsored booking, separate from cash-ride ledger entries.
- **Withdrawal Request**: A driver-submitted request to convert wallet balance into an external payout, with an amount, a payout mobile-wallet number, a status (pending, approved, rejected), and the admin who reviewed it.
- **Dashboard Contact**: The designation of which member of a sponsored group may view that group's read-only company dashboard.
- **Ride (existing entity, extended)**: A ride scoped to a sponsored group may be booked via sponsored-balance debit instead of cash payment.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can create and fund a new sponsored group in under 3 minutes.
- **SC-002**: A domain-verified sponsored-group member can complete a free sponsored booking in no more steps than booking a normal cash ride today, minus the payment step.
- **SC-003**: 100% of sponsored bookings correctly debit the sponsoring organization's balance by the full seat price and credit the driver's wallet with seat price minus commission.
- **SC-004**: 100% of sponsored booking attempts against an insufficiently funded group are rejected with no partial debit.
- **SC-005**: A driver can submit a withdrawal request in under 2 minutes.
- **SC-006**: A sponsoring organization's designated contact can view their remaining funded balance and sponsored-ride activity summary within 2 clicks of logging in.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Sponsored-balance debits and driver-credit issuance MUST happen atomically as part of the booking transaction, so a booking cannot succeed while leaving the two sides of the ledger inconsistent.
- **NFR-002**: The company dashboard MUST return within the same performance envelope as other read-only dashboards already in the platform (interactive, sub-second perceived response under normal load).
- **NFR-003**: Withdrawal request and sponsored-ledger data MUST be protected with the same least-privilege access controls as other financial data on the platform (driver sees only their own; admin sees all; company contact sees only their own group's aggregate).
- **NFR-004**: Withdrawal request review MUST NOT require a full application deployment to operate — it follows the platform's existing admin manual-review pattern already used for wallet top-ups.

---

## Dependencies *(mandatory)*

- **Internal**: Groups domain (Spec 024) — sponsored groups reuse group membership and domain-verified email joining; Ride Booking domain — the existing booking flow must branch to sponsored-balance debit instead of cash payment when a ride is scoped to a funded sponsored group; Wallet & Commission domain (`wallet_service`, `commission_service`) — sponsored credit issuance reuses the existing commission calculation and wallet balance/reserved-balance primitives; Wallet Top-Up domain (Spec 018) — the withdrawal-request flow mirrors its admin manual-review pattern in reverse; Organization-Only Access (Spec 025) — sponsored-group members must also satisfy the platform-wide organization email verification gate.
- **External**: None new — payout to drivers' external mobile wallets (e.g., Vodafone Cash) happens manually outside the platform, as with existing top-ups.
- **Data**: No new external data dependency; uses the platform's existing PostgreSQL database.

---

## Out-of-Scope

- Automated/integrated payment-gateway disbursement of driver withdrawals — payout remains a manual, admin-executed action outside the platform, consistent with how top-ups work today.
- Self-service sponsored-group creation or funding by a company without going through an admin.
- Multiple dashboard contacts per sponsored group, or company-side self-service management of who the contact is — reassignment is admin-only (FR-020).
- Automatic low-balance alerts or renewal reminders to sponsoring organizations — a future enhancement, not required for v1.
- Any change to how non-sponsored (cash) rides, groups, or bookings work — this spec only adds a sponsored variant alongside existing mechanics.

---

## Technical Considerations

- Sponsored booking logic should branch within the existing ride-booking flow (checking whether the ride's group is a funded sponsored group) rather than introducing a parallel booking pipeline, per Principle VI (modular, non-duplicative architecture).
- Sponsored-ride driver credit should reuse `commission_service`'s existing commission calculation so sponsored and cash rides apply identical commission rates, only differing in who pays (company balance vs. rider cash).
- Sponsored bookings must not touch `create_reservation`/`release_reservation`/reservation-linked `check_available_balance` — those exist specifically for the cash-prepay-buffer case, which does not apply here.
- The withdrawal-request table and admin review flow should mirror the existing `wallet_topup_requests` table and review UI structure (reversed direction: debit instead of credit), for implementation consistency and to minimize new admin-UI patterns.
- The company dashboard should live in the existing Main App (already deployed) rather than the Admin Panel (local-only, unde­ployed), per prior architecture decisions, so sponsoring organizations can access it without needing internal tooling access.

---

## Assumptions

- A sponsored group's designated dashboard contact is a single user per group for v1; multi-contact delegation is deferred.
- Withdrawal requests draw from a driver's total wallet balance regardless of whether the underlying earnings came from cash or sponsored rides — the ledger distinguishes credit *source* (FR-007) but does not silo withdrawable funds by source.
- Sponsored group funding is denominated in the platform's existing currency (EGP), with no multi-currency support required.
- A sponsored group's funded balance has no expiration; unspent balance simply persists until spent or the admin adjusts it.
- The company dashboard contact is designated by an admin from the group's existing domain-verified members, either after at least one member has joined the newly-created sponsored group or via later reassignment (FR-020); there is no self-nomination flow for v1. A brand-new sponsored group with zero members has no dashboard contact until an admin assigns one.
- Refunding a cancelled sponsored booking's driver credit may leave a driver's wallet balance negative if funds were already withdrawn; this is treated the same as any other negative-balance recovery case the platform already tolerates for commission enforcement.
