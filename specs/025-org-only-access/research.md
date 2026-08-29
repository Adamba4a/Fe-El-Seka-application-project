# Phase 0 Research: Organization-Only Access Gate

## R1: Reuse strategy for the Groups (024) domain-verification mechanism

**Decision**: Extract the shared OTP primitives currently private to `group_service.py` — domain blocklist lookup (`_get_domain_blocklist`), OTP generation/hashing (`_generate_otp`, `_hash_otp`), and per-email resend rate-limiting (`_check_domain_otp_resend_rate`) — into a new shared module, `services/api/app/services/domain_verification_service.py`. Both `group_service.py` (refactored to import from it, no behavior change for Groups) and a new `org_access_service.py` (this feature) call into the shared module. New, dedicated endpoints (`org_access_service.request_verification` / `confirm_verification`) write to the same `domain_verifications` table but do **not** perform Groups' group-creation/auto-join side effect.

**Rationale**:
- The constitution (Principle VII) prohibits duplicating shared functionality — copy-pasting the OTP send/hash/rate-limit logic into a second service would violate this directly.
- Groups' existing `confirm_domain_verification` is unsuitable to call as-is for this gate for two independent reasons: (1) it hard-requires `verification_status == "verified"` (National ID verification) via `_require_verified`, which would make the gate unreachable for the brand-new, not-yet-ID-verified accounts this gate must cover (FR-013, per Spec 021's deferred-KYC model); (2) on success it always creates/joins a group for the domain, which is out of this spec's scope (Out-of-Scope: "this specification covers only the access gate [Groups/026-028] will build on top of").
- A shared low-level module keeps the OTP mechanics (hash format, expiry, rate-limit window, blocklist) identical between both features without coupling their business logic.

**Alternatives considered**:
- *Call Groups' existing endpoints directly from the gate flow*: rejected — would require weakening `_require_verified` on a Groups-security-relevant endpoint, and would silently auto-enroll every gate-verifying user into a company/university group they never asked to join.
- *Duplicate the OTP logic in a new, fully independent service*: rejected — direct violation of Principle VII with no offsetting benefit; the two features would drift (e.g. blocklist edits made for one wouldn't apply to the other, contradicting the spec's Assumption that one shared list is reused).

---

## R2: Where org-verified status lives

**Decision**: Add a nullable `profiles.org_verified_at TIMESTAMPTZ` column, set once when an account passes the gate (either via a fresh confirm on this feature's new endpoint, or via a one-time backfill migration crediting accounts that already have a confirmed `domain_verifications` row from Groups — see R3). Gate checks (`app/page.tsx`, `(app)/layout.tsx`, `GET /me`-equivalent profile fetch) read this single column directly, exactly like the existing `verification_status` column.

**Rationale**:
- NFR-001 requires the gate check add no noticeable delay for already-verified users, who are the overwhelming majority of requests post-launch. A denormalized column on `profiles` is read in the same query that already fetches `role`/`display_name`/`verification_status` on every page load (see `app/page.tsx`) — zero extra round trips, versus a derived `EXISTS (...)` subquery/join against `domain_verifications` on every request.
- Matches the platform's existing pattern: `verification_status` (ID verification) already lives directly on `profiles` rather than being derived from a submissions table on each read.

**Alternatives considered**:
- *Derive status live from `domain_verifications` (`EXISTS` query)*: rejected as the primary mechanism — adds a query/join to the hottest path in the app (every authenticated page load) for no benefit, though this query is still useful as the one-time backfill source (R3).
- *A separate `org_verifications` status table*: rejected — unnecessary indirection when a single nullable timestamp column captures everything the gate needs to check ("has this account passed the gate, and when").

---

## R3: Crediting existing Groups domain verifications (FR-015)

**Decision**: A migration script backfills `profiles.org_verified_at` for every account that already has at least one confirmed `domain_verifications` row (`verified_at IS NOT NULL`), using the earliest such `verified_at` per user. Going forward, the new gate's own confirm endpoint sets `org_verified_at = now()` directly; Groups' existing confirm endpoint is additionally extended to set `profiles.org_verified_at` (if not already set) as a side effect, so a user who verifies a domain through Groups *after* this feature ships is also credited immediately, not just at backfill time.

**Rationale**: Directly implements the clarified decision (Clarifications session 2026-08-29) that a confirmed Groups verification — past or future — satisfies this gate without a second OTP round trip.

**Alternatives considered**:
- *Only credit at backfill time, not going forward*: rejected — would mean a brand-new user who verifies via Groups next month still hits the app-wide gate separately afterward, contradicting the "auto-credit" decision's intent.

---

## R4: `domain_verifications.requested_group_type` schema conflict

**Decision**: Migration relaxes `domain_verifications.requested_group_type` from `NOT NULL` + `CHECK (... IN ('company','university'))` to nullable, keeping the existing two allowed values for Groups-initiated rows and allowing `NULL` for rows created by this feature's gate-only flow (no group intent).

**Rationale**: The column's current `NOT NULL` constraint is specific to Groups' "which group type are you registering for" UX; this gate's flow (User Story 1) never asks that question — it only asks for an email. Reusing the table (R1/R2) is only viable if a gate-only row can be inserted without providing a group type.

**Alternatives considered**:
- *Force the gate UI to also ask "company or university?"*: rejected — adds a UI step with no product purpose for this feature (the value is only ever consumed by Groups' group-creation logic, which this flow never triggers), and contradicts the spec's User Story 1 acceptance scenarios (email + code only).

---

## R5: Domain rejection list storage

**Decision**: Reuse the existing `platform_settings` key `group_domain_blocklist` as-is (via the extracted `domain_verification_service._get_domain_blocklist`, R1) — no new key, no new admin surface. FR-006's "admin can add a domain to the rejection list" is satisfied by whatever mechanism already edits `group_domain_blocklist` today for Groups.

**Rationale**: Directly matches the spec's own Assumption ("no separate list is created") and Out-of-Scope ("no new admin UI for managing individual verification records"). A single shared blocklist also means an admin blocking an abused domain protects both Groups and the app-wide gate in one action.

**Alternatives considered**: A dedicated `access_gate_domain_blocklist` key — rejected as an unjustified split of one conceptual "personal/abusive email domains" list into two, adding an admin surface this spec explicitly puts out of scope.

---

## R6: Auditability (NFR-005)

**Decision**: No new audit-log table. The `domain_verifications` table itself is already an append-only record of every attempt (who, what email/domain, when requested, when confirmed/expired) and satisfies "verification activities" auditability for user-initiated events. Admin edits to the `group_domain_blocklist` platform setting go through the existing `admin_audit_logs` (`audit_service.append_log`) path already used for other admin actions — this feature adds no new admin action type beyond what already logs platform-setting changes, if any exists; if platform-setting edits are not currently audited, that is a pre-existing gap in Groups' own admin tooling, not something this feature must newly solve (see Out-of-Scope: no new admin UI).

**Rationale**: Reuses existing constitutional-compliance infrastructure rather than building parallel logging (Principle VII).

---

## R7: Enforcement point (frontend gate vs backend middleware)

**Decision**: Follow Spec 020's established pattern exactly — a page-level check in `apps/main`'s `app/page.tsx` and `(app)/layout.tsx` (mirroring the existing `verification_status`/`display_name === "New User"` checks), not a new global backend middleware or a rewrite of `dependencies/auth.get_current_user`. Backend endpoints that represent "real" app usage (ride search, booking, posting) additionally check `profiles.org_verified_at IS NOT NULL` server-side, the same way gated actions already check `verification_status` today, so the gate cannot be bypassed by calling the API directly.

**Rationale**: Spec 020 already established and shipped this exact "non-skippable frontend gate + backend-enforced server-side check on real actions" pattern for an app-wide requirement; reusing it is lower-risk than introducing a new enforcement mechanism (e.g., rewriting `get_current_user` to hard-block all requests, which risks breaking already-working prod auth — a risk this spec's Technical Considerations explicitly calls out avoiding).

**Alternatives considered**: Global backend middleware blocking all API calls pre-org-verification — rejected as higher blast radius (touches every endpoint, including the verification endpoints themselves, requiring careful allowlisting) for no behavioral difference from the chosen approach once each gated action is individually covered.
