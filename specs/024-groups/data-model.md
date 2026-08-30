# Phase 1 Data Model: Groups

> **Superseded 2026-08-30**: The `type`/`domain` columns described in the original design below were dropped by `supabase/migrations/20260830000004_open_groups_multi_domain_sponsorship.sql`. Groups no longer carry a type; any org-email-verified user may join any group unconditionally. Domain-gated email verification survived, but repurposed: it now proves per-group *sponsorship eligibility* (Spec 026) via a new `group_sponsor_domains` table (documented in `specs/026-sponsored-groups/data-model.md`), not group creation or membership gating. The table below reflects the CURRENT schema.

## `groups`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `name` | `text NOT NULL` | User-provided at creation — FR-001 |
| `description` | `text NULL` | Free text |
| `route_tags` | `text[] NOT NULL DEFAULT '{}'` | Free-form; GIN-indexed for directory search |
| `owner_id` | `uuid NOT NULL REFERENCES profiles(id)` | FR-002; transferable (FR-019) |
| `invite_token` | `text NOT NULL UNIQUE DEFAULT replace(gen_random_uuid()::text,'-','')` | Regeneratable (FR-004). Uses `gen_random_uuid()` rather than `pgcrypto`'s `gen_random_bytes()` since this project doesn't enable `pgcrypto` (native `gen_random_uuid()` is Postgres 13+ built-in). |
| `invite_token_revoked_at` | `timestamptz NULL` | Non-null token segments are invalid once regenerated — old token row is simply overwritten, so this tracks last-rotation time for audit only |
| `member_count` | `integer NOT NULL DEFAULT 0` | Denormalized counter, maintained entirely by a trigger on `group_memberships` insert/delete (including the owner's own initial membership row), for directory display (FR-003) without a COUNT(*) on every search hit. Default is `0`, not `1`, so the trigger is the single source of truth and the owner's insert isn't double-counted. |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `archived_at` | `timestamptz NULL` | Soft delete (FR-021, constitution Data Standards) |
| `is_sponsored` / `funded_balance_egp` / `dashboard_contact_user_id` | — | Added by Spec 026; documented in `specs/026-sponsored-groups/data-model.md`, not repeated here. |

**Validation**: `name` required, 3–80 chars. `route_tags` max 10 tags, each ≤40 chars (mirrors reasonable UI constraints, not explicitly in spec — documented as an implementation default). The former `type`/`domain` columns and their `chk_groups_type_domain` constraint were dropped; the public-provider blocklist check now applies at the sponsorship-eligibility-verification step (`group_sponsor_domains`), not at group creation.

## `group_memberships`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `group_id` | `uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE` | |
| `user_id` | `uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE` | |
| `role` | `text NOT NULL CHECK (role IN ('owner','member')) DEFAULT 'member'` | Exactly one `owner` row per group, enforced at the service layer during creation/transfer |
| `domain_verification_id` | `uuid NULL REFERENCES domain_verifications(id)` | Optional per-group sponsorship-eligibility flag (Spec 026): set only when this member confirmed a domain on that specific group's `group_sponsor_domains` list; null for every ordinary membership, since joining itself no longer requires or implies any domain verification |
| `joined_at` | `timestamptz NOT NULL DEFAULT now()` | |

**Constraints**: `UNIQUE (group_id, user_id)` — a user cannot join the same group twice (US3 acceptance scenario 4: re-opening an invite link shows "already a member").

**State transitions**: row deleted on leave (FR-017) or owner-removal (FR-018) — membership has no soft-delete state; a re-join creates a fresh row. Ownership transfer (FR-019) is a service-layer transaction: flip old owner's role to `member`, new owner's role to `owner`, both in the same DB transaction.

## `domain_verifications`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `user_id` | `uuid NOT NULL REFERENCES profiles(id)` | |
| `email` | `text NOT NULL` | The full address entered by the user |
| `domain` | `text NOT NULL` | Lowercased portion after `@`, extracted at insert |
| `group_id` | `uuid NULL REFERENCES groups(id)` | Added by the redesign migration: the specific sponsored group this verification attempt targets. Nullable to preserve historical rows from before the redesign. |
| `otp_code_hash` | `text NOT NULL` | Salted hash, never store the raw code |
| `otp_expires_at` | `timestamptz NOT NULL` | Matches platform's existing OTP TTL convention (5 min, per `auth_service.request_otp`'s `expires_in_seconds: 300`) |
| `verified_at` | `timestamptz NULL` | Null until confirmed |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

`requested_group_type` and `is_first_for_domain` (original design) were dropped by the redesign migration — there is no group-type to request, and domain verification no longer creates groups or has a "first for domain" concept; eligible domains are pre-registered per sponsored group by an admin (`group_sponsor_domains`, Spec 026).

**Validation**: FR-011 blocklist check happens before a row is even inserted (no OTP sent, no record of the rejected attempt needed beyond the existing resend-rate-limit tracking pattern). Standard OTP resend/attempt rate limiting reuses the same window/max shape as `auth_service._check_resend_rate` (FR-020). On confirm, the target group must be sponsored, not archived, and the email's domain must be on that group's `group_sponsor_domains` list, or confirmation is rejected (`not_sponsored` / `group_archived` / `domain_not_eligible`).

## `rides` (existing table, extended)

| Column | Type | Notes |
|---|---|---|
| `group_id` | `uuid NULL REFERENCES groups(id) ON DELETE RESTRICT` | NULL = general feed (today's behavior, unchanged); non-null = visible only to that group's members (FR-007, FR-008). `ON DELETE RESTRICT`, not `SET NULL`/`CASCADE`: groups are soft-deleted only (`archived_at`, FR-021), so a hard delete should never happen — `RESTRICT` blocks it at the DB level rather than risking `SET NULL` silently exposing a group's private rides to the public feed (`group_id IS NULL` is the public-feed flag) or `CASCADE` destroying real ride history. |

No other existing tables change.

## Relationships

```text
profiles 1───* group_memberships *───1 groups
profiles 1───* domain_verifications
domain_verifications 1───0..1 group_memberships   (domain_verification_id, optional sponsorship-eligibility flag)
domain_verifications *───1 groups                 (group_id, the specific sponsored group targeted)
groups 1───* group_sponsor_domains                (Spec 026 — a sponsored group's eligible domains)
groups 1───* rides   (nullable group_id)
groups 1───1 profiles (owner_id)
```

## RLS Summary (detail in `contracts/api.md` and the migration itself)

- `groups`: `SELECT` open to any authenticated user (directory browsing, FR-003); `INSERT`/`UPDATE` restricted to service-role or owner (via API, not direct client writes — matches existing pattern where the FastAPI service role performs writes).
- `group_memberships`: `SELECT` restricted to the row's own `user_id` or the group's `owner_id`; writes via service role only.
- `domain_verifications`: `SELECT` restricted to the row's own `user_id`; no client `INSERT`/`UPDATE` policy at all — writes are service-role only, since a client-writable row would let a user set `verified_at` themselves and bypass the OTP flow. No client ever reads another user's verification attempts either (contains a hashed OTP and a real email address — least-privilege per constitution Security & Privacy).
- `rides`: existing `SELECT` policy extended with `OR (group_id IS NOT NULL AND EXISTS (SELECT 1 FROM group_memberships WHERE group_id = rides.group_id AND user_id = auth.uid()))`, replacing the current unconditional-if-not-cancelled visibility for the group-scoped case.
