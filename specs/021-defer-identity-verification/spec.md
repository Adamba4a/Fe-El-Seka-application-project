# Feature Specification: Deferred Identity Verification (Progressive KYC)

**Feature Branch**: `021-defer-identity-verification`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Deferred identity verification (progressive KYC): Users sign up with only email, phone, name, and age (no ID number field, no photo, no documents required at signup). After signup they get immediate access to browse the app — passengers can view/search posted rides, drivers can view the app — without being verified. A persistent 'Verify identity' affordance is shown at all times for unverified users. When an unverified user attempts a gated action (passenger: booking a ride; driver: posting or accepting a ride), the app blocks the action and shows a prompt directing them to verification. Verification itself reuses the existing document submission flow (front ID, back ID, and driver's license for drivers) and existing review/notification pipeline (5 min–2 hour manual review turnaround, decision notification via existing push/email system). Once approved, the user can perform gated actions normally. This replaces the current behavior where phone number, profile photo, and documents are all required immediately after signup before any app access is granted."

## Business Objective *(mandatory)*

Reduce signup drop-off by moving the highest-friction steps — document upload and photo capture — out of the mandatory signup path and into a just-in-time step triggered only when a user actually tries to book, post, or accept a ride. New accounts get immediate, real access to the app (browsing rides, searching, viewing their dashboard) the moment they sign up, while ride-sharing participation (the point where trust actually matters, per the platform's "Trust Before Transportation" principle) stays gated behind identity verification.

**Constitutional Domain**: Authentication / Trust & Community

**Affected Applications**: Passenger App / Driver App (both via the shared `apps/main` frontend). Admin Panel is unaffected except that it will now see accounts sitting in `unverified` status for longer (potentially indefinitely, for users who never book/drive) rather than only transiently.

---

## Clarifications

### Session 2026-08-19

- Q: Should signup collect a raw `age` integer or a `date_of_birth`? → A: Store `date_of_birth` and compute age on demand — stays accurate indefinitely.
- Q: Existing accounts missing a phone number — gate once to collect it, or grandfather entirely? → A: Grandfather entirely — treated exactly like a missing photo, never gated.
- Q: Existing accounts (all of them, since `date_of_birth` is a brand-new field) — exempt permanently, or require providing it once? → A: Exempt permanently — the minimum-age check applies only to new signups going forward.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New user signs up in seconds and starts browsing (Priority: P1)

A new user signs up with just their email, a phone number, their display name, and their date of birth. As soon as that's submitted, they land in the normal app — passengers see the ride search/browse experience, drivers see the app's home — with no document upload, no photo capture, and no waiting screen in between.

**Why this priority**: This is the entire point of the feature. If signup still routes through a mandatory document/photo step before any app access, friction hasn't actually been reduced.

**Independent Test**: Sign up a brand-new email address, provide phone/name/date-of-birth, and confirm the very next screen is the normal browsing experience (search for passengers, home for drivers) — not a document-upload or photo screen.

**Acceptance Scenarios**:

1. **Given** a new user has verified their email and selected a role, **When** they reach the signup-completion step, **Then** they are asked only for phone number, display name, and date of birth — no ID documents, no photo, no ID number.
2. **Given** a new user submits phone, name, and a date of birth meeting the minimum-age threshold, **When** the submission succeeds, **Then** their account is created with verification status "unverified" and they are taken straight into the app (search/browse for passengers, home for drivers).
3. **Given** a new unverified passenger, **When** they browse the app, **Then** they can search for rides and open a ride's detail page exactly as a verified passenger would.
4. **Given** a new unverified driver, **When** they open the app, **Then** they can view the app's normal driver screens (e.g. browsing their own dashboard) without being routed to a verification step first.

---

### User Story 2 - Unverified user is blocked only at the point of commitment (Priority: P1)

An unverified passenger tries to book a ride, or an unverified driver tries to post a new ride or accept a booking request. Instead of silently failing or being blocked earlier in the journey, the app stops them right at that action with a clear message explaining that identity verification is required, and a direct way to start it.

**Why this priority**: This is what makes deferring verification safe — the trust boundary the constitution requires ("verifiable entities before participating in ride-sharing activities") still holds; it just moves to the transaction instead of to signup.

**Independent Test**: As an unverified passenger, attempt to book any open ride and confirm the booking is blocked with a message directing to verification (not a generic error). As an unverified driver, attempt to post a new ride and confirm the same.

**Acceptance Scenarios**:

1. **Given** an unverified passenger is viewing a ride's detail page, **When** they attempt to book it, **Then** the booking is blocked before any booking record is created, and a message is shown explaining that identity verification is required, with a way to start verification.
2. **Given** an unverified driver, **When** they attempt to post a new ride, **Then** the action is blocked with the same kind of message before any ride is created.
3. **Given** an unverified driver, **When** they attempt to accept or confirm a booking request on a ride they posted, **Then** the action is blocked with the same kind of message.
4. **Given** a verified user, **When** they perform any of the above actions, **Then** nothing changes from current behavior — the action proceeds normally.

---

### User Story 3 - Persistent "Verify identity" entry point and document submission (Priority: P2)

At any point after signup, an unverified user can see a persistent, always-visible "Verify identity" affordance and use it to submit their front ID, back ID, and (if a driver) their driver's license. After submitting, they see a "submitted, we'll notify you" confirmation and can keep using the rest of the app while their review is pending.

**Why this priority**: Without a discoverable, self-serve way to start verification, users would only ever encounter it after being blocked — this story makes it something users can act on proactively (e.g. a passenger who knows they'll want to book later).

**Independent Test**: As a freshly-signed-up unverified user, locate the "Verify identity" affordance without having attempted a gated action first, submit front/back ID (and license, if a driver), and confirm a "submitted" confirmation is shown while the rest of the app remains usable.

**Acceptance Scenarios**:

1. **Given** an unverified user is anywhere in the app, **When** they look for it, **Then** a "Verify identity" affordance is visible and reachable from wherever they are.
2. **Given** an unverified passenger opens the verification flow, **When** they submit front and back ID, **Then** their verification status becomes "pending review" and they see a confirmation that review typically takes 5 minutes to 2 hours.
3. **Given** an unverified driver opens the verification flow, **When** they submit front ID, back ID, and driver's license, **Then** their verification status becomes "pending review" with the same confirmation.
4. **Given** a user's verification is "pending review", **When** they browse the rest of the app, **Then** they can still browse freely but gated actions (booking/posting/accepting) remain blocked until a decision is made.
5. **Given** a user's documents are approved, **When** the decision is made, **Then** they receive the existing decision notification (push/email) and gated actions become available without needing to sign in again.
6. **Given** a user's documents are rejected, **When** the decision is made, **Then** they receive the existing rejection notification with a reason, and can resubmit through the same "Verify identity" entry point.

---

### Edge Cases

- What happens if an unverified user's booking/posting attempt is blocked but they had already filled out a form (e.g. selected seats, entered ride details)? The in-progress input should not be lost — the verification prompt is shown as an interrupting step, and the user can return to complete the action after approval.
- What happens to a user who is "pending review" and their documents are approved or rejected while they have the app open? The next gated action they attempt reflects their current status (no stale "unverified" blocking after approval); a passive UI refresh of the persistent affordance is acceptable rather than a hard requirement.
- What happens to a suspended account? Suspension is checked first and blocks all app access, exactly as today — this feature does not change suspension handling.
- What happens to an account that signed up before this feature shipped and is mid-flow in the old required-phone/photo completion gate? They are treated as unverified under the new model: they get full browsing access immediately, with the "Verify identity" affordance available, rather than being stuck on the old completion screen. Any phone number or photo they already provided is kept; if either is still missing, it stays missing and is never gated (grandfathered), same as a new signup's optional photo.
- What happens to an existing account's missing `date_of_birth` (every pre-existing account, since the field is new)? Nothing — it is permanently exempt from the minimum-age check and is never prompted to backfill it.
- What happens if a user has submitted documents but never receives a review decision within the expected window? Out of scope for this feature — covered by the existing review-operations process, unchanged here.
- What happens when an unverified driver tries to view (not act on) their own posted-ride list or incoming booking requests? Viewing is not gated — only the posting/accepting actions are.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Signup MUST collect only email, phone number, display name, and date of birth to complete account creation — no ID number, no profile photo, and no identity documents may be required to complete signup.
- **FR-002**: System MUST compute age from the submitted date of birth at signup, validate it against a minimum age threshold, and reject signups below it with a clear message.
- **FR-003**: Upon successful signup, the account's verification status MUST be set to "unverified" and the user MUST be taken directly into normal app browsing (search for passengers, home for drivers) — no mandatory document/photo step may sit between signup and app access.
- **FR-004**: Unverified users MUST be able to browse freely: passengers can search for rides and view ride detail pages; drivers can view their normal app screens. Browsing MUST NOT be blocked or redirected because of verification status.
- **FR-005**: System MUST display a persistent "Verify identity" affordance to any unverified or pending-review user, visible from anywhere in the app, at all times until they reach "verified" status.
- **FR-006**: System MUST block a passenger from completing a ride booking while their verification status is not "verified", and MUST show a message directing them to the verification flow instead of creating the booking.
- **FR-007**: System MUST block a driver from posting a new ride while their verification status is not "verified", and MUST show a message directing them to the verification flow instead of creating the ride.
- **FR-008**: System MUST block a driver from accepting or confirming a booking request while their verification status is not "verified", and MUST show a message directing them to the verification flow instead of confirming the booking.
- **FR-009**: The "Verify identity" affordance MUST lead to a document-submission flow that collects front ID and back ID for all users, and additionally a driver's license for drivers — reusing the platform's existing document-submission and manual-review pipeline unchanged.
- **FR-010**: Upon document submission, verification status MUST move to "pending review", and the user MUST see confirmation that review typically takes between 5 minutes and 2 hours.
- **FR-011**: System MUST continue to notify users of the verification decision (approval or rejection) via the existing push/email notification pipeline, unchanged by this feature.
- **FR-012**: Upon approval, gated actions (booking, posting, accepting) MUST become available to the user without requiring them to sign out and back in.
- **FR-013**: Upon rejection, the user MUST be able to resubmit documents through the same "Verify identity" entry point, reusing the existing rejection/resubmission flow.
- **FR-014**: Profile photo MUST become fully optional: never required at signup, never required to browse, and never required to perform a gated action. Users MAY add or change a profile photo at any time from their account settings.
- **FR-015**: Suspended accounts MUST continue to be blocked from all app access regardless of verification status, unchanged from current behavior.
- **FR-016**: Existing accounts created under the previous required-phone/photo-at-signup model that are missing a profile photo and/or a phone number MUST NOT be blocked or redirected on account of either missing field once this feature ships — phone number becomes grandfathered exactly like profile photo for pre-existing accounts.
- **FR-017**: The minimum-age (date-of-birth) requirement applies only at new signup. Existing accounts, none of which have a `date_of_birth` on file, MUST NOT be blocked, gated, or prompted to retroactively provide one — they are permanently exempt from this check.

### Key Entities

- **User Profile**: Represents an account holder (passenger or driver). Verification status (`unverified` / `pending_review` / `verified` / `rejected` / `suspended`) now governs only participation actions (booking, posting, accepting), not app access itself. Gains a mandatory `date_of_birth` value collected at signup, from which age is computed on demand (never stored as a static number). Profile photo remains a stored field but is never a gating condition.
- **Verification Submission**: The existing document bundle (front ID, back ID, driver's license for drivers) tied to a profile; unchanged in shape, but now reachable proactively via the persistent "Verify identity" affordance rather than only as a forced first step or a post-rejection resubmission step.
- **Gated Action**: A transaction-time check (not a persisted entity) applied at three points — passenger booking creation, driver ride creation, driver booking acceptance — that requires verification status "verified" to proceed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete signup and reach normal app browsing in under 30 seconds (down from the current flow, which requires document/photo upload first).
- **SC-002**: 100% of unverified users can reach and use ride search / ride browsing without being redirected to a verification or completion screen.
- **SC-003**: 100% of booking, ride-posting, and booking-acceptance attempts by unverified users are blocked before the underlying record is created, with a message directing to verification.
- **SC-004**: The signup completion rate (accounts that finish signup, measured as reaching the browsing screen) increases relative to the pre-change baseline.
- **SC-005**: 100% of approval/rejection decisions continue to trigger the existing notification within the same delivery expectations as today (no regression from this change).

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The gated-action check (verification status lookup at booking/posting/accepting time) MUST add no noticeable latency to those actions beyond the existing performance envelope of the endpoints involved.
- **NFR-002**: Verification-status enforcement for gated actions MUST be authoritative at the backend/API layer, not only in frontend UI — the frontend prompt is a UX convenience, not the sole enforcement point.
- **NFR-003**: Date of birth collected at signup MUST be stored and transmitted under the same PII protections as other profile fields (TLS in transit, standard database access controls).

---

## Dependencies *(mandatory)*

- **Internal**: Depends on the existing Authentication domain (email+OTP/password sign-in, already implemented), the existing verification/document-submission pipeline and manual-review process (front/back ID, driver's license, `pending_review`/`verified`/`rejected` states), and the existing verification-decision notification system (push/email), all of which are reused unchanged.
- **External**: None new.
- **Data**: Requires a new nullable `date_of_birth` field on the profile, collected at signup for new accounts only (existing accounts are permanently exempt, per FR-017, and need no backfill). No other schema changes are required — `verification_status`, document-submission tables, and `profile_photo_path` already exist and are reused.

---

## Out-of-Scope

- Any change to the manual document-review process itself, its turnaround time, or reviewer tooling (admin panel).
- Any change to how documents are stored, validated (file type/size), or the fraud/AI triage pipeline already in place.
- Re-introducing an ID-number field or any other new required signup field beyond phone, name, and date of birth.
- Enforcing phone number verification or uniqueness (unchanged from the existing unverified-plain-text phone model).
- Changing suspension behavior.
- Retroactively notifying existing users about the new flow.

---

## Technical Considerations

- The current architecture gates entire route groups and the app root (`apps/main/src/app/page.tsx`, `(passenger)/layout.tsx`, `middleware.ts`) on `verification_status === "verified"`, redirecting anything less to a mandatory profile-completion screen. This feature removes those blanket access gates and replaces them with targeted checks only at the three gated actions.
- Backend booking/ride-creation endpoints already depend on verified-user guards (e.g. `get_current_verified_passenger`); these become the authoritative enforcement point per NFR-002 and are extended to cover driver ride-posting and booking-acceptance if not already covered.
- The existing document-only submission screen (currently reachable only after rejection) is the natural reuse target for the proactive "Verify identity" entry point, generalized to also serve first-time unverified users rather than only rejected ones.
- Signup must add a `date_of_birth` collection step; the removed profile-photo-required and document-required steps should be deleted from the signup path rather than made conditionally skippable, per the constitutional preference for a single reused screen over duplicated flows.

---

## Assumptions

- Minimum signup age is 18, consistent with standard ride-sharing platform practice; no other age-based rule (e.g. different minimums for drivers vs. passengers) applies unless specified later.
- Date of birth is not itself verified against any document at signup (verification remains ID-document-based, unchanged); it is trusted user input, same trust level as the phone number.
- The existing review turnaround (5 minutes to 2 hours) and notification pipeline are already correctly implemented (per the merged Verification Notifications feature) and need no changes here — this feature only changes when the door to that pipeline is opened.
- "Driver posting a ride" and "driver accepting a booking" are the complete set of driver-side gated actions; any other driver action not explicitly listed (e.g. editing a ride's own details, cancelling) is out of scope for gating decisions in this spec and can be addressed later if needed.
- Existing accounts currently stuck on the old mandatory phone/photo completion screen are migrated forward as "unverified" with full browsing access; no data backfill is required since the fields they may be missing (photo, phone number, and date of birth) are grandfathered and never gated for pre-existing accounts.
