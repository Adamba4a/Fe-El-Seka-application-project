# Phase 0 Research: Groups

All items below were resolved by reading the existing codebase rather than external research — this feature extends established in-repo patterns end to end. No `NEEDS CLARIFICATION` markers remain in the Technical Context.

## 1. Email OTP mechanism for domain verification

**Decision**: Build a small, purpose-specific OTP flow inside `group_service.py` — generate a random 6-digit code, store a salted hash + expiry in the new `domain_verifications` table, send it via the platform's existing transactional-email sender (`notification_service`'s Resend/Mailpit `_send_email` pattern), and verify by hash comparison + expiry check.

**Rationale**: The platform's only existing "email OTP" is Supabase Auth's `sign_in_with_otp` / `verify_otp` (`auth_service.py`), used for **login** — verifying it signs the caller into a session *as that email's identity* and will create a new `auth.users` row for a previously-unseen email. Reusing it for domain verification would either hijack the caller's existing session identity or silently create a duplicate/orphaned auth user for their work/school email — neither is acceptable, since the person is already authenticated under their own primary login email and is only proving *secondary* mailbox control. A self-contained code+hash+expiry table sidesteps this entirely while still reusing the platform's real email-sending infrastructure and matching the UX (6-digit code, timed expiry, rate-limited resend) users already know from login OTP.

**Alternatives considered**:
- Reuse `sb.auth.sign_in_with_otp` — rejected (identity/session hijack risk, described above).
- Supabase "email change" flow (`update_user` with new email) — rejected; that mutates the user's primary login email, which is not the goal (domain verification is additive, not a login-identity change).
- Third-party email-verification API — rejected; out of scope per spec ("no paid third-party KYC/employment-verification integration").

## 2. Configurable blocklist & rate-limit thresholds (NFR-004, NFR-005)

**Decision**: Reuse the existing `platform_settings` key/value table (already used by `verification_service._get_support_email` and `wallet_topup_service._get_vodafone_cash_number`). Add two keys: `group_domain_blocklist` (comma-separated domains, seeded with the six named in the spec) and `group_new_domain_rate_limit` (integer string: max first-time domain registrations per window) plus `group_new_domain_rate_limit_window_minutes`.

**Rationale**: This is the platform's established pattern for admin-tunable values that must not require a redeploy — no new infrastructure needed, and it's consistent with how every other "configurable threshold" already works on this platform.

**Alternatives considered**: New dedicated `group_settings` table — rejected as needless duplication of an existing, working pattern (Principle VII: no duplication of shared functionality). Environment variables — rejected; those require a redeploy, violating NFR-004/005 directly.

## 3. New-domain rate limiting implementation

**Decision**: DB-backed counting query (not in-memory), since the API runs as multiple processes/containers behind Bunny — count rows in `domain_verifications` where `verified_at IS NOT NULL AND is_first_for_domain = true AND created_at > now() - window`, compared against the configured threshold, inside the same transaction that would create a brand-new domain's group.

**Rationale**: `verification_service`'s existing resend-rate-limiter (`auth_service._resend_tracker`) is in-memory and per-process — acceptable there because it's a soft per-user throttle where a slightly-too-generous limit under multi-process skew is low-risk. First-domain-registration throttling is an anti-abuse control (spam org-group creation) where under-counting across processes would materially weaken the control, so a DB-backed count is used instead.

**Alternatives considered**: In-memory counter matching `auth_service` — rejected for the reason above. Redis/external rate-limiter — rejected, no such infrastructure exists on this platform yet and one query against an already-indexed table is sufficient at current scale.

## 4. Group-scoped ride visibility

**Decision**: Add a nullable `group_id UUID REFERENCES groups(id)` column to the existing `rides` table. General-feed search/listing queries (in `candidate_service.py`, `search/router.py`, `rides/router.py`) add `AND group_id IS NULL`. A new group-ride-listing path filters `WHERE group_id = :group_id`, gated by a membership check. RLS additionally enforces that only members can `SELECT` rides with a non-null `group_id` for their group (defense in depth beyond the application-level filter).

**Rationale**: Directly matches the spec's Key Entities framing ("Ride, existing entity, extended") and Technical Considerations ("extend the existing ride search/listing logic with a group filter rather than introducing a parallel ride-discovery system" — Principle VI). Minimal schema change, no new ride-lifecycle states.

**Alternatives considered**: Many-to-many `ride_groups` join table — rejected; spec's clarification fixed ride:group cardinality at exactly one group per ride (or none), so a join table would model a relationship that can never have more than one row per ride, which is unnecessary complexity (Quality Standards: "favor simplicity unless complexity is demonstrably justified").

## 5. Route-tag / directory search

**Decision**: `route_tags TEXT[]` column on `groups`, searched via existing `pg_trgm` (already enabled by `20260802000001_phase11_profiles_search_trgm_index.sql`) trigram index on `name` and a GIN index on `route_tags` for array containment/overlap queries.

**Rationale**: Reuses infrastructure already proven for sub-second fuzzy search (NFR-001) rather than introducing a new search mechanism (e.g., full-text search config, external search service) for what the spec explicitly frames as free-form descriptive text (Assumptions: "not a fixed geofence or enforced route boundary").

**Alternatives considered**: PostGIS geofence matching on route tags — rejected per spec Assumptions (explicitly deferred to future recommendation work, not required to gate membership).

## 6. Identity-verification gating pattern

**Decision**: Enforce `profiles.verification_status == 'verified'` as an explicit check inside `group_service.py` functions that require it (create group, join, post/book group-scoped rides), not via a global middleware change.

**Rationale**: Matches the platform's established, deliberate pattern (per prior Spec 021 "Deferred Identity Verification" — gating is page/endpoint-level, not middleware-level, so partially-onboarded users aren't blocked from unrelated read-only actions). `get_current_user` (`dependencies/auth.py`) only blocks `suspended` accounts globally; every other verification-status gate in this codebase (e.g., `verification_service`, ride creation) is enforced locally at the point of the sensitive action. Directory *browsing* (FR-003) does not require full verification per the spec's user story language ("any identity-verified platform user" is the ceiling, not every unauthenticated action) — browsing follows the same authenticated-but-not-necessarily-fully-verified pattern as general ride search today.

**Alternatives considered**: New middleware-level gate — rejected as inconsistent with the established, deliberate pattern and Spec 021's explicit design decision.

## 7. Domain → group type determination

**Decision**: The first user to verify an email on a never-seen domain declares the intended group type (`company` or `university`) as part of the verification request (`POST /groups/domain-verification/request`). That declared type is persisted on `domain_verifications` and copied onto the newly created `groups` row when verification succeeds. Every subsequent verification on the same domain is looked up by domain only (type is ignored/inherited from the existing group) — this directly implements the spec's edge case ("the first successful verification on a domain fixes its type going forward").

**Rationale**: The spec requires a type but never says where it comes from for a brand-new domain; declaring it at request time is the minimal addition that resolves the ambiguity without a manual admin step.

**Alternatives considered**: Infer type heuristically (e.g., `.edu`-style suffix detection) — rejected; unreliable across countries/TLDs (many Egyptian universities do not use a distinguishing suffix) and the spec's anti-abuse framing already assumes explicit user-declared org type is acceptable at this trust tier ("domain-verified," not "employer-verified").
