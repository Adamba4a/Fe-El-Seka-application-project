# Quickstart: Validating Groups

Prerequisites: local Supabase stack running with the `024-groups` migrations applied, `services/api` running (`uvicorn`), two verified test accounts (A = driver, B = passenger), Mailpit running for local email capture (per `notification_service._use_mailpit`).

## 1. General group create + directory discovery (US1)

1. As A: `POST /api/groups` with `{ name: "Shorouk-Zayed Commute", description: "...", route_tags: ["shorouk","zayed"] }` → expect `201`, A is `owner`.
2. As B (different account): `GET /api/groups?q=shorouk` → expect the group in `items`, with `member_count: 1`, no membership required.
3. `GET /api/groups?q=doesnotexist` → expect `{ items: [], total: 0 }`.

**Pass condition**: SC-001 (create + directory-visible fast), SC-002 (found via search directly).

## 2. Group-scoped ride post + book (US2)

1. As B: `POST /api/groups/{group_id}/join` → `200`, B is now `member`.
2. As A: `POST /api/rides` with the usual ride payload + `group_id`.
3. As B: `GET /api/groups/{group_id}/rides` → the new ride appears.
4. As a third, non-member account C: `GET /api/groups/{group_id}/rides` → `403`.
5. As B: `GET /api/search` (general feed) → the group-scoped ride does **not** appear.
6. As B: book the ride via the existing booking endpoint, unchanged from today.

**Pass condition**: FR-006/007/008/009, SC-005, SC-006.

## 3. Invite link (US3)

1. As A: `POST /api/groups/{group_id}/invite-link` → capture `invite_token`.
2. As fresh account D: `GET /api/groups/join/{invite_token}` → resolves to the group (general type → no extra gate).
3. As A: regenerate the link (`POST` again).
4. As D: retry the *old* `invite_token` → `404`.

**Pass condition**: FR-004, FR-005, Edge Case (revoked link).

## 4. Company/university domain verification (US4)

1. As E (fresh account): `POST /api/groups/domain-verification/request` with `{ email: "e@gmail.com", requested_group_type: "company" }` → expect `422 blocklisted_domain`, confirm no email was sent (check Mailpit inbox is empty for this request).
2. As E: same request with `{ email: "e@acmecorp.com", requested_group_type: "company" }` → expect `200`; check Mailpit for the 6-digit code.
3. As E: `POST /api/groups/domain-verification/confirm` with the real code → expect `200`, a new group named "Acmecorp" exists, E is `owner` and `member`.
4. As fresh account F: repeat steps 2–3 with `f@acmecorp.com` → expect F joins the **same** existing group automatically, no admin step, F is `member` (not `owner`).
5. Confirm the group/member UI never displays "employer-verified," only "domain-verified" (FR-015).

**Pass condition**: FR-010 through FR-015, SC-003, SC-004.

## 5. Membership lifecycle (US5)

1. As F: `POST /api/groups/{group_id}/leave` → `204`; F's subsequent `GET /api/groups/{group_id}/rides` → `403`.
2. As E (owner) with F still a member: attempt `POST /api/groups/{group_id}/leave` before F leaves → expect `409 ownership_transfer_required`.
3. As E: `POST /api/groups/{group_id}/transfer-ownership` to another remaining member, then leave successfully.

**Pass condition**: FR-017, FR-018, FR-019.

## 6. Rate limit smoke test (anti-abuse)

1. Lower `group_new_domain_rate_limit` in `platform_settings` to `1` for the test window.
2. Verify two different brand-new domains within the window as two different first-time users.
3. Expect the second confirm to return `429 domain_registration_rate_limited`.

**Pass condition**: FR-014.

Refer to `contracts/api.md` for exact request/response shapes and `data-model.md` for the underlying schema.
