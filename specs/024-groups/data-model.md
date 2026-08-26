# Phase 1 Data Model: Groups

## `groups`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `name` | `text NOT NULL` | User-provided (general) or auto-derived from domain (company/university) — FR-001, FR-013 |
| `type` | `text NOT NULL CHECK (type IN ('general','company','university'))` | Immutable after creation |
| `description` | `text NULL` | Free text; required for general groups, optional/auto-filled for domain groups |
| `route_tags` | `text[] NOT NULL DEFAULT '{}'` | Free-form; GIN-indexed for directory search |
| `owner_id` | `uuid NOT NULL REFERENCES profiles(id)` | FR-002; transferable (FR-019) |
| `domain` | `text NULL UNIQUE` | Set only for `company`/`university`; enforces one-group-per-domain (FR-013). `CHECK` constraint ties this to `type`: NULL iff `general`, NOT NULL iff `company`/`university`. |
| `invite_token` | `text NOT NULL UNIQUE DEFAULT replace(gen_random_uuid()::text,'-','')` | Regeneratable (FR-004). Uses `gen_random_uuid()` rather than `pgcrypto`'s `gen_random_bytes()` since this project doesn't enable `pgcrypto` (native `gen_random_uuid()` is Postgres 13+ built-in). |
| `invite_token_revoked_at` | `timestamptz NULL` | Non-null token segments are invalid once regenerated — old token row is simply overwritten, so this tracks last-rotation time for audit only |
| `member_count` | `integer NOT NULL DEFAULT 0` | Denormalized counter, maintained entirely by a trigger on `group_memberships` insert/delete (including the owner's own initial membership row), for directory display (FR-003) without a COUNT(*) on every search hit. Default is `0`, not `1`, so the trigger is the single source of truth and the owner's insert isn't double-counted. |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
| `archived_at` | `timestamptz NULL` | Soft delete (FR-021, constitution Data Standards) |

**Validation**: `name` required, 3–80 chars. `route_tags` max 10 tags, each ≤40 chars (mirrors reasonable UI constraints, not explicitly in spec — documented as an implementation default). `domain` lowercase-normalized, non-blocklisted (enforced at the service layer before insert, not a DB constraint, since the blocklist is runtime-configurable per NFR-004).

## `group_memberships`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid PK default gen_random_uuid()` | |
| `group_id` | `uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE` | |
| `user_id` | `uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE` | |
| `role` | `text NOT NULL CHECK (role IN ('owner','member')) DEFAULT 'member'` | Exactly one `owner` row per group, enforced at the service layer during creation/transfer |
| `domain_verification_id` | `uuid NULL REFERENCES domain_verifications(id)` | Set for company/university memberships; null for general groups |
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
| `requested_group_type` | `text NOT NULL CHECK (requested_group_type IN ('company','university'))` | Declared by the requester; only meaningful/used the first time a domain is seen (Research §7) |
| `otp_code_hash` | `text NOT NULL` | Salted hash, never store the raw code |
| `otp_expires_at` | `timestamptz NOT NULL` | Matches platform's existing OTP TTL convention (5 min, per `auth_service.request_otp`'s `expires_in_seconds: 300`) |
| `verified_at` | `timestamptz NULL` | Null until confirmed |
| `is_first_for_domain` | `boolean NOT NULL DEFAULT false` | Set true if `domain` had no prior successful (`verified_at IS NOT NULL`) row at request time — used both to decide whether a new `groups` row is created on success, and as the rate-limit counting predicate (Research §3) |
| `created_at` | `timestamptz NOT NULL DEFAULT now()` | |

**Validation**: FR-011 blocklist check happens before a row is even inserted (no OTP sent, no record of the rejected attempt needed beyond the existing resend-rate-limit tracking pattern). Standard OTP resend/attempt rate limiting reuses the same window/max shape as `auth_service._check_resend_rate` (FR-020).

## `rides` (existing table, extended)

| Column | Type | Notes |
|---|---|---|
| `group_id` | `uuid NULL REFERENCES groups(id) ON DELETE RESTRICT` | NULL = general feed (today's behavior, unchanged); non-null = visible only to that group's members (FR-007, FR-008). `ON DELETE RESTRICT`, not `SET NULL`/`CASCADE`: groups are soft-deleted only (`archived_at`, FR-021), so a hard delete should never happen — `RESTRICT` blocks it at the DB level rather than risking `SET NULL` silently exposing a group's private rides to the public feed (`group_id IS NULL` is the public-feed flag) or `CASCADE` destroying real ride history. |

No other existing tables change.

## Relationships

```text
profiles 1───* group_memberships *───1 groups
profiles 1───* domain_verifications
domain_verifications 1───0..1 group_memberships   (domain_verification_id, company/university only)
groups 1───* rides   (nullable group_id)
groups 1───1 profiles (owner_id)
```

## RLS Summary (detail in `contracts/api.md` and the migration itself)

- `groups`: `SELECT` open to any authenticated user (directory browsing, FR-003); `INSERT`/`UPDATE` restricted to service-role or owner (via API, not direct client writes — matches existing pattern where the FastAPI service role performs writes).
- `group_memberships`: `SELECT` restricted to the row's own `user_id` or the group's `owner_id`; writes via service role only.
- `domain_verifications`: `SELECT` restricted to the row's own `user_id`; no client `INSERT`/`UPDATE` policy at all — writes are service-role only, since a client-writable row would let a user set `verified_at`/`is_first_for_domain` themselves and bypass the OTP flow. No client ever reads another user's verification attempts either (contains a hashed OTP and a real email address — least-privilege per constitution Security & Privacy).
- `rides`: existing `SELECT` policy extended with `OR (group_id IS NOT NULL AND EXISTS (SELECT 1 FROM group_memberships WHERE group_id = rides.group_id AND user_id = auth.uid()))`, replacing the current unconditional-if-not-cancelled visibility for the group-scoped case.
