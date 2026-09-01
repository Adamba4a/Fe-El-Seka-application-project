# Feature Specification: Loyalty Points

**Feature Branch**: `028-loyalty-points`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "028-loyalty-points: points system where passengers redeem points for a free ride/discount, drivers redeem points for car-maintenance credit, and both passengers and drivers can redeem points for vouchers. Recommended to generalize the existing car-maintenance savings ledger (0.3 EGP/km distance fee mechanism) rather than building a parallel points system from scratch. Explicitly out of scope for now: Klaxit's 'Guaranteed Ride Home' stickiness feature — skip it. This is the 4th and final spec in the students/employees pivot sequence (025-org-only-access, 026-sponsored-groups, 027-recurring-rides all done and merged)."

## Business Objective *(mandatory)*

Give students and employees a reason to keep choosing Triplyy over one-off alternatives by rewarding repeat use: passengers and drivers both earn loyalty points for riding/driving on the platform and can redeem them for tangible value (free rides, fare discounts, car-maintenance credit, or vouchers), increasing retention and ride frequency within the org-verified user base established by Spec 025.

**Constitutional Domain**: Rewards & Retention (extends the existing Financial System domain's car-maintenance ledger)

**Affected Applications**: Passenger App / Driver App / Admin Panel

---

## Clarifications

### Session 2026-09-01

- Q: Should point-cost thresholds (free-ride, discount, car-maintenance credit, vouchers) be admin-configurable via settings, or fixed constants defined at build time? → A: Admin-configurable via settings.
- Q: Should the passenger free-ride redemption be capped at a maximum fare value, or always cover the full fare regardless of ride length/price? → A: Capped at a configurable maximum fare value; passenger pays any difference above it.
- Q: Should the passenger fare discount be a percentage of the fare, or a fixed EGP amount off the fare? → A: Percentage of the fare.
- Q: Should voucher redemptions be fulfilled instantly/automatically, or always go through the same manual admin-reviewed queue as car-maintenance credit? → A: Instant/automatic for standard vouchers; the manual queue is reserved for car-maintenance credit and any voucher type explicitly flagged as needing manual fulfillment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Passenger earns and redeems points for a ride (Priority: P1)

A passenger completes paid rides over time and automatically accumulates loyalty points. Once they have enough points, they redeem them at booking time for either a fully free ride or a discount off the fare.

**Why this priority**: This is the core retention lever for the largest user group (passengers) and the most direct incentive to keep booking through the platform instead of alternatives.

**Independent Test**: Can be fully tested by completing several paid rides as a passenger, confirming the points balance increases after each completed ride, then booking a new ride and applying points for a free ride or discount, and confirming the fare charged reflects the redemption.

**Acceptance Scenarios**:

1. **Given** a passenger has just completed a paid ride, **When** the ride is marked completed, **Then** their loyalty points balance increases by the amount earned for that ride within a few seconds.
2. **Given** a passenger's points balance meets the free-ride threshold and the ride's fare is at or below the configured maximum free-ride value, **When** they book a new ride and choose to redeem points for a free ride, **Then** the ride is booked at zero fare and their points balance is reduced by the redemption cost.
2a. **Given** a passenger's points balance meets the free-ride threshold but the ride's fare exceeds the configured maximum free-ride value, **When** they redeem points for a free ride, **Then** the redemption covers fare up to that maximum and the passenger pays the remaining difference.
3. **Given** a passenger's points balance is below the free-ride threshold but above the discount threshold, **When** they book a new ride and choose to redeem points for a discount, **Then** the fare is reduced by the configured discount percentage and their points balance is reduced accordingly.
4. **Given** a passenger's points balance is below any redemption threshold, **When** they view redemption options, **Then** the free-ride and discount options are shown as locked/unavailable with the points still needed.
5. **Given** a ride a passenger already earned points for is later cancelled, refunded, or found fraudulent, **When** the cancellation/refund is processed, **Then** the points earned from that ride are reversed from their balance.

---

### User Story 2 - Driver earns points and redeems for car-maintenance credit (Priority: P2)

A driver completes rides and accumulates loyalty points the same way today's car-maintenance savings accumulate (funded by the existing 0.3 EGP/km distance fee), expressed now as points instead of a raw EGP counter. When they have enough points, they redeem them for car-maintenance credit, which an admin fulfills offline exactly as today.

**Why this priority**: Preserves and extends an already-shipped, already-valued driver benefit (car-maintenance savings) without regressing it, while unifying it under the same points system used for passengers and vouchers.

**Independent Test**: Can be fully tested by completing several rides as a driver, confirming the points balance increases proportionally to distance driven, redeeming points for car-maintenance credit once the threshold is reached, and confirming the redemption appears in the admin fulfillment queue exactly like today's car-maintenance rewards queue.

**Acceptance Scenarios**:

1. **Given** a driver completes a ride, **When** the ride's distance fee is settled, **Then** the driver's loyalty points balance increases by an amount proportional to the distance fee, matching the existing 0.3 EGP/km accrual behavior re-expressed in points.
2. **Given** a driver's points balance reaches the car-maintenance redemption threshold, **When** the driver chooses to redeem for car-maintenance credit, **Then** a car-maintenance reward request is created, their points balance is reduced by the redemption cost, and the request appears in the admin's pending fulfillment queue.
3. **Given** an admin fulfills a driver's car-maintenance reward request, **When** they mark it fulfilled, **Then** the driver is notified and the points spent on that redemption are not refunded.
4. **Given** a driver has an in-progress (pending, unfulfilled) car-maintenance redemption, **When** they view their rewards status, **Then** they can see it is pending admin fulfillment.

---

### User Story 3 - Passengers and drivers redeem points for vouchers (Priority: P3)

Both passengers and drivers can browse a shared catalog of vouchers (platform perks/discounts) that admins publish, and redeem their points balance for a voucher of their choice.

**Why this priority**: Adds a flexible, admin-controlled reward option beyond fixed free-ride/discount/car-maintenance rewards, giving the platform a lever to promote specific behaviors (e.g., off-peak ride vouchers) without a code change.

**Independent Test**: Can be fully tested by an admin publishing a voucher to the catalog, a passenger or driver with sufficient points redeeming it, and confirming the voucher appears in their account as redeemed while their points balance decreases by its cost.

**Acceptance Scenarios**:

1. **Given** an admin has published an active voucher available to passengers, **When** a passenger with enough points selects and redeems it, **Then** it is fulfilled instantly (no admin step) unless the voucher is flagged as requiring manual fulfillment, and their points balance is reduced by its point cost.
2. **Given** a voucher is marked driver-only, **When** a passenger views the catalog, **Then** that voucher is not shown to them (and vice versa for passenger-only vouchers).
3. **Given** a voucher has been retired by an admin, **When** a user who already redeemed it (before retirement) views their redeemed vouchers, **Then** it still appears in their redemption history.
4. **Given** two concurrent redemption requests would each spend a user's entire points balance, **When** both are submitted at nearly the same time, **Then** only one succeeds and the other is rejected for insufficient balance (no double-spend).

---

### User Story 4 - Admin manages the loyalty program (Priority: P4)

An admin creates and maintains the voucher catalog (what's redeemable, at what point cost, for whom, instant or manual fulfillment), configures the program's point-cost thresholds and rates (free-ride max fare, discount percentage, car-maintenance threshold, earning rates), and works a fulfillment queue for pending manual redemption requests (car-maintenance credit and any voucher flagged as manual), mirroring the existing car-maintenance rewards queue and wallet top-up/withdrawal review flows.

**Why this priority**: Enables the reward catalog and fulfillment operations the other three stories depend on, but is an internal operations capability rather than a user-facing growth lever, so it ranks behind the passenger- and driver-facing stories.

**Independent Test**: Can be fully tested by an admin creating a voucher, editing its point cost, retiring it, and separately reviewing and fulfilling (or rejecting) a pending redemption request from the operations queue.

**Acceptance Scenarios**:

1. **Given** an admin is on the loyalty program admin screen, **When** they create a new voucher with a description, point cost, target audience (passengers/drivers/both), and fulfillment mode (instant or manual), **Then** it becomes visible to eligible users in the catalog and redeems according to the chosen fulfillment mode.
1a. **Given** an admin is on the loyalty program admin screen, **When** they update a program-wide setting (free-ride max fare, discount percentage, a redemption threshold, or an earning rate), **Then** the new value takes effect immediately without a code deployment.
2. **Given** an admin retires an active voucher, **When** users next view the catalog, **Then** the retired voucher no longer appears as redeemable.
3. **Given** a pending redemption request (car-maintenance or voucher) is in the queue, **When** an admin fulfills it, **Then** its status updates to fulfilled and the requesting user is notified.
4. **Given** a pending redemption request looks fraudulent or invalid, **When** an admin rejects it, **Then** the points spent on that redemption are refunded to the user's balance and the user is notified of the rejection.

---

### Edge Cases

- What happens to a driver's existing `car_maintenance_savings_egp` balance (already accrued in EGP, not yet at the 3000 EGP threshold) at the moment this feature launches? It is converted 1:1 into points toward the equivalent points threshold, preserving the driver's existing progress exactly.
- What happens when a user's points balance is insufficient for the redemption they attempt? The system must block the redemption before any points are deducted and show how many more points are needed.
- How does the system handle a ride refund/cancellation that occurs *after* the points earned from it have already been redeemed (balance can't go negative)? The reversal is capped at the user's current balance and any shortfall is flagged for admin review rather than driving the balance negative.
- What happens when two redemption requests race against the same balance? Only one may succeed; the loser is rejected for insufficient balance at the time it is processed.
- How does the system handle a dual-role user (someone who is both a passenger and a driver)? Passenger-earned and driver-earned points are tracked as separate balances, since they come from different activities and redeem against different catalogs (see Assumptions).
- What happens to a voucher redeemed just before an admin retires it? The redemption already in progress is honored; only new redemption attempts are blocked once retired.
- What happens if an admin rejects a redemption request? The points spent are refunded to the user's balance in full.
- What happens when a passenger tries to redeem points for a free ride on a ride that is fully or partially sponsored (Spec 026) or otherwise already discounted? Points redemption is mutually exclusive with any other active discount/sponsorship — it is not offered on a ride that already carries one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically award loyalty points to a passenger when one of their bookings is marked completed (not for cancelled, no-show, or refunded bookings).
- **FR-002**: System MUST automatically award loyalty points to a driver when a ride they drove is completed and its distance fee is settled, generalizing the existing 0.3 EGP/km car-maintenance-savings accrual into the points system rather than running a separate parallel counter.
- **FR-003**: System MUST maintain a running loyalty points balance per user, tracked separately for their passenger activity and their driver activity when a user has both roles.
- **FR-004**: Passengers MUST be able to redeem points for a free ride once their balance meets the free-ride threshold; the redemption covers fare up to an admin-configured maximum value, with the passenger paying any amount above it.
- **FR-005**: Passengers MUST be able to redeem points for a fare discount, expressed as an admin-configured percentage off the fare, once their balance meets a lower discount threshold.
- **FR-005a**: System MUST NOT offer points redemption (free ride or discount) on a ride that already carries another active discount or sponsorship (e.g., a Spec 026 sponsored-group ride) — the two are mutually exclusive.
- **FR-006**: Drivers MUST be able to redeem points for car-maintenance credit once their balance meets the car-maintenance threshold, preserving the existing offline admin-fulfillment process (pending → fulfilled, no payment gateway).
- **FR-007**: Both passengers and drivers MUST be able to browse an admin-published voucher catalog, filtered to the vouchers eligible for their role, and redeem points for any voucher they can afford; standard vouchers are fulfilled instantly upon redemption, with no admin step.
- **FR-008**: Admins MUST be able to create, edit, and retire voucher catalog entries, each with a description, a point cost, an eligible audience (passengers, drivers, or both), and a flag indicating whether it requires manual fulfillment (default: instant/automatic).
- **FR-008a**: Admins MUST be able to configure, without a code deployment, the point-cost thresholds for the free-ride reward, the discount reward (including its percentage and the free-ride's maximum covered fare), and the car-maintenance credit reward.
- **FR-009**: Admins MUST be able to review, fulfill, or reject pending redemption requests routed to the manual queue (car-maintenance credit, and any voucher explicitly flagged as requiring manual fulfillment) through a single operations queue, mirroring the existing car-maintenance rewards queue.
- **FR-010**: System MUST prevent any redemption that would take a user's points balance negative, rejecting the request instead.
- **FR-011**: System MUST deduct points at the moment a redemption request is submitted (not at fulfillment time), so concurrent redemption attempts cannot double-spend the same balance.
- **FR-012**: System MUST refund the points spent on a redemption request back to the user's balance if an admin rejects that request.
- **FR-013**: System MUST record every points-earning and points-redeeming event as an auditable, immutable ledger entry (who, when, how many points, and why), consistent with the existing car-maintenance-rewards and wallet ledger patterns.
- **FR-014**: System MUST reverse points earned from a ride that is later cancelled, refunded, or found fraudulent, capped at the user's current available balance.
- **FR-015**: System MUST notify a user when a redemption request they submitted is fulfilled or rejected, and when they cross a redemption-eligible threshold, using the existing notification mechanism.
- **FR-016**: Passengers and drivers MUST each be able to view their current points balance and a history of their points-earning and points-redemption transactions within their respective apps.

### Key Entities *(include if feature involves data)*

- **Loyalty Points Balance**: A per-user, per-role (passenger or driver) running points total. Generalizes today's driver-only `car_maintenance_savings_egp` counter into a points value usable by both roles.
- **Points Transaction**: An immutable ledger entry recording one earn or redeem event — amount, direction, timestamp, and the source (a completed ride) or destination (a redemption request) it's tied to.
- **Reward / Voucher Catalog Entry**: An admin-managed, redeemable item with a description, an admin-configurable point cost, an eligible audience (passenger/driver/both), a fulfillment mode (instant/automatic by default, or manual), and an active/retired status. Free-ride (with its configurable max covered fare) and fare-discount (with its configurable percentage) rewards for passengers, and the car-maintenance credit reward for drivers, are catalog entries with fixed system behavior; vouchers are free-form catalog entries admins define.
- **Redemption Request**: A user's request to redeem points for one catalog entry, with a status (pending, fulfilled, rejected). Instant/automatic redemptions resolve to fulfilled immediately; redemptions routed to the manual queue follow today's `car_maintenance_rewards` PENDING/FULFILLED/REJECTED flow, generalized to cover all manually-fulfilled reward types.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A passenger's points balance reflects a just-completed ride within 5 seconds, matching current car-maintenance-accrual responsiveness.
- **SC-002**: Passengers can redeem points for a free ride or discount in 3 taps or fewer from the booking flow.
- **SC-003**: Instant/automatic redemptions (standard vouchers, and free-ride/discount at booking) complete with no perceptible wait; at least 90% of redemption requests routed to the manual queue (car-maintenance credit, manually-flagged vouchers) are fulfilled or rejected by an admin within 48 hours.
- **SC-004**: Zero incidents of a user's points balance going negative or being double-spent, measured over the first 3 months post-launch.
- **SC-005**: Among org-verified users active for at least 30 days, ride frequency for users who have redeemed at least one reward is measurably higher than for users who have never redeemed, within 90 days of launch.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Points balance and transaction history reads MUST return within 500ms at p95 under normal load.
- **NFR-002**: Points balance mutations (earn, redeem, reverse, refund) MUST be atomic and consistent under concurrent requests — no lost updates and no double-spend, even under simultaneous redemption attempts against the same balance.
- **NFR-003**: The voucher catalog MUST support at least 50 concurrently active vouchers without degrading catalog browsing performance.
- **NFR-004**: Points ledger entries MUST be retained indefinitely for audit purposes, consistent with existing financial ledger retention.

---

## Dependencies *(mandatory)*

- **Internal**: Ride/booking completion events (source of passenger and driver earning events); the existing car-maintenance savings ledger and its offline admin-fulfillment workflow, which this feature generalizes rather than duplicates; the existing notification mechanism for earn/redeem alerts; the admin operations panel (Spec 015) for the catalog-management and fulfillment-queue UI; org-email verification (Spec 025) as the underlying trust floor for who is eligible to earn/redeem.
- **External**: None.
- **Data**: Extends the existing driver savings/reward tables into a role-agnostic points ledger and adds a voucher catalog and a generalized redemption-request table.

---

## Out-of-Scope

- Klaxit-style "Guaranteed Ride Home" or any other stickiness feature beyond points earning/redemption — explicitly deferred by product decision.
- Payment-gateway-integrated or cash-purchasable vouchers — v1 vouchers are redeemable with points only.
- External/third-party merchant vouchers — v1 vouchers are platform-issued perks and discounts only, not outside-partner integrations.
- Points transfer or gifting between users.
- Tiered membership levels (e.g., bronze/silver/gold status) — v1 is a single flat points balance per role, not a tier system.
- Redesigning or replacing the underlying ride/booking completion or commission/distance-fee calculation logic — this feature only adds a points layer on top of existing settlement events.

---

## Technical Considerations

- This feature MUST generalize the existing car-maintenance savings ledger (driver-only, EGP-denominated, distance-fee-funded) into a shared points ledger usable by both passenger and driver roles, rather than introducing a second, parallel points/rewards system.
- Redemption fulfillment MUST reuse the existing offline, admin-reviewed PENDING → FULFILLED/REJECTED pattern already proven for car-maintenance rewards and wallet top-up/withdrawal requests — no payment-gateway integration is introduced by this feature.
- Notifications for points thresholds and redemption outcomes MUST reuse the existing notification-events mechanism used elsewhere in the platform.

---

## Assumptions

- Passenger points-earning is proportional to the fare paid on each completed ride; driver points-earning continues to be proportional to distance driven via the existing 0.3 EGP/km distance-fee mechanism, now expressed in points. The exact points-per-EGP and points-per-km conversion rates, all redemption point-cost thresholds, the free-ride's maximum covered fare, and the discount percentage are all admin-configurable business parameters, not fixed in this spec.
- Points do not expire in v1.
- Passenger-earned and driver-earned points are separate balances for dual-role users; there is no cross-role conversion or pooling in v1.
- v1 vouchers are platform-issued (ride discounts, platform perks) rather than external-merchant partnerships.
- The free-ride, fare-discount, and car-maintenance-credit rewards are fixed, system-defined catalog entries (not admin-creatable/deletable like general vouchers), since their behavior is wired into the booking and wallet flows; only their point-cost thresholds are admin-configurable.
