# Feature Specification: Organization-Only Access Gate

**Feature Branch**: `025-org-only-access`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Require every user (new signups and existing accounts) to verify ownership of a company or university email address before they can use any part of the Triplyy app, reusing the domain-verification OTP mechanism already built for Groups (Spec 024)."

## Business Objective *(mandatory)*

Restrict app access to members of verified companies and universities, using ownership of a company/university email address as the platform's trust floor while phone-number verification and mandatory ID verification are not yet in place. This affects both the Passenger and Driver experience in `apps/main`.

**Constitutional Domain**: Authentication / Trust & Community

**Affected Applications**: Passenger App / Driver App (shared `apps/main` frontend). Admin Panel gains visibility into each account's org-verification status but no new admin workflow.

---

## Clarifications

### Session 2026-08-29

- Q: Does an existing confirmed Groups (Spec 024) domain verification satisfy this app-wide gate? → A: Auto-credit — an account with an existing confirmed Groups domain verification is automatically treated as org-verified for this gate; no new OTP required.
- Q: If a domain is later added to the rejection list, does that revoke access for accounts already org-verified on it? → A: Forward-looking only — the rejection blocks new verification attempts; already org-verified accounts on that domain keep their access.
- Q: When is the "email already verified on another account" conflict (FR-010) enforced — before or after the one-time code is confirmed? → A: Confirm-time — the code is sent as normal, and the conflict is surfaced only after the user proves ownership by entering the correct code, to avoid leaking another account's verification status to someone who does not control the inbox.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New user must verify an org email before using the app (Priority: P1)

A brand-new user signs up (email+OTP or Google) and, immediately after account creation, is asked to enter a company or university email address and confirm a one-time code sent to it. They cannot reach any other part of the app — browsing, searching, or their dashboard — until this is done.

**Why this priority**: This is the core of the gate. Without it, new accounts continue entering the app exactly as before, and the pivot's stated goal (org email as the trust mechanism) is not met.

**Independent Test**: Sign up a brand-new account, and confirm that after account creation the very next screen is the org-email verification step — not the normal browsing/home screen — and that no navigation path around it exists.

**Acceptance Scenarios**:

1. **Given** a new user has just completed signup, **When** they land in the app, **Then** they see a non-skippable screen asking for a company or university email address.
2. **Given** a user on that screen enters a qualifying email address, **When** they submit it, **Then** a one-time code is sent to that address and they are prompted to enter it.
3. **Given** a user enters the correct one-time code before it expires, **When** they submit it, **Then** their account is marked org-verified and they land on their normal home/browse screen.
4. **Given** a user enters an incorrect or expired code, **When** they submit it, **Then** they see a clear error and can request a new code without losing their entered email address.
5. **Given** a user attempts to close, refresh, or navigate away from the org-email verification screen before completing it, **When** they return to the app, **Then** they are shown the same screen again with no other part of the app reachable.

---

### User Story 2 - Existing user is gated on next login (Priority: P1)

A user who created their account before this change signs in as usual. Because no account is exempt, they are immediately routed to the same non-skippable org-email verification screen as a new signup, before reaching any other screen — regardless of their existing verification status, ride history, or role.

**Why this priority**: Without retroactively gating existing accounts, the business goal only covers new growth and leaves the entire current user base — the immediate concern driving this pivot — unaddressed.

**Independent Test**: Sign in with an existing, fully-onboarded test account and confirm it is routed to the org-email verification screen before reaching its normal landing screen, with no grace period or dismissible warning shown first.

**Acceptance Scenarios**:

1. **Given** an existing user has never completed org-email verification, **When** they sign in after this feature ships, **Then** they are routed to the org-email verification screen before any other screen, on their very first post-release sign-in.
2. **Given** an existing user completes org-email verification successfully, **When** they sign in again later, **Then** they are not shown the verification screen again and go straight to their normal landing screen.
3. **Given** an existing, ID-verified driver with active ride postings has not completed org-email verification, **When** they sign in, **Then** they are still routed to the gate — ID-verification status does not exempt them.
4. **Given** a suspended account, **When** it signs in, **Then** the existing suspension block takes precedence and the user never reaches the org-email verification screen.

---

### User Story 3 - Personal email domains are rejected (Priority: P2)

A user attempts to verify using a personal email address (e.g. a Gmail or Yahoo account) instead of a company or university one. The system rejects the domain before sending any code, with a message explaining why.

**Why this priority**: Without this check, the gate provides no real trust signal — anyone could "verify" with any inbox they control, defeating the purpose of using org-email ownership as a trust mechanism.

**Independent Test**: Attempt to submit a known personal-provider domain (e.g. `gmail.com`) on the verification screen and confirm it is rejected immediately, with no code sent, while a plausible company/university domain is accepted.

**Acceptance Scenarios**:

1. **Given** a user enters an email address on a known personal-email domain, **When** they submit it, **Then** the system rejects it with a clear message and does not send a one-time code.
2. **Given** a user enters an email address on any domain not on the personal-provider list, **When** they submit it, **Then** the system accepts it and proceeds to send a one-time code (no separate company/university whitelist check).
3. **Given** an admin identifies a domain being abused to bypass the gate's intent (e.g. a disposable-email service), **When** they add it to the rejection list, **Then** subsequent verification attempts using that domain are rejected the same way as a personal-provider domain.

---

### Edge Cases

- What happens if a user's chosen org email is already verified and attached to another account (e.g. a shared department inbox)? The system must prevent the same verified email address from being actively attached to more than one account at a time.
- What happens if the one-time code email fails to send (delivery failure, provider outage)? The user must see a clear error and be able to retry, and must not be left on a screen that looks successful without a code actually being sent.
- What happens if a user has no company/university email at all? They remain permanently blocked from the app; this specification defines no exception or manual-override path.
- What happens to a user mid-way through an active booking or an in-progress ride when this feature ships? Their next sign-in is still gated like any other existing account — this specification does not carve out an exception for in-progress activity, since the gate is checked at sign-in, not mid-session.
- What happens if a user abandons the verification screen with an unconfirmed code and returns later? Their prior, unconfirmed attempt is not treated as valid; they must complete a fresh code request and confirmation if the previous code has expired.
- What happens if a user changes jobs/schools and their org email stops working later? This specification does not require periodic re-verification after the initial pass — see Out-of-Scope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST require every user — new signups and existing accounts alike — to verify ownership of a company or university email address before accessing any part of the app beyond the verification step itself.
- **FR-002**: System MUST present the org-email verification step immediately after signup completes for new users, and immediately after sign-in (before any other screen) for existing users who have not yet completed it.
- **FR-003**: The org-email verification step MUST NOT offer any way to skip, dismiss, or bypass it.
- **FR-004**: System MUST reject email addresses on a maintained list of known personal-email-provider domains (e.g. gmail.com, yahoo.com, outlook.com) without sending a one-time code, and MUST show the user a clear reason for the rejection.
- **FR-005**: System MUST accept any email domain not on the rejection list as a valid company/university email, without requiring the domain to appear on any pre-approved allowlist.
- **FR-006**: System MUST allow an admin to add a domain to the rejection list after launch (e.g. one found to be facilitating gate bypass), and rejections MUST apply to all subsequent verification attempts using that domain; adding a domain to the rejection list MUST NOT revoke org-verified status already granted to accounts verified on that domain before the rejection was added.
- **FR-007**: System MUST send a time-limited one-time verification code to the submitted org email address and require the user to enter it correctly before marking the account as org-verified.
- **FR-008**: System MUST allow a user to request a new one-time code if the previous one expired or was not received, subject to the platform's existing OTP rate-limiting behavior.
- **FR-009**: System MUST persist an account's org-verified status (and the verified email/domain) so the user is not asked to re-verify on subsequent sign-ins once completed.
- **FR-010**: System MUST prevent an email address that is already actively org-verified on one account from being used to complete org-verification on a second account; this conflict MUST be surfaced only after the second account's user enters a correct one-time code (proving inbox ownership), not at the point they merely submit the email address, so verification status is never revealed to someone who has not proven they control the inbox.
- **FR-011**: System MUST apply the org-email verification requirement identically to both passenger and driver roles.
- **FR-012**: System MUST check the account-suspension status before the org-email gate, so a suspended account is blocked by the existing suspension mechanism rather than being routed to the verification screen.
- **FR-013**: System MUST apply the org-email gate independently of the account's National ID identity-verification status (Spec 021) — an account may be org-verified without being ID-verified, and vice versa; gated actions that already require ID verification (e.g. booking, posting a ride) continue to require it separately.
- **FR-014**: System MUST NOT treat the org-email gate as satisfied by the account's login/sign-in email address — the org email verified for this gate is independent of, and may differ from, the email used to sign in.
- **FR-015**: System MUST automatically treat an account as org-verified for this gate, without requiring a new one-time code, if that account already has a confirmed domain verification from the existing Groups feature (Spec 024).

### Key Entities

- **Org Email Verification**: Represents one user's attempt to prove ownership of a company/university email address — the submitted email, its domain, the one-time code (never stored in plain form), an expiry time, and whether it has been confirmed. An account's current org-verified status is derived from having at least one confirmed, still-active verification.
- **Domain Rejection List**: The maintained set of domains (starting with known personal-email providers) that are never accepted for org-email verification, extendable by an admin.
- **User Profile**: Gains a derived org-verified status (and the associated verified email/domain) that gates all app access beyond the verification screen, independent of its existing identity-verification status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new signups reach the org-email verification screen immediately after account creation, before any other screen.
- **SC-002**: 100% of existing accounts that have not completed org-email verification are routed to the verification screen on their first sign-in after this feature ships.
- **SC-003**: Zero users can reach ride browsing, search, posting, or booking screens without a confirmed org-email verification on file.
- **SC-004**: Users with a valid company/university email can complete verification (submit email, receive code, confirm code) in under 2 minutes under normal email delivery conditions.
- **SC-005**: 100% of submission attempts using a known personal-email-provider domain are rejected before any one-time code is sent.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The org-email verification screen and its sign-in/signup gate check MUST add no noticeable delay to normal app load for users who are already org-verified.
- **NFR-002**: One-time verification codes MUST be stored only in hashed form and MUST expire within a short, fixed window consistent with the platform's existing OTP expiry (5 minutes).
- **NFR-003**: Verification-code request attempts MUST be rate-limited per email address and per account to prevent abuse (spamming an inbox, brute-forcing a code), consistent with the platform's existing OTP rate-limiting behavior.
- **NFR-004**: Org email addresses and domains MUST be transmitted and stored with the same protections already applied to other account PII (TLS in transit, standard database access controls).
- **NFR-005**: Org-email verification attempts (requests, confirmations, rejections) and admin changes to the domain rejection list MUST be traceable and auditable, consistent with the platform's constitutional requirement that verification activities and administrative actions be auditable.

---

## Dependencies *(mandatory)*

- **Internal**: Depends on the existing Authentication domain (email+OTP / Google sign-in, already implemented) and reuses the domain-verification OTP mechanism built for Groups (Spec 024) — including its personal-email-domain rejection list — as the underlying verification pattern for this app-wide gate.
- **Internal**: Must coexist with the deferred identity-verification model (Spec 021) without reintroducing a hard ID-verification requirement at signup; the two verification statuses (org-verified, ID-verified) remain independent and are checked at different points.
- **External**: None — no new third-party service; reuses the existing email delivery path used for OTP codes today.
- **Data**: Requires each account to carry a persisted org-verification status, verified email, and verified domain, and requires a persisted, admin-extendable domain rejection list.

---

## Out-of-Scope

- Building a curated allowlist of pre-approved company/university domains — any non-rejected domain is accepted (see FR-005).
- A grace period or transition window for existing users — the gate applies on each account's very next sign-in after release.
- A manual admin exception/appeal path for users without any company or university email — they remain blocked; not addressed by this specification.
- Periodic re-verification of an org email after the initial confirmation (e.g. re-checking if a user later leaves their company/university) — out of scope for this iteration.
- Any change to how National ID identity verification (Spec 021) itself works, or to its independent gating of booking/posting actions.
- Sponsored/company-funded groups, recurring rides, or loyalty points (Specs 026-028) — this specification covers only the access gate they will build on top of.
- Admin-panel workflows beyond exposing the existing org-verification status and domain rejection list for visibility — no new admin UI for managing individual verification records.

---

## Technical Considerations

- Reuses the domain-verification OTP infrastructure introduced for Groups (Spec 024) — the request/confirm code-verification flow and its domain-rejection-list check — rather than building a parallel OTP mechanism, per the constitution's prohibition on duplicating shared functionality (Principle VII).
- This gate must not depend on National ID verification status as a prerequisite, unlike Spec 024's Groups feature, which requires ID verification before a user can even request domain verification — for this app-wide gate, org-email verification must be reachable by brand-new, not-yet-ID-verified accounts (Spec 021 leaves most accounts in an "unverified" ID state well after signup).
- Follows the same "non-skippable full-app gate checked at sign-in" pattern established by Spec 020 (required phone/photo), rather than a per-action gate — apply as a page-level check in `apps/main`, not a rewrite of the shared authentication/login flow.

---

## Assumptions

- The email address verified for this gate is a new, independent field from the account's login/sign-in email — a user's login email and their org email may be the same address or different addresses.
- The existing personal-email-provider rejection list built for Groups (Spec 024) is reused as the starting rejection list for this gate; no separate list is created.
- "Org-verified" is a one-time gate per account: once completed, a user is not asked again on subsequent sign-ins, consistent with how Spec 020's phone/photo completion gate behaves.
- Admins reviewing or extending the domain rejection list already have access to whatever admin surface currently manages Groups' domain blocklist; this specification does not require a new admin UI, only that the mechanism be reachable.
- No production accounts currently share a single verified org email across multiple active accounts; this should be spot-checked before enforcing the one-email-per-account uniqueness constraint (FR-010) against production data.
