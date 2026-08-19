# Phase 0 Research: Deferred Identity Verification (Progressive KYC)

All Technical Context fields were resolvable directly from the existing codebase and the clarified spec — no `NEEDS CLARIFICATION` markers remain. This document records the implementation-level decisions made while translating the spec into the plan, each with rationale and rejected alternatives.

## 1. Where to enforce the minimum-age check

**Decision**: Validate `date_of_birth` against the minimum-age threshold in `services/api/app/services/profile_service.py`, at signup time, mirroring the existing `phone_number` regex-validation pattern already in that file. Reject with a 422/400 and a clear message; do not persist an underage signup at all.

**Rationale**: Consistent with the project's existing pattern (`ProfileUpdate.phone_number` validator lives in the Pydantic model, but signup-specific business validation — e.g. uniqueness — lives in the service layer). Age-from-DOB is a business rule ("minimum age to use the platform"), not a shape constraint, so it belongs in the service layer alongside other signup business rules. Frontend performs the same check for instant feedback (UX only, per Constitint's frontend/backend split), but the backend is authoritative.

**Alternatives considered**: A Pydantic field-validator on `ProfileSetup` — rejected because minimum-age is a product policy value that may change, and keeping it in the service layer (next to where other signup policy constants would live) keeps Pydantic models purely structural.

## 2. Deleting vs. repurposing `(auth)/complete-profile`

**Decision**: Delete `apps/main/src/app/(auth)/complete-profile/page.tsx` and its route.

**Rationale**: This page exists today solely to catch accounts with `verification_status` not `unverified`/`rejected` but missing `phone_number` or `profile_photo_path` — an inconsistent state that can only arise from the old required-at-signup flow. Once phone is collected at signup (new default) and photo is fully optional forever, no new account can ever reach this inconsistent state. Per the clarified spec (FR-016/FR-017 and the explicit "grandfather them normally" instruction), existing accounts missing phone are exempted outright rather than funneled through a completion screen — so the page has zero remaining callers. Deleting dead code is preferred over leaving an unreachable route (avoids confusion for future readers about when it fires).

**Alternatives considered**: Repurpose it as the new "Verify identity" entry screen — rejected because `verify-id`/`driver/verify-documents` already serve that exact purpose and are the pages the spec explicitly says to reuse; keeping both would duplicate the same responsibility.

## 3. Persistent "Verify identity" affordance placement

**Decision**: Add the affordance to `TopBar.tsx`, driven by the `profile.verification_status` value `AppShell.tsx` already fetches and passes down (no new API call needed).

**Rationale**: `AppShell` already fetches the full `Profile` object once per app shell mount for both passenger and driver variants, and already conditionally renders a full-screen override for `suspended` — extending the same data flow to render a small persistent badge for `unverified`/`rejected` (rather than a full-screen override) is the minimal, precedented change. `TopBar` is present on every screen inside the shell, satisfying the spec's "always visible" requirement without new layout plumbing.

**Alternatives considered**: A separate polling/context provider for verification status — rejected as unnecessary; the data is already in hand at the right layer.

## 4. Handling 403 `verification_required` at gated actions

**Decision**: Frontend API wrapper functions (`lib/api/bookings.ts`, `lib/api/rides.ts`) catch the existing `{error: "verification_required", message}` shape (already used consistently by the backend guards) and surface a new shared `VerificationRequiredModal` component instead of a generic error toast.

**Rationale**: The error shape is already standardized across the codebase (same pattern as `submission_locked`, which `profile/page.tsx` and `verify-id/page.tsx` already special-case). No backend change is needed — `get_current_verified_passenger`/`get_current_verified_driver` already return exactly this shape today. This is purely a frontend UX improvement layered on an existing, unchanged contract.

**Alternatives considered**: Adding new dedicated exception classes/error codes on the backend — rejected as unnecessary; the existing shape is already sufficiently specific and reused elsewhere.

## 5. `date_of_birth` migration shape

**Decision**: A single additive migration, `ALTER TABLE profiles ADD COLUMN IF NOT EXISTS date_of_birth DATE;` — nullable, no default, no backfill, no CHECK constraint at the DB layer.

**Rationale**: Per FR-017, existing accounts are permanently exempt from ever providing a date of birth, so the column must tolerate `NULL` indefinitely — a DB-level minimum-age CHECK constraint would either need to allow `NULL` (making it toothless) or break for grandfathered rows. Minimum-age validation is enforced once, at signup, in the service layer (see Decision 1); the DB stays a plain nullable date column. This mirrors the style of `20260814000010_add_phone_number_to_profiles.sql`, the most recent precedent for adding a nullable, app-enforced-required column to `profiles`.

**Alternatives considered**: `NOT NULL` with a default sentinel value for legacy rows — rejected as it would fabricate data (a fake birthdate) for real users, which is worse than a `NULL` that the app already knows to treat as "exempt."
