# Feature Specification: Trust & Community

**Feature Branch**: `014-trust-community`

**Created**: 2026-07-29

**Status**: Draft

**Input**: Phase 10 — Trust & Community: mutual post-ride ratings between passengers and drivers, a reporting mechanism for safety concerns, and an admin safety-moderation workflow that acts on reports and rating patterns.

---

## Clarifications

### Session 2026-07-29

- Q: Should ratings be double-blind (hidden from the other party until both have rated or a window passes), immediately visible, or never mutually visible? → A: Double-blind — hidden until both parties have rated, or 14 days after ride completion, whichever comes first (FR-008).
- Q: Does filing a report impose any immediate restriction on the reported user before an admin acts? → A: Soft flag only — the report is visible to admins the moment it's filed (via the existing open-report queue), but the reported user can still ride/book normally until an admin takes explicit action (FR-017).
- Q: What are the default auto-flagging thresholds for the moderation queue (FR-019)? → A: Rating average below 3.0 over the last 10 ratings (minimum 5 ratings received before eligible), OR 3+ reports within a rolling 30-day window; both remain admin-configurable without a deployment.
- Q: Is there a deadline for submitting a rating after ride completion, or can it be rated indefinitely? → A: 14-day cutoff — a booking can be rated up to 14 days after completion, matching FR-008's reveal window; after that, the rating opportunity is gone (FR-011).

---

## Business Objective *(mandatory)*

Close the trust loop the platform has been building toward since Phase 3. Passengers and drivers can already verify their identity, book and complete rides, and receive push notifications about ride events — but once a ride ends, the platform has no memory of how it went. A driver who drives recklessly, a passenger who repeatedly no-shows, or a user who behaves inappropriately leaves no trace admins can act on, and no signal future riders can see. This phase adds three connected capabilities: mutual ratings after every completed ride, a way for either party to report a safety concern, and an admin moderation queue that turns repeated bad signals into account-level action (warning, suspension, reinstatement) using the suspension mechanism already defined in Phase 3's `profiles.verification_status`.

This phase also unblocks the platform's own AI roadmap: the match-learning instrumentation shipped in `013-match-learning-foundation` already defines a `rated` outcome transition and the real-outcome training pipeline's signal-strength hierarchy explicitly ranks "completed + highly rated" above plain completion — neither is usable until ratings exist to produce that signal.

**Constitutional Domain**: Trust & Safety (Principle III — Trust Before Transportation)

**Affected Applications**: Main App (post-ride rating prompt for passengers and drivers, report flow, own-rating visibility), Admin Panel (safety moderation queue), Shared backend (FastAPI).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Mutual Post-Ride Rating (Priority: P1)

Sarah's ride with Ahmed just completed. The next time she opens the app, she sees a prompt: "How was your ride with Ahmed?" She taps 5 stars and adds a short note: "Great driver, right on time." At the same moment, Ahmed sees his own prompt asking him to rate Sarah, and rates her 5 stars as well. Neither can see what the other rated them until both have submitted, or a reasonable waiting window has passed.

**Why this priority**: This is the foundational trust signal the rest of the phase (and the platform's real-outcome AI training pipeline) depends on. Without it, reporting has no context ("reported by whom, after what kind of ride?") and moderation has no baseline signal to act on. It is also independently valuable and shippable on its own — ratings are useful to users the moment they exist, even before reporting or moderation ship.

**Independent Test**: Complete a ride with a confirmed booking between a test passenger and driver account. As the passenger, submit a rating for the driver on that booking. As the driver, submit a rating for the passenger on the same booking. Verify: both ratings are persisted, each tied to the correct booking and direction; each user's aggregate rating updates to include the new score; attempting to submit a second rating for the same booking/direction is rejected; a rating cannot be submitted for a booking that never reached `completed` status.

**Acceptance Scenarios**:

1. **Given** a booking with `status = completed`, **When** either the passenger or the driver on that booking submits a star rating (1-5) and an optional short comment, **Then** the system persists the rating tied to that booking, the rater, and the ratee, and the ratee's aggregate rating is recalculated to include it.
2. **Given** a booking with `status = completed` that the passenger already rated, **When** the passenger attempts to submit another rating for the same booking, **Then** the system rejects the second submission and the original rating is unchanged.
3. **Given** a booking that is `pending`, `confirmed` but not yet completed, or `cancelled`, **When** either party attempts to submit a rating for it, **Then** the system rejects the request — ratings are only accepted for `completed` bookings.
4. **Given** a user who was neither the passenger nor the driver on a given booking, **When** they attempt to submit a rating for it, **Then** the system rejects the request with an authorization error.
5. **Given** a passenger who books through the AI-ranked search results, **When** she rates the ride after completion, **Then** the system records a `rated` transition on the corresponding `match_outcomes` record (per `013-match-learning-foundation`), linking the star rating back to the original ranked match event.
6. **Given** a completed booking where only one party has rated so far, **When** the other party opens their own rating prompt, **Then** they can still submit their rating normally — submission by one party is never blocked, and neither party's score/comment is shown to the other until both have rated or 14 days have passed since ride completion (FR-008).
7. **Given** a user views their own profile, **When** they check their rating, **Then** they see their current aggregate (average) rating and total number of ratings received, but not who gave which individual score.

---

### User Story 2 - Reporting a Safety Concern (Priority: P2)

Midway through a ride, Sarah notices Ahmed is driving unsafely — running red lights, checking his phone. After the ride (or even during it, from the live tracking screen), she opens a "Report a concern" option, selects "Unsafe driving" from a list of categories, and writes a short description of what happened. She receives confirmation that her report was submitted and will be reviewed.

**Why this priority**: Reporting is the mechanism that surfaces safety problems ratings alone might not catch — a driver can drive dangerously and still receive an average star rating if the passenger doesn't connect "rating" with "safety issue." It depends on Story 1 only in that reports reference a ride/booking the reporter actually participated in, not on ratings existing first, so it ships second because it is a smaller, more narrowly scoped addition once the ride/booking relationship is in place.

**Independent Test**: As a passenger with a `confirmed` or `completed` booking on a ride, submit a report against the driver selecting a concern category and description. Verify: the report is persisted with `status = open`, associated with the correct reporter, reported user, and ride/booking; the reporter receives a confirmation; a user attempting to report a ride they were never a party to is rejected; a user attempting to report themselves is rejected.

**Acceptance Scenarios**:

1. **Given** a passenger with a `confirmed` or `completed` booking on a ride, **When** she submits a report against the ride's driver with a concern category and a description, **Then** the system creates a report with `status = open`, tied to the reporter, the reported user, and the ride/booking, and confirms submission to the reporter.
2. **Given** a driver with a ride that has at least one `confirmed` or `completed` booking, **When** he submits a report against one of his passengers, **Then** the same report creation flow applies symmetrically — reporting is available to both passengers and drivers.
3. **Given** a user who was never a passenger or driver on a given ride, **When** they attempt to submit a report referencing that ride, **Then** the system rejects the request.
4. **Given** a user, **When** they attempt to submit a report naming themselves as the reported user, **Then** the system rejects the request.
5. **Given** a report submission, **When** no category is selected or the description is empty, **Then** the system rejects the submission and prompts for the missing field.
6. **Given** a ride still `in_progress`, **When** a confirmed passenger submits a report about an active safety concern (e.g., unsafe driving happening right now), **Then** the report is accepted — reporting is not gated on the ride having completed.
7. **Given** a report has been submitted, **When** the reporter checks their own report history, **Then** they can see the status of reports they filed (open, under review, resolved, dismissed) but not the admin's internal resolution notes.

---

### User Story 3 - Admin Safety Moderation Queue (Priority: P3)

An admin opens the moderation section of the admin panel and sees a queue of open reports, newest first, each showing the category, a short description, the reporter, the reported user, and a link to the ride in question. She also sees users who have been automatically flagged for review because their rolling rating average dropped below a threshold or they accumulated multiple reports in a short window. She reviews one report, decides the driver's account should be suspended, records a reason, and confirms. The driver can no longer create or accept rides. A week later, after the driver appeals through an outside channel and the admin is satisfied, she reinstates the account.

**Why this priority**: Moderation is the payoff of Stories 1 and 2 — reports and low ratings are only as useful as the action admins can take on them. It is P3 because it is meaningful only once there is data (ratings and reports) to review, and because the account-suspension mechanism it uses already exists from Phase 3 (`profiles.verification_status = 'suspended'` and the `admin_audit_logs` action types `suspended`/`reinstated`), so this story is primarily about wiring existing admin infrastructure to a new data source, not building new account-state machinery.

**Independent Test**: As an admin, open the moderation queue and confirm open reports and auto-flagged users appear. Take a "warn" action on one user and confirm it is recorded without changing their account state. Take a "suspend" action on another user and confirm their `verification_status` becomes `suspended`, they can no longer create rides or bookings, and an audit log entry is recorded. Reinstate that user and confirm `verification_status` returns to `verified` and they can resume normal activity.

**Acceptance Scenarios**:

1. **Given** an admin viewing the moderation queue, **When** the queue loads, **Then** it lists all reports with `status = open` or `under_review`, ordered newest-first, each showing category, description, reporter, reported user, and the associated ride.
2. **Given** a user whose rolling average rating (over their most recent N ratings) falls below a configured threshold, or who accumulates more than a configured number of reports within a rolling time window, **When** the threshold is crossed, **Then** the system surfaces that user in the moderation queue as "flagged for review" — this flagging is advisory only and never automatically changes the user's account state.
3. **Given** an open report, **When** an admin marks it `under_review`, **Then** the report's status updates and it remains visible in the queue until resolved or dismissed.
4. **Given** a report an admin has reviewed, **When** she takes a "warn" action with a required reason, **Then** the system records the action in the existing `admin_audit_logs` mechanism against the reported user and marks the report `resolved`; the user's `verification_status` is unchanged.
5. **Given** a report an admin has reviewed, **When** she takes a "suspend" action with a required reason, **Then** the system sets the reported user's `profiles.verification_status = 'suspended'`, records the action in `admin_audit_logs` (`action_type = 'suspended'`), and marks the report `resolved`; a suspended driver can no longer create or be booked into new rides, and a suspended passenger can no longer create new bookings — existing `confirmed` bookings and in-progress rides are unaffected.
6. **Given** a suspended user, **When** an admin reviews their case and reinstates them with a reason, **Then** `profiles.verification_status` returns to `verified`, the action is recorded in `admin_audit_logs` (`action_type = 'reinstated'`), and the user regains the ability to create rides/bookings.
7. **Given** a report an admin determines has no merit, **When** she dismisses it with a reason, **Then** the report's status becomes `dismissed`, no account state changes, and the action is logged.
8. **Given** any moderation action (warn, suspend, reinstate, dismiss), **When** it is recorded, **Then** the affected user receives a notification informing them of the outcome, using the existing notification-event mechanism from `010-realtime-transportation`, without exposing the reporter's identity.
9. **Given** a non-admin user, **When** they attempt to call any moderation endpoint, **Then** the system rejects the request with an authorization error.

---

### Edge Cases

- What happens if a passenger and driver both try to rate the same booking at the exact same moment? Each rating is a distinct row keyed by `(booking_id, rater_id)`; both submissions succeed independently since they represent opposite directions of the same booking.
- What happens if a user's aggregate rating is requested before they have ever received a rating? The system returns a "not yet rated" state (no numeric average) rather than a default of zero, so an unrated new user is not penalized relative to a genuinely low-rated one.
- What happens if a report references a ride that is later deleted or a user account that is later removed? Reports reference rides and users by foreign key with `ON DELETE RESTRICT`-equivalent integrity — the existing platform has no user/ride hard-delete path, so this is not a practical concern at MVP scale, but reports are never silently orphaned.
- What happens if the same user is reported multiple times for the same incident by different parties (e.g., two passengers on the same ride both report the driver for the same event)? Each report is stored independently; the admin queue groups reports by reported user so an admin reviewing one sees the others, but duplicate reports are not auto-merged or deduplicated.
- What happens if an admin suspends a driver who has passengers with `confirmed` bookings on a not-yet-departed ride? The suspension blocks new activity only; already-confirmed bookings and any ride already `in_progress` are not automatically cancelled — that remains a manual admin/driver action outside this phase's scope, and passengers are notified of the driver's suspension so they can decide whether to proceed.
- What happens if a suspended user tries to log in? Authentication itself is unaffected (this reuses the existing Phase 3 `verification_status` gate, not a new auth lock) — they can still view their account and history, but ride-creation and booking-creation actions are blocked, consistent with how `suspended` already behaves for verification-related suspensions.
- What happens if a user submits an extremely long or empty comment on a rating? The star score is mandatory; the comment is optional and capped at a reasonable length (see NFR), with empty comments accepted.
- What happens if the same booking's rating window (once resolved) is queried again after the ratee's account is later suspended for an unrelated reason? The historical rating remains unchanged — moderation actions do not retroactively alter past ratings.
- What happens to a reported user's ability to ride/book while their report sits unreviewed? Nothing changes automatically — filing a report is a soft, informational flag only (FR-017); the reported user keeps full normal access until an admin takes explicit action, which places the burden on prompt admin triage rather than an automatic hold that could itself be abused via false reports.

---

## Requirements *(mandatory)*

### Functional Requirements

**Ratings**

- **FR-001**: The system MUST allow the passenger on a `completed` booking to submit a rating (1-5 stars, required) and an optional short comment for the driver of that ride.
- **FR-002**: The system MUST allow the driver of a ride to submit a rating (1-5 stars, required) and an optional short comment for each passenger whose booking on that ride reached `completed`.
- **FR-003**: The system MUST reject a rating submission for any booking whose status is not `completed`.
- **FR-004**: The system MUST reject a rating submission from any user who was not the passenger or driver party to the referenced booking.
- **FR-005**: The system MUST allow at most one rating per `(booking_id, rater_id)` pair; a second submission for the same direction on the same booking MUST be rejected without altering the original.
- **FR-006**: The system MUST maintain each user's aggregate rating (average star score and total count of ratings received) and expose it via the user's own profile.
- **FR-007**: A rater's individual star score and comment MUST NOT be attributable to a specific rater when viewed by the ratee — the ratee sees their aggregate and, at most, an anonymized list of comments, never "rater X gave you N stars."
- **FR-008**: A rating MUST be double-blind: the score and comment submitted by one party on a booking MUST NOT be visible to the other party until either (a) both parties have submitted their rating for that booking, or (b) 14 days have elapsed since the ride's completion, whichever occurs first.
- **FR-009**: When a rating is submitted for a booking that originated from an AI-ranked search result with a corresponding `match_events` row (per `013-match-learning-foundation`), the system MUST record a `rated` transition on the associated `match_outcomes` record, carrying the star score as part of the outcome payload.
- **FR-010**: A user with no ratings yet MUST be represented as "not yet rated" (no average), distinct from a user whose average is a low numeric score.
- **FR-011**: A rating submission MUST be rejected if more than 14 days have elapsed since the referenced booking's ride reached `completed` status; after this window, the rating opportunity for that direction is permanently closed, consistent with the double-blind reveal cutoff in FR-008.

**Reporting**

- **FR-012**: The system MUST allow a passenger with a `confirmed` or `completed` booking on a ride, or the driver of that ride, to submit a report against the other party, selecting a concern category from a fixed set (e.g., unsafe driving, harassment, no-show, fraud or scam, vehicle mismatch, other) and providing a required text description.
- **FR-013**: The system MUST reject a report submission where the reporter was not a party (passenger or driver) to the referenced ride/booking, or where the reported user is the reporter themselves.
- **FR-014**: The system MUST reject a report submission missing a category or description.
- **FR-015**: Reports MUST be acceptable for rides in `in_progress` or `completed` status — reporting is not gated on ride completion, since safety concerns can arise during an active ride.
- **FR-016**: Each report MUST be created with `status = open` and MUST be visible to the reporter in a personal report-history view showing status only (open, under review, resolved, dismissed), never the admin's internal resolution notes or the outcome taken against the reported user.
- **FR-017**: Filing a report MUST NOT, by itself, impose any restriction on the reported user's ability to create rides or bookings. The report appearing in the admin moderation queue (FR-018) with `status = open` is a purely informational flag for admin awareness; any restriction on the reported user requires an explicit admin action (FR-021 through FR-022).

**Safety Moderation**

- **FR-018**: The system MUST provide an admin-only moderation queue listing all reports with `status = open` or `under_review`, ordered newest-first, showing category, description, reporter, reported user, and the associated ride.
- **FR-019**: The system MUST automatically surface a user in the moderation queue as "flagged for review" (without changing their account state) when either (a) their rolling average rating over their most recent 10 ratings falls below 3.0 stars, with at least 5 ratings received before this check applies, or (b) they accumulate 3 or more reports within a rolling 30-day window. These default values (rating floor, minimum rating count, report count, and time window) MUST be admin-configurable without a code deployment.
- **FR-020**: An admin MUST be able to transition a report's status to `under_review`.
- **FR-021**: An admin MUST be able to resolve a report by taking one of the following actions, each requiring a reason: **warn** (logged only, no account state change), **suspend** (sets `profiles.verification_status = 'suspended'`), or **dismiss** (no action, report closed as unfounded).
- **FR-022**: An admin MUST be able to reinstate a previously suspended user, setting `profiles.verification_status` back to `verified` and requiring a reason.
- **FR-023**: Every moderation action (warn, suspend, reinstate, dismiss) MUST be recorded in the existing `admin_audit_logs` mechanism, reusing its established `action_type` values (`suspended`, `reinstated`) introduced in `003-auth-verification`, extended with a `warned` value for the warn action.
- **FR-024**: A suspended user MUST be blocked from creating new rides (if a driver) or new bookings (if a passenger); existing `confirmed` bookings and rides already `in_progress` are unaffected by the suspension.
- **FR-025**: When a moderation action is taken, the system MUST notify the affected user of the outcome via the existing notification-event mechanism (`010-realtime-transportation`), without revealing the identity of the reporter.
- **FR-026**: Only authenticated users with the `admin` role MUST be able to access moderation endpoints; all other callers MUST receive an authorization error.

### Key Entities

- **Rating**: A single star score (1-5) and optional short comment given by one party of a completed booking to the other. Attributes: booking reference; ride reference; rater; ratee; rater's role (passenger or driver) at time of rating; star score; optional comment; created timestamp; a derived/computed reveal state (visible to the other party once both have rated or 14 days have elapsed per FR-008 — not necessarily a stored column). Unique per `(booking, rater)`.

- **Report**: A safety or conduct concern raised by one party of a ride against the other. Attributes: reporter; reported user; ride reference; booking reference; category (fixed set); description; status (open / under review / resolved / dismissed); resolution action taken (warn / suspend / dismiss, when resolved); resolution reason; resolved-by admin reference; created and resolved timestamps.

- **Moderation Action (extension of existing `admin_audit_logs`)**: No new table — this phase extends the `action_type` values already used for verification moderation (`003-auth-verification`) with a `warned` value, and adds an optional report reference so a moderation action can be traced back to the report(s) that triggered it, alongside the National-ID-verification actions the table already records.

- **Profile (extended usage, no schema change)**: `verification_status = 'suspended'`/`'verified'` — this value already exists (`003-auth-verification`); this phase is a new *trigger path* into an existing state, not a new state.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 60% of completed bookings receive a rating from at least one party within 7 days of ride completion, once the feature has been live for a full rating cycle.
- **SC-002**: 100% of rating submissions for non-completed bookings, duplicate directions, or non-party users are rejected without corrupting existing rating data.
- **SC-003**: A user can submit a report in under 60 seconds from opening the report flow to confirmation, requiring no more than a category selection and a short description.
- **SC-004**: 100% of moderation actions (warn, suspend, reinstate, dismiss) are traceable to an admin identity, a reason, and — where applicable — the triggering report, via the audit log.
- **SC-005**: A suspended user is unable to create a new ride or booking on their very next attempt after suspension, with zero exceptions observed in testing.
- **SC-006**: Admins can review and resolve an open report from the moderation queue in under 2 minutes on average, including reading the report and selecting an action.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Rating and report submission endpoints MUST respond within 300ms at p95 under expected load.
- **NFR-002**: Aggregate rating recalculation MUST be reflected in the ratee's profile within 5 seconds of a new rating being submitted.
- **NFR-003**: Rating comments MUST be capped at a reasonable length (e.g., 500 characters) and report descriptions at a longer cap (e.g., 1,000 characters), enforced server-side.
- **NFR-004**: The auto-flagging thresholds (rating floor, report count/window) introduced in FR-019 MUST be adjustable without a code deployment, mirroring the existing `pricing_config`/`ranking_config` singleton-config pattern from prior phases.
- **NFR-005**: All rating and report data MUST be protected by Row Level Security — a rater/reporter can see only their own submissions and history; a ratee/reported user can see only their own aggregate and anonymized comments, never who submitted what; only admins can see raw report contents and reporter identity.
- **NFR-006**: Every moderation action MUST emit a structured log entry (admin identity, action type, target user, reason, duration) consistent with the observability standard established in prior phases.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `003-auth-verification` — the `profiles.verification_status` enum (including the existing `suspended` value) and the `admin_audit_logs` table (including its existing `suspended`/`reinstated` action types) are reused directly rather than reintroduced; this phase is additive to both.
  - `009-passenger-experience` / Phase 6 booking system — ratings and reports are anchored to `bookings` and their `status` field (specifically the `completed` state).
  - `010-realtime-transportation` — the `notification_events` mechanism is reused to inform users of moderation outcomes.
  - `013-match-learning-foundation` — the `rated` value in the `match_outcome_transition` enum and the `match_outcomes`/`match_events` tables are the integration point for FR-009; this phase produces the first real data for that pipeline.

- **Data**:
  - Supabase PostgreSQL — two new tables (ratings, reports) and one enum extension (`admin_audit_logs.action_type` gains `warned`); no changes to existing table shapes beyond the new `warned` enum value.

---

## Out-of-Scope

- **Incorporating ratings into AI match scoring or ranking** — surfacing rating-weighted ranking to passengers is a future extension of `012-ai-application`/`013-match-learning-foundation`, not this phase. This phase only produces the `rated` outcome signal; consuming it in the ranking model is separate work.
- **Automated ML-based abuse or fraud detection** — flagged in the roadmap as a distinct future item (`TBD — fraud-detection`); this phase's auto-flagging (FR-019) is a simple threshold check, not a model.
- **Appeals workflow** — a suspended user contesting a decision happens through an out-of-platform channel (e.g., support email) for this phase; an in-app appeals flow is deferred.
- **Evidence attachments on reports** — reports are text-only (category + description); photo/video evidence upload is deferred.
- **Blocking or muting between individual users** — users cannot prevent a specific other user from booking their rides; account-level suspension via admin moderation is the only enforcement mechanism in this phase.
- **Public-facing rating display on ride search/details cards** — this phase computes and stores aggregate ratings and exposes a user's own rating to themselves; showing a driver's rating to passengers browsing search results is a future presentation-layer extension.
- **Rating or reporting for cancelled bookings** — only `completed` bookings support ratings (FR-003); reports may reference `in_progress` or `completed` rides only (FR-015).

---

## Technical Considerations

- The auto-flagging mechanism (FR-019) follows the same advisory-only, non-auto-deciding philosophy already established for AI identity-verification triage — it surfaces signal to a human admin rather than acting on it directly, consistent with the platform's established pattern of keeping automated systems advisory where account status is at stake.
- Suspension continues to be represented purely via `profiles.verification_status`, avoiding a second, competing "is this account restricted" flag; any future feature checking whether a user can create rides/bookings should continue to gate on this single field.
- The moderation action log should extend the existing `admin_audit_logs` table (add a `warned` action type and an optional report reference) rather than introducing a parallel audit mechanism, keeping a single source of truth for all admin-taken actions across verification and safety moderation.
- Rating aggregate (average + count) should be maintained as a fast-read denormalized value (recalculated on each new rating) rather than computed from the raw ratings table on every profile view, consistent with NFR-002's 5-second freshness target.

---

## Assumptions

- **Two-way rating, not one-way**: Both the passenger and the driver rate each other after a completed booking; this is not a passenger-only or driver-only rating system.
- **Star scale is 1-5**: No half-star or 10-point scale is assumed; this matches common industry convention for lightweight post-transaction ratings.
- **No rating edit window**: A submitted rating is final; there is no "edit within 24 hours" grace period for MVP, keeping the model simple and consistent with the platform's existing immutable-ledger style (financial system, audit logs).
- **Fixed report categories**: A small, fixed enum of report categories (unsafe driving, harassment, no-show, fraud/scam, vehicle mismatch, other) is sufficient for MVP; a free-form category system is not required.
- **Suspension does not cancel existing rides**: Suspending a user blocks new activity only; unwinding already-confirmed bookings or in-progress rides on suspension is an admin judgment call made manually outside this phase's automated scope.
- **English-only moderation UI and notifications**: Consistent with the platform's English-first MVP policy; Arabic/RTL is deferred platform-wide, not specific to this phase.
- **Single-tier admin role**: Any user with `profiles.role = 'admin'` can access the full moderation queue; there is no separate "senior admin" tier with elevated moderation permissions for MVP.
