# Feature Specification: Required Phone Number & Profile Photo (Email+OTP Only)

**Feature Branch**: `020-required-phone-photo`

**Created**: 2026-08-14

**Status**: Draft

**Input**: User description: "Reverse the just-shipped phone-OTP sign-in feature (spec 019) and replace it with: (1) email+OTP remains the ONLY sign-in/verification method, no SMS, no Twilio, no phone-as-alternate-identifier; (2) phone_number becomes a REQUIRED plain-text field (never SMS-verified) collected during account signup/onboarding, alongside email, for both passenger and driver roles; (3) profile photo becomes REQUIRED (currently optional) at signup, for both roles; (4) existing accounts that already went through signup before this change and are missing phone_number and/or profile_photo must be forced through a non-skippable 'complete your profile' step on their next login before they can use the rest of the app."

## Business Objective *(mandatory)*

Ensure every account carries reliable contact and identity information (a phone number and a profile photo) from the moment it's created, so drivers and passengers can trust who they're matched with and support/ops can reach any user. This reverses the just-shipped Spec 019, which made phone number an alternate sign-in identifier verified via SMS — that approach is abandoned in favor of a simpler, cheaper model: email+OTP stays the only way to sign in, and phone number becomes an unverified but mandatory profile field.

**Constitutional Domain**: Authentication / Trust & Community

**Affected Applications**: Passenger App / Driver App (both via the shared `apps/main` frontend). Admin Panel is unaffected except for viewing the (now-guaranteed-present) phone number and photo on user records.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New user completes signup with phone and photo (Priority: P1)

A new user signs up with email+OTP, picks a role (passenger or driver), and must provide a phone number and a profile photo before they can use the app. They cannot skip either field.

**Why this priority**: This is the core of the feature — without it, new accounts would keep being created without the data the business now requires.

**Independent Test**: Sign up a brand-new email address, verify via OTP, select a role, and confirm the app blocks progress past the profile-completion step until both a phone number and a photo are provided.

**Acceptance Scenarios**:

1. **Given** a new user has verified their email via OTP and selected a role, **When** they reach the profile-completion step, **Then** they see required fields for phone number and profile photo (alongside the existing display name and identity document fields).
2. **Given** a new user is on the profile-completion step, **When** they attempt to submit without a phone number, **Then** the submission is blocked with a clear validation message and no account/profile changes are saved for that field.
3. **Given** a new user is on the profile-completion step, **When** they attempt to submit without a profile photo, **Then** the submission is blocked with a clear validation message.
4. **Given** a new user provides a validly formatted phone number and a valid photo (along with the other already-required fields), **When** they submit, **Then** their profile is saved with all fields and they proceed to the existing verification/review flow.

---

### User Story 2 - Sign-in remains email+OTP only (Priority: P1)

Users continue to sign in exclusively via email address + one-time code sent to that email. There is no phone-based sign-in option anywhere in the product.

**Why this priority**: This is the direct reversal of Spec 019 — without removing the phone sign-in path, the product would confusingly offer two ways to authenticate, one of which (phone/SMS) is no longer desired.

**Independent Test**: Visit the login screen and confirm only email-based sign-in (password or one-time code) is offered; confirm there is no phone-number entry point for authentication anywhere in the login/verification flow.

**Acceptance Scenarios**:

1. **Given** a user is on the login screen, **When** they view the available sign-in methods, **Then** they see only email/password and email+one-time-code options (plus any existing third-party sign-in, e.g. Google) — no phone-number option.
2. **Given** a user requests a one-time code, **When** the system processes the request, **Then** the code is sent only to the user's email address; no SMS is ever sent by the system.

---

### User Story 3 - Existing users are prompted to complete their profile (Priority: P2)

A user who created their account before this change — and therefore may be missing a phone number and/or a profile photo — signs in as usual and is immediately, unavoidably prompted to supply whatever is missing before they can reach any other part of the app.

**Why this priority**: Without this, the business goal (every account has a phone number and photo) would only apply to new signups, leaving a large gap of existing accounts non-compliant indefinitely.

**Independent Test**: Take an existing test account with no phone number or photo on file, sign in, and confirm the user is routed to a completion screen that cannot be dismissed or bypassed until the missing information is provided — after which normal app access resumes.

**Acceptance Scenarios**:

1. **Given** an existing user's profile is missing a phone number, a photo, or both, **When** they sign in, **Then** they are shown a "complete your profile" screen requesting only the missing field(s), before reaching any other screen.
2. **Given** a user is on the "complete your profile" screen, **When** they attempt to navigate away or close the screen without submitting, **Then** they are kept on the screen (no skip option, no way to reach the rest of the app first).
3. **Given** a user completes the missing field(s) and submits successfully, **When** they next open the app, **Then** they are not shown the completion screen again and proceed straight to their normal landing screen.
4. **Given** an existing user's profile already has both a phone number and a photo, **When** they sign in, **Then** they are not shown the completion screen at all.

---

### Edge Cases

- What happens when a user enters a phone number in an invalid format (e.g., too short, contains letters)? The system must reject it with a clear message before submission succeeds, for both the signup flow and the existing-user completion flow.
- What happens if a user's photo upload fails midway (e.g., network error) during signup? The submission must not silently succeed without a photo — the user must see an error and be able to retry.
- What happens to an existing user who is mid-review (`pending_review` verification status) and also missing phone/photo? They are still routed through the completion screen on next sign-in before returning to their pending-review waiting screen — completion is independent of verification status.
- What happens to a suspended account missing phone/photo? Suspension is checked first; a suspended user is blocked from the app regardless of profile completeness, per existing behavior.
- What happens if two users happen to enter the same phone number? Since phone number is no longer a verified unique identifier (unlike the abandoned Spec 019 design), duplicates are permitted — no uniqueness is enforced.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate all users exclusively via email address (password or one-time email code); no phone-number-based sign-in or verification path may exist anywhere in the product.
- **FR-002**: System MUST require every new signup to provide a phone number as part of completing their profile, before the account is usable.
- **FR-003**: System MUST require every new signup to provide a profile photo as part of completing their profile, before the account is usable.
- **FR-004**: System MUST validate that a submitted phone number is in a plausible phone-number format before accepting it; the system MUST NOT send an SMS or otherwise attempt to verify the number's validity or ownership.
- **FR-005**: System MUST persist the phone number as plain profile data (not tied to sign-in/authentication) alongside the existing email address on every profile.
- **FR-006**: System MUST detect, on every sign-in, whether the signed-in user's profile is missing a phone number and/or a profile photo.
- **FR-007**: System MUST redirect any user with a missing phone number and/or missing profile photo to a dedicated completion screen before allowing access to any other part of the app, regardless of how long ago their account was created.
- **FR-008**: The completion screen MUST NOT offer any way to skip, dismiss, or bypass providing the missing field(s).
- **FR-009**: The completion screen MUST only ask for the field(s) that are actually missing (e.g., a user missing only a photo is not re-asked for a phone number they already have on file).
- **FR-010**: System MUST allow a user to view and update their phone number after signup (e.g., from account settings), since no such capability exists today and the completion flow depends on it.
- **FR-011**: System MUST NOT require phone numbers to be unique across accounts.
- **FR-012**: System MUST apply the phone-number and profile-photo requirements identically to both passenger and driver roles.
- **FR-013**: System MUST remove all SMS-provider configuration and phone-based one-time-code request/verify capability that was introduced by the now-superseded Spec 019.

### Key Entities

- **User Profile**: Represents an account holder (passenger or driver). Gains a mandatory-going-forward `phone_number` (plain text, unverified, non-unique) and a mandatory-going-forward profile photo. Existing profiles created before this change may temporarily lack either field until the user completes the new gate.
- **Profile Completion Gate**: A transient state/screen a signed-in user is routed through when their profile is missing required fields; not a persisted entity itself, but its trigger condition (missing phone and/or photo) is derived from the User Profile.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new accounts created after this feature ships have both a phone number and a profile photo on file before reaching any part of the app beyond signup.
- **SC-002**: 100% of sign-in attempts by pre-existing accounts missing a phone number or photo are routed to the completion screen before reaching any other screen.
- **SC-003**: Zero SMS messages are sent by the system after this feature ships (fully replacing the Spec 019 SMS-OTP path).
- **SC-004**: Users can complete the new required fields (phone + photo) in under 1 minute as part of the normal signup flow, consistent with the time already budgeted for the existing profile-completion step.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Profile-completion submissions (phone/photo) MUST respond within the same performance envelope as existing profile-update calls (no new latency budget needed since this reuses existing endpoints).
- **NFR-002**: Phone number data MUST be transmitted and stored with the same protections already applied to other profile PII (TLS in transit, standard database access controls).
- **NFR-003**: The completion-gate check MUST add no noticeable delay to normal sign-in for the common case (photo and phone already present).

---

## Dependencies *(mandatory)*

- **Internal**: Depends on the existing Authentication domain (email+OTP sign-in, already implemented) and the existing profile/verification flow (`(onboarding)/profile` screen, identity document upload) that this feature extends.
- **External**: None — this feature removes an external dependency (Twilio SMS) rather than adding one.
- **Data**: Requires the `profiles.phone_number` column already added by Spec 019's migration (repurposed here as an unverified plain field rather than a verified alternate identifier).

---

## Out-of-Scope

- Re-verifying or validating phone number ownership in any way (no SMS, no call, no third-party lookup) — phone number is trusted, unverified user input.
- Enforcing phone number uniqueness across accounts.
- Any change to email+OTP sign-in itself, password sign-in, or Google sign-in — those remain as they are today.
- Admin panel changes beyond what's needed to display the now-guaranteed phone/photo fields (no new admin workflows).
- Retroactively contacting or notifying existing users in advance that they'll need to complete their profile — the prompt only appears at their next sign-in.

---

## Technical Considerations

- This feature builds on top of the `profiles.phone_number` column and its E.164-style format check introduced by Spec 019's migration, but relaxes the uniqueness and "verified identifier" constraints since phone is no longer a sign-in method.
- The existing onboarding/profile-completion screen already collects required identity documents and an optional photo — this feature extends that same screen rather than introducing a separate step, for both new signups and, in a parallel non-skippable gate screen, existing accounts.
- All SMS-provider (Twilio) configuration, environment variables, and phone-based OTP request/verify code paths introduced by Spec 019 must be fully removed, not just disabled.

---

## Assumptions

- No production accounts currently exist with only a phone number and no email, since Spec 019's phone-OTP sign-in was only ever exercised in local development (never deployed with a funded SMS provider) — this should be verified against the production database before applying any migration that re-tightens `email` to required.
- "Complete your profile" is a one-time gate per missing field: once a user supplies the missing phone number and/or photo, they are not asked again on subsequent sign-ins.
- The existing profile-photo upload mechanism (image type/size validation, storage) from the current optional-photo flow is reused as-is; only its "required" enforcement changes.
