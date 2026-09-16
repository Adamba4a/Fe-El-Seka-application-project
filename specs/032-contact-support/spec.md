# Feature Specification: Contact Support

Created: 2026-09-16. Scope authorized by the user: full feature workflow.

## Business Objective
Let people report signup and in-app problems without requiring an account. Give the team a persistent admin inbox and email notifications at triplyy.info@gmail.com.

Domain: Support. Applications: main passenger/driver app and admin.

## Clarifications and decisions
- Both admin storage and email delivery are required (user decision).
- Recipient is triplyy.info@gmail.com (user decision).
- Use a global dialog so signup progress is preserved when opening/closing support.
- Admins triage open / in_progress / resolved reports; replies happen through email. No chat or attachments.
- Email failure must not lose or reject an already saved report. Retry automatically, display delivery status to admins.
- Submission is public, including users blocked in signup. Email is contact information, not proof of identity; do not associate an account based on a supplied email.

## Functional Requirements
FR-001: Show “Have a problem?” / “عندك مشكلة؟” throughout signup and authenticated main-app pages.
FR-002: Require a valid email (maximum 254 characters) and a trimmed description of 10–5000 characters; accept Arabic and English.
FR-003: Persist a UUID report with contact email, description, locale, creation time, status and email delivery state before acknowledging success.
FR-004: Queue an email to the configured support inbox using the existing delivery infrastructure; escape user content. Retry transient failures and expose exhausted delivery.
FR-005: Provide admin-only paginated listing, status filtering and status changes with an audit trail. Ordinary users and anonymous visitors cannot read reports or change their status.
FR-006: Localize the complete user-facing form, validation and feedback; inherit RTL layout. Preserve draft on failure and prevent repeated submission while pending.
FR-007: Apply database-backed submission limits (3 per contact email per hour and 10 per client IP per hour), serialized across workers. Add a honeypot. Never trust arbitrary forwarded headers.
FR-008: Use a client-generated request UUID to safely retry ambiguous network failures without duplicating reports or exposing existing content.

## Acceptance Criteria
1. From login, OTP, each onboarding screen and signed-in pages, opening/closing support retains the current page and its form data.
2. Valid submission succeeds without authentication and appears in the admin inbox; notification targets the agreed inbox.
3. Invalid email/short/oversized descriptions fail; rate limits return 429; failed submission keeps the draft.
4. Email transport failure leaves the report visible and queued, and retries survive API restart.
5. Anonymous/non-admin listing and updates are rejected. Admin changes retain who/when/old/new status.
6. English and Arabic show translated labels, errors and success states; Arabic uses RTL with LTR email input.
7. Concurrent duplicate request IDs create one report; report content is not returned to public callers.

## Non-Functional Requirements
Mobile-friendly, keyboard-operable modal with focus containment/restoration; bounded inputs and pagination; private database tables with RLS and no browser grants. No report text or email in application logs. Email delivery is at-least-once (a crash after delivery can cause a duplicate notification).

## Dependencies
Existing FastAPI/asyncpg database, Supabase admin authentication, Resend/Mailpit transport, Next.js/next-intl catalogs. Apply the migration before deploying the API. Production email needs the existing valid Resend credentials and verified sender.

## Out of Scope
Attachments, live chat, automatic replies, public ticket lookup, SLA promises, production deployment. App-wide localization gaps outside this feature are recorded in an audit rather than expanding the feature.

## Technical Considerations
Follow actual services/api architecture (the older 004 plan's backend paths are outdated). Support owns its durable email queue because existing ride notifications require a ride ID. No new runtime dependencies required.
