# Phase 1 API Contract: Groups

Base path: `/api/groups` (new router mounted in `services/api/app/main.py` alongside the existing domain routers). All endpoints require an authenticated session (`get_current_user`); endpoints marked **Verified** additionally require `profiles.verification_status == 'verified'`, enforced in `group_service.py` per Research §6.

## Directory & Group Management

### `POST /api/groups` — Create a general group **[Verified]**
Request: `{ name: string, description: string, route_tags: string[] }`
Response `201`: full group object (see below), caller is `owner`.
Errors: `422` invalid name/tags, `403` not identity-verified.
→ FR-001, FR-002

### `GET /api/groups` — Search/browse directory **[authenticated]**
Query: `q?: string` (matches name via trigram), `type?: 'general'|'company'|'university'`, `route_tag?: string`, `limit?`, `offset?`
Response `200`: `{ items: GroupSummary[], total: number }` where `GroupSummary = { id, name, type, description, route_tags, member_count }` — no membership required to view (FR-003).
→ FR-003

### `GET /api/groups/{group_id}` — Group detail **[authenticated]**
Response `200`: `GroupSummary` + `{ is_member: boolean, is_owner: boolean }` for the caller.
Errors: `404` unknown or archived group.

### `POST /api/groups/{group_id}/invite-link` — Generate/regenerate invite link **[owner only]**
Response `200`: `{ invite_token: string, invite_url: string }`. Regenerating invalidates the previous token immediately (old token's `GET /join/{token}` starts returning `404`).
→ FR-004

### `GET /api/groups/join/{invite_token}` — Resolve invite link **[authenticated]**
Response `200`: same shape as group detail, used by the frontend to render the join screen before the join action is confirmed.
Errors: `404` unknown, revoked, or regenerated token (Edge Case: revoked link).
→ FR-005, US3

### `POST /api/groups/{group_id}/join` — Join a general group (directory or resolved-invite-link path) **[Verified]**
Response `200`: membership object. For `company`/`university` groups this endpoint returns `409 { error: "domain_verification_required" }` — the client must complete the domain-verification endpoints below first.
Errors: `409` already a member (idempotent-friendly — returns existing membership, not an error, per US3 scenario 4).
→ FR-005, FR-009 (feeds into), US1/US3

## Company/University Domain Verification

### `POST /api/groups/domain-verification/request` — Request a code **[Verified]**
Request: `{ email: string, requested_group_type: 'company'|'university' }`
Behavior: normalize domain from `email`; reject immediately with `422 { error: "blocklisted_domain" }` if on the blocklist (**no code sent** — FR-011, SC-004); otherwise create a `domain_verifications` row, send a 6-digit code via the platform's transactional email sender, subject to the same resend rate limit as `auth_service` (FR-020).
Response `200`: `{ verification_id: string, expires_in_seconds: 300 }`
→ FR-010, FR-011, US4 scenario 1–2

### `POST /api/groups/domain-verification/confirm` — Confirm a code **[Verified]**
Request: `{ verification_id: string, code: string }`
Behavior: check hash + expiry; on success, mark `verified_at`; if `is_first_for_domain`, create the `groups` row (name auto-derived per FR-013, type = `requested_group_type`) and check the new-domain rate limit (Research §3) before allowing the create to proceed — over-threshold returns `429`; otherwise attach to the existing group for that domain. Either way, create the caller's `group_memberships` row.
Response `200`: membership + group object.
Errors: `400 { error: "otp_invalid" }`, `410 { error: "otp_expired" }`, `429 { error: "domain_registration_rate_limited" }` (only possible on a first-for-domain confirm).
→ FR-010, FR-012, FR-013, FR-014, FR-015, US4 scenario 3–6

## Group Rides (thin layer over existing ride domain)

### `GET /api/groups/{group_id}/rides` — Group's active ride listing **[member only]**
Response `200`: same `RideResponse` shape already returned by the general search endpoint, filtered to `group_id = :group_id`. Non-members get `403`.
→ FR-007, US2 scenario 2/3

### Existing `POST /api/rides` — extended, not replaced
Request gains an optional `group_id?: string`. Service validates the caller is a member of that group before allowing the association; omitted/`null` = today's unscoped behavior.
→ FR-006, FR-008

### Existing general search/listing endpoints — extended, not replaced
All add `AND group_id IS NULL` to their base query so group-scoped rides never leak into the city-wide feed (FR-007, SC-005).

## Membership Management

### `POST /api/groups/{group_id}/leave` **[member]**
Response `204`. If caller is the owner and other members remain, returns `409 { error: "ownership_transfer_required" }` instead (FR-019) — client must call transfer-ownership first.
→ FR-017

### `DELETE /api/groups/{group_id}/members/{user_id}` **[owner only]**
Response `204`. Same effect as the target leaving voluntarily.
→ FR-018

### `POST /api/groups/{group_id}/transfer-ownership` **[owner only]**
Request: `{ new_owner_user_id: string }` (must already be a member).
Response `200`: updated group object.
→ FR-019

### `DELETE /api/groups/{group_id}` — Archive a group **[owner only]**
Soft-delete: sets `archived_at`, blocks new joins/invite-link resolution and new group-scoped ride creation from that point on. Already-posted, still-active rides keep `group_id` set and run their normal lifecycle unaffected (`ON DELETE SET NULL` on `rides.group_id` only fires on a hard delete, which this endpoint never performs).
Response `204`.
→ FR-021

## Shared error shape

All errors follow the existing platform convention already used across `verification_service`/`wallet_topup_service`: `{ "error": "<snake_case_code>", "message": "<human readable>" }` with an appropriate HTTP status.
