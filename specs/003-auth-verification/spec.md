# Feature Specification: Authentication & Verification

**Feature Branch**: `003-auth-verification`

**Created**: 2026-06-14

**Status**: Draft

**Input**: Phase 3 — Authentication & Verification: Phone OTP, user profiles, National ID manual review, driver/vehicle onboarding, basic admin verification dashboard.

## Business Objective *(mandatory)*

Enable every person who interacts with Fe El Seka to have a verified, trusted identity before participating in any ride activity. This phase establishes the complete trust layer: phone-based authentication, profile creation, identity document verification via admin review, driver-specific document submission, and vehicle registration. No ride can be created or booked until the relevant verification steps are complete.

**Constitutional Domain**: Authentication, Identity Verification

**Affected Applications**: Main App (passenger + driver auth, profiles, ID submission), Admin Panel (verification review dashboard)

---

## Clarifications

### Session 2026-06-14

- Q: When an admin suspends a user, what happens to their currently active authenticated session? → A: Active session tokens are immediately revoked on suspension; the user receives a "your account has been suspended" error on their next request and re-authentication is also blocked while suspended.
- Q: How do admin users authenticate to the admin panel? → A: Email + password via Supabase Auth — a separate credential type from the phone OTP used by passengers and drivers; no SMS required for admin logins.
- Q: Is there a cap on how many times a user can re-submit documents after rejection? → A: Maximum 3 total submissions (1 initial + 2 re-submissions); after the 3rd failure the account is locked from further submissions and the user is shown a message with the platform support email to contact for a manual review.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Phone OTP Registration & Login (Priority: P1)

A new visitor opens the Fe El Seka app for the first time. They enter their Egyptian mobile number, receive a one-time passcode via SMS, and enter it to create a session. On subsequent visits, the same flow logs them back in without a password.

**Why this priority**: All other stories in this phase — and every phase that follows — require an authenticated session. This is the prerequisite for everything.

**Independent Test**: Open the app, enter a valid Egyptian phone number, enter the received OTP, and reach the role-selection screen. The user is authenticated and a session exists. Independently validates that Supabase Auth is wired up and SMS delivery works for Egyptian numbers.

**Acceptance Scenarios**:

1. **Given** an unregistered Egyptian phone number, **When** the user submits it, **Then** an OTP SMS is delivered within 30 seconds and a session is created upon correct entry.
2. **Given** a registered phone number, **When** the user submits it and enters the OTP, **Then** they are logged back in and land on their existing profile home screen.
3. **Given** an incorrect OTP, **When** the user submits it, **Then** an error message is shown and the user may retry; after 3 failed attempts the code is invalidated.
4. **Given** a valid OTP not entered within 5 minutes, **When** the user tries to submit it, **Then** the system rejects it with an expiry message and offers a resend.
5. **Given** a non-Egyptian phone number format, **When** the user submits it, **Then** the system rejects it immediately with a clear format error before any SMS is sent.
6. **Given** a user who requests OTP resend more than 3 times in 15 minutes, **When** they request another resend, **Then** the system rate-limits the request and shows a cooldown message.

---

### User Story 2 — Profile Creation & Role Selection (Priority: P2)

After first login, the user selects whether they are joining as a **Passenger** or a **Driver**, then completes their display name and uploads an optional profile photo. This role choice determines their onboarding path and the features available to them throughout the app.

**Why this priority**: Role and profile data are required before verification or ride activity. Without a role, the system cannot route the user to the correct onboarding flow.

**Independent Test**: Complete OTP login, select "Driver" role, enter a display name, and submit. Verify the driver onboarding screens become visible and the passenger ride-search screens are not the default entry point.

**Acceptance Scenarios**:

1. **Given** a first-time logged-in user, **When** they land on the role-selection screen, **Then** they see exactly two choices — Passenger and Driver — with brief descriptions of each.
2. **Given** a user who selects "Passenger" and enters their name, **When** they submit, **Then** a passenger profile is created and they land on the ride-search home screen.
3. **Given** a user who selects "Driver" and enters their name, **When** they submit, **Then** a driver profile is created with verification status `pending_documents` and they are directed to the driver onboarding flow.
4. **Given** a user who has already completed role selection, **When** they log in again, **Then** they bypass role selection and land directly on their role-appropriate home screen.
5. **Given** a user who uploads a profile photo, **When** it is submitted, **Then** only JPEG or PNG files under 5 MB are accepted; other formats or sizes display a clear rejection message.

---

### User Story 3 — Passenger National ID Submission & Admin Review (Priority: P3)

A passenger who wants to book rides must first verify their identity by uploading clear photos of the front and back of their Egyptian National ID card. An admin reviews the submission in the admin dashboard and either approves or rejects it with a reason. The passenger's booking eligibility is gated on approval.

**Why this priority**: Passenger verification is required before booking (Phase 6). This story must be complete before the booking system is built.

**Independent Test**: Log in as a passenger, upload two ID photos (front and back), submit. Log in to the admin dashboard, find the submission, approve it. Verify the passenger's status changes to `verified` and the submission is removed from the pending queue.

**Acceptance Scenarios**:

1. **Given** an unverified passenger, **When** they navigate to their profile, **Then** they see a "Verify your identity" prompt with upload slots for front and back ID photos.
2. **Given** a passenger who uploads both ID photos, **When** they submit, **Then** their verification status becomes `pending_review` and they see a "Under review" message.
3. **Given** a pending submission in the admin dashboard, **When** the admin approves it, **Then** the passenger's status becomes `verified` and the submission moves to the approved history.
4. **Given** a pending submission in the admin dashboard, **When** the admin rejects it with a reason (e.g., "Photo is blurry"), **Then** the passenger's status becomes `rejected`, the reason is stored, and the passenger is notified in-app.
5. **Given** a rejected passenger, **When** they view their profile, **Then** they see the rejection reason and a re-upload option; submitting new photos resets their status to `pending_review`.
6. **Given** an unverified passenger, **When** they attempt to book a ride, **Then** the system blocks the booking and shows a "Verify your identity first" prompt.

---

### User Story 4 — Driver Identity & License Submission (Priority: P4)

A driver must submit their National ID (front and back) and a valid Egyptian driving license photo before they can post or manage rides. An admin reviews all driver documents together and either approves or rejects the driver's account.

**Why this priority**: Driver verification gates ride creation (Phase 4). Must be complete before Phase 4 work begins.

**Independent Test**: Log in as a driver, upload the three required documents (NID front, NID back, driving license), submit. In the admin dashboard, approve the driver. Verify the driver's status changes to `verified` and they can proceed to vehicle registration.

**Acceptance Scenarios**:

1. **Given** a driver who has completed profile setup, **When** they enter the driver onboarding flow, **Then** they see three upload slots: National ID front, National ID back, and Driving License.
2. **Given** a driver who uploads all three documents, **When** they submit, **Then** their verification status becomes `pending_review`.
3. **Given** a pending driver submission, **When** the admin approves it, **Then** the driver's status becomes `verified` and they are routed to vehicle registration.
4. **Given** a pending driver submission, **When** the admin rejects it with a reason, **Then** the driver's status becomes `rejected`, the reason is shown in the driver's app, and they may re-submit.
5. **Given** an unverified driver, **When** they attempt to create a ride, **Then** the system blocks ride creation and shows a "Complete verification first" message.
6. **Given** a driver whose account is suspended by an admin, **When** they attempt any driver action, **Then** all driver-role actions are blocked with a "Account suspended" message.

---

### User Story 5 — Vehicle Registration (Priority: P5)

After a driver's identity is approved, they must register the vehicle they will use for ride-sharing. The vehicle details (plate number, make, model, year, color, and passenger capacity) are stored and associated with that driver's profile.

**Why this priority**: Vehicle data is required for ride creation (Phase 4). Drivers cannot post rides without a registered vehicle.

**Independent Test**: Log in as an approved driver, navigate to vehicle registration, enter all required fields, and submit. Verify the vehicle record is created and linked to the driver, and the driver is shown a "Ready to post rides" confirmation.

**Acceptance Scenarios**:

1. **Given** a verified driver without a registered vehicle, **When** they open the app, **Then** they are prompted to register their vehicle before accessing ride management.
2. **Given** a driver entering vehicle details, **When** they submit a valid plate number, make, model, year (2000–current), color, and seat count (2–7), **Then** the vehicle is saved and associated with their account.
3. **Given** a driver entering an invalid plate number format (not matching Egyptian plate standards), **When** they try to submit, **Then** the system rejects it with a clear format error.
4. **Given** a driver with a registered vehicle, **When** they view their profile, **Then** they can see their vehicle details and update them (except the plate number, which requires admin action to change).
5. **Given** a driver who tries to register more than one vehicle, **When** they attempt a second registration, **Then** the system informs them that only one vehicle is supported per account for the current version.

---

### User Story 6 — Admin Verification Dashboard (Priority: P6)

An admin logs into the admin panel and sees a queue of pending identity verification submissions (both passenger and driver). They can view the uploaded documents, approve or reject with a reason, and track the history of all processed submissions.

**Why this priority**: Without the admin review tool, no user can ever become verified. This is the operational backbone of the entire verification system.

**Independent Test**: Submit a verification request as a test passenger, then log into the admin panel and find the request in the pending queue. Approve it. Verify the queue length decreases by one and the approval is logged in the history.

**Acceptance Scenarios**:

1. **Given** the admin dashboard is open, **When** an admin views the verification queue, **Then** they see all pending submissions ordered by submission time (oldest first), separated into Passenger and Driver sections.
2. **Given** a pending submission, **When** the admin clicks it, **Then** they can view the uploaded photos at readable size and see the user's name and phone number.
3. **Given** an admin viewing a submission, **When** they click "Approve", **Then** the user's status is updated immediately, the submission is removed from the queue, and the action is logged with the admin's ID and timestamp.
4. **Given** an admin viewing a submission, **When** they click "Reject" without entering a reason, **Then** the system requires them to provide a rejection reason before submitting.
5. **Given** an admin who has processed submissions, **When** they view the history section, **Then** they see all past approvals and rejections with admin ID, timestamp, and outcome.
6. **Given** an admin reviewing driver documents, **When** there are both passenger and driver queues, **Then** the driver queue is visually distinct and shows all three required documents.
7. **Given** a user who has been locked out after 3 failed submissions, **When** the admin views their profile in the dashboard, **Then** the admin sees a "Unlock for re-submission" action that resets the submission count and allows one additional attempt.

---

### Edge Cases

- What happens if an OTP SMS is never delivered (carrier failure)? User sees a "Didn't receive it?" resend option with a 60-second cooldown.
- What if a user uploads a photo that is too small to read? Admin can reject with reason "Document unreadable — please retake the photo."
- What if the admin rejects a user who has already been approved once? Approval is permanent for MVP — admin must use the suspend action instead.
- What if a driver tries to proceed to vehicle registration before their ID is approved? The vehicle registration screen is locked with a "Awaiting ID approval" state.
- What if two admins act on the same submission simultaneously? The first action wins; the second admin sees a "Already processed" message.
- What if a suspended user has a valid session token in flight when suspension occurs? The token is immediately revoked server-side; the next API call from that token returns a 401 with a "suspended" reason regardless of token expiry time.
- What if a user tries to submit for a 4th time after being locked out? The system shows the support email message and the submission is blocked at both the frontend and backend — no document upload is accepted.
- What if a user contacts support and is unlocked, then fails again? The admin unlock grants exactly one additional attempt; if that also fails the account is locked again and requires another admin unlock.
- What if a user submits the same phone number from two devices simultaneously? Supabase Auth handles session management; only one OTP is valid at a time.

---

## Requirements *(mandatory)*

### Functional Requirements

**Authentication**

- **FR-001**: System MUST accept only Egyptian phone numbers in E.164 format (`+20XXXXXXXXXX`) for authentication.
- **FR-002**: System MUST send an OTP via SMS to the provided phone number within 30 seconds.
- **FR-003**: OTPs MUST expire after 5 minutes; expired OTPs MUST be rejected with a clear error.
- **FR-004**: System MUST invalidate an OTP after 3 failed entry attempts and require a new code.
- **FR-005**: System MUST enforce a rate limit of 3 OTP resend requests per phone number per 15-minute window.
- **FR-006**: System MUST create a new user account on first successful OTP entry; subsequent entries resume the existing session.
- **FR-007**: System MUST maintain authenticated sessions across app restarts using secure persistent tokens.

**Profiles & Role Selection**

- **FR-008**: First-time authenticated users MUST be directed to role selection before accessing any other feature.
- **FR-009**: Users MUST select exactly one role — Passenger or Driver — and this selection is permanent for the current version.
- **FR-010**: All users MUST provide a display name (2–50 characters) as part of profile creation.
- **FR-011**: Profile photo upload is optional; accepted formats are JPEG and PNG only, maximum 5 MB.
- **FR-012**: All profile photos MUST be stored with private access control; direct public URLs MUST NOT be generated.

**Passenger Identity Verification**

- **FR-013**: Passengers MUST be able to upload exactly two documents: National ID front and National ID back.
- **FR-014**: Accepted document photo formats are JPEG and PNG only, maximum 10 MB each.
- **FR-015**: After submission, a passenger's verification status MUST be set to `pending_review`.
- **FR-016**: An admin MUST be able to approve a passenger submission, setting status to `verified`.
- **FR-017**: An admin MUST be able to reject a passenger submission with a mandatory reason; status is set to `rejected`.
- **FR-018**: A rejected passenger MUST be shown the rejection reason and allowed to re-upload and resubmit. Each user is allowed a maximum of 3 total submissions (1 initial + 2 re-submissions). After exhausting all 3 attempts, further submissions are blocked and the user is shown a message with the platform support email address, instructing them to contact the team for a manual review. Only an admin can unlock a submission-locked account.
- **FR-019**: Unverified passengers MUST be blocked from booking rides (enforced at the backend, not only the frontend).

**Driver Identity & License Verification**

- **FR-020**: Drivers MUST upload three documents: National ID front, National ID back, and Driving License.
- **FR-021**: Driver document photo requirements are identical to passenger (JPEG/PNG, max 10 MB each).
- **FR-022**: Admin approval and rejection flows for drivers are identical to passengers (FR-016–FR-018), including the 3-submission cap and support email message after lock-out.
- **FR-023**: Unverified drivers MUST be blocked from creating or managing rides (enforced at the backend).
- **FR-024**: Admins MUST be able to suspend any verified user (driver or passenger), which immediately revokes all active session tokens for that user and blocks re-authentication while the suspension is active; all role-specific actions are blocked from the moment of suspension with no grace period.

**Vehicle Registration**

- **FR-025**: A verified driver MUST register exactly one vehicle before being able to post rides.
- **FR-026**: Required vehicle fields: plate number, make (brand), model, year (2000–current year), color, passenger seat count (2–7 inclusive, excluding driver).
- **FR-027**: Egyptian plate number format validation MUST be enforced (numeric or alphanumeric per Egyptian standard).
- **FR-028**: A driver MAY update vehicle details (color, seat count) after registration; plate number changes require admin action.
- **FR-029**: Only one vehicle may be registered per driver account for this version.

**Admin Verification Dashboard**

- **FR-030**: The admin dashboard MUST display separate queues for pending passenger and pending driver submissions.
- **FR-031**: Submissions MUST be displayed in chronological order (oldest submission first).
- **FR-032**: Each submission view MUST display the user's name, phone number, submission timestamp, and all uploaded documents at readable size.
- **FR-033**: Reject actions MUST require the admin to enter a rejection reason before the action is committed.
- **FR-034**: All admin actions (approve, reject, suspend) MUST be logged with admin identity, timestamp, and target user.
- **FR-035**: The admin dashboard MUST be accessible only to users with the admin role, enforced server-side.
- **FR-037**: When a user's submission is locked after exhausting 3 attempts, the system MUST display a message containing the platform support email address and instructing the user to contact the team for a manual review. The support email address MUST be configurable via a platform setting (not hard-coded).
- **FR-038**: Admins MUST be able to unlock a submission-locked account, resetting the user's submission count to allow one additional attempt.
- **FR-036**: Admin users MUST authenticate via email + password — a separate authentication method from the phone OTP used by passengers and drivers; admin credentials are provisioned by a platform operator and are not self-registerable.

### Key Entities

- **User**: Unique identifier, phone number (unique, E.164), display name, role (`passenger` | `driver` | `admin`), profile photo reference, verification status (`unverified` | `pending_review` | `verified` | `rejected` | `suspended`), account creation timestamp, last login timestamp.

- **VerificationSubmission**: Unique identifier, reference to user, submission type (`passenger_id` | `driver_id_license`), document references (front ID photo, back ID photo, license photo for drivers), status (`pending_review` | `approved` | `rejected`), rejection reason (nullable), reviewer reference (nullable), reviewed timestamp (nullable), submitted timestamp, submission attempt number (1–3; incremented on each re-submission), is_locked flag (set to true when attempt 3 is rejected; cleared only by admin unlock).

- **Vehicle**: Unique identifier, reference to driver user, plate number, make, model, year, color, passenger seat count, active flag, registered timestamp.

- **AdminAuditLog**: Unique identifier, admin user reference, action type (`approved` | `rejected` | `suspended` | `reinstated`), target user reference, reason (nullable), timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can complete OTP registration and reach the role-selection screen in under 2 minutes from opening the app.
- **SC-002**: SMS OTP delivery is confirmed within 30 seconds for 95% of valid Egyptian phone numbers.
- **SC-003**: A passenger or driver can submit their identity documents in under 5 minutes of first login.
- **SC-004**: An admin can review, decide, and action a verification submission in under 3 minutes.
- **SC-005**: 100% of ride creation or booking attempts by unverified users are blocked at the server level.
- **SC-006**: Admin rejection reasons are recorded for 100% of rejected submissions — zero rejections without a stored reason.
- **SC-007**: A driver with an approved identity and registered vehicle can reach the "Ready to post rides" state in under 10 minutes of first app open.
- **SC-008**: All identity document photos are inaccessible via direct public URL; access is only possible through authenticated, server-mediated requests.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Authentication endpoints MUST respond within 500ms at p95 under expected load (≤1,000 concurrent users).
- **NFR-002**: All identity document photos MUST be stored with private access policies; no publicly guessable URL may grant access to any uploaded document.
- **NFR-003**: Authentication session tokens MUST use short-lived access tokens with secure refresh token rotation; tokens MUST NOT be stored in browser localStorage.
- **NFR-004**: All data in transit (OTP delivery, document uploads, API responses) MUST be encrypted via TLS 1.2 or higher.
- **NFR-005**: Admin dashboard actions (approve/reject/suspend) MUST be idempotent — acting on an already-processed submission MUST return a clear error, not silently succeed.
- **NFR-006**: The verification queue MUST render within 2 seconds for queues up to 500 pending submissions.
- **NFR-007**: Document upload endpoints MUST enforce file-type and file-size limits server-side; client-side validation alone is insufficient.
- **NFR-008**: All admin actions MUST be auditable; audit logs MUST be append-only and not deletable by admin users.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `001-platform-foundation` — Supabase project, FastAPI backend, monorepo structure, and both Next.js apps must be operational.
  - `002-ai-foundation` — No direct dependency; AI scoring is consumed in Phase 9, after this phase is complete.

- **External**:
  - Supabase Auth with phone OTP provider configured and an Egyptian SMS gateway integrated.
  - Supabase Storage with at least two private buckets: one for profile photos and one for identity documents.

- **Data**:
  - Supabase PostgreSQL database with UUID extension enabled.
  - Row Level Security (RLS) policies required on all user, document, and vehicle tables.

---

## Out-of-Scope

- Push notification delivery for verification outcomes (SMS/FCM) — covered by Phase 7 (Real-Time).
- Third-party KYC API integration — manual admin review only for MVP.
- Arabic / RTL interface — English-first for MVP; Arabic deferred post-competition.
- Password-based or email-based authentication — phone OTP only.
- Multi-vehicle management per driver — single vehicle per account for MVP.
- Driver license validity checking or expiry tracking — admin reviews visually; no automated validation.
- Passenger license verification — passengers only submit National ID.
- Self-service role switching — role is permanent; changes require a manual admin action outside this spec.
- Admin user management (creating/removing admin accounts) — separate admin-foundation spec.

---

## Technical Considerations

- Authentication MUST use Supabase Auth's phone OTP provider; no custom OTP implementation is permitted (Constitution §Technical Standards).
- Identity document photos MUST be stored in Supabase Storage with private bucket policies; signed URLs with short expiry times MUST be used for admin viewing (Constitution §Data Standards: "National identification data MUST NOT be publicly exposed").
- Verification status enforcement for ride creation and booking MUST be implemented in the FastAPI backend — not exclusively in the frontend (Constitution §Architecture Standards: "Critical business rules MUST NOT exist exclusively in frontend applications").
- The admin dashboard is part of `apps/admin` — admin users authenticate via email + password (not phone OTP); this is a distinct Supabase Auth provider from the consumer app. Admin credentials MUST NOT be shareable with the passenger/driver auth flow (Constitution §Security & Privacy).
- All admin actions MUST be recorded in an append-only audit log (Constitution §Auditability: "Critical platform actions MUST be traceable and auditable").
- Vehicle plate number validation MUST account for Egyptian plate standards (alphanumeric, typically 3 letters + 4 digits or numeric only for older plates).
- RLS policies MUST ensure users can only read their own verification submissions; only admins may read all submissions (Constitution §Data Standards: "Sensitive information MUST be protected and access-controlled").

---

## Assumptions

- Egyptian phone numbers follow the `+20XXXXXXXXXX` format with a 10-digit local number after the country code.
- The Supabase project has SMS delivery configured for Egypt via a compatible SMS gateway (e.g., Twilio, MessageBird, or Vonage with Egyptian carrier coverage).
- Admin accounts are pre-created by a platform operator using Supabase Auth email + password; there is no self-registration path for admin users. Admin credentials are entirely separate from passenger/driver phone OTP accounts.
- A "first login" is defined as the first time a phone number successfully completes OTP entry — role selection is triggered exactly once per phone number.
- Profile photos are displayed at thumbnail size in listings and at moderate resolution in profile views; full-resolution storage is acceptable.
- The admin panel is accessed only on desktop browsers by internal staff; mobile admin experience is not required for MVP.
- Session expiry follows Supabase Auth defaults (access token: 1 hour; refresh token: 60 days with rotation).
