# Phase 1 Data Model: Organization-Only Access Gate

## Modified: `profiles`

| Column | Type | Notes |
|---|---|---|
| `org_verified_at` | `TIMESTAMPTZ`, nullable | **NEW**. Set once an account passes the gate (fresh confirm on this feature's endpoint, a Groups domain-verification confirm, or the one-time backfill migration). `NULL` means the account is still gated. Never cleared once set (Out-of-Scope: no periodic re-verification, no revocation on later domain rejection — R... see research.md R4). |
| `org_verified_domain` | `TEXT`, nullable | **NEW**. The domain that satisfied the gate, denormalized for admin visibility (Admin Panel display) without joining `domain_verifications`. |

Both columns are nullable at the DB level — "required" is an application-layer gate (frontend redirect + backend check on gated actions), mirroring how `verification_status` and Spec 020's phone/photo requirements are enforced today, not a DB-level NOT NULL.

No change to `verification_status` or any other existing `profiles` column. `org_verified_at` and `verification_status` are independent (FR-013).

## Modified: `domain_verifications` (existing table, from Spec 024)

| Column | Change |
|---|---|
| `requested_group_type` | Relax `NOT NULL` + `CHECK (requested_group_type IN ('company','university'))` to allow `NULL`. `NULL` = this row was created by the org-only-access gate flow (no group-join intent); `'company'`/`'university'` = created by the Groups domain-verification flow (unchanged behavior). |

No other schema change. Existing indexes (`idx_domain_verifications_domain`, `idx_domain_verifications_user`) already support this feature's lookups (checking for an existing confirmed row per user for the backfill/credit path, R3).

**Validation rules** (unchanged from Spec 024, reused via the extracted shared service — research.md R1):
- `email` must contain exactly one `@`, not at the start/end.
- `domain` (the part after `@`) must not appear in the `group_domain_blocklist` platform setting (R5).
- `otp_code_hash` never stores the plaintext code; expires 5 minutes after `request`.
- A `verification_id` is single-use — a `confirm` against an already-`verified_at`-set row is rejected (`otp_already_used`).

## New: Org Email Verification (conceptual — maps onto `domain_verifications`)

Per the spec's Key Entities, this is not a new table — it *is* the existing `domain_verifications` row, now shared by two flows:

| Flow | `requested_group_type` | Side effect on confirm |
|---|---|---|
| Groups domain verification (existing, Spec 024) | `'company'` or `'university'` | Creates/joins the domain's group (unchanged) **and** sets `profiles.org_verified_at`/`org_verified_domain` if not already set (new, R3) |
| Org-only-access gate (this feature) | `NULL` | Sets `profiles.org_verified_at`/`org_verified_domain` only — no group interaction |

An account's org-verified status is simply `profiles.org_verified_at IS NOT NULL` — no derived/joined query needed at read time (research.md R2).

## Unchanged: Domain Rejection List

Maps onto the existing `platform_settings` row keyed `group_domain_blocklist` (comma-separated domain list, default `gmail.com,yahoo.com,outlook.com,hotmail.com,icloud.com,protonmail.com`). No schema change; reused as-is (research.md R5).

## State transitions

```
profiles.org_verified_at
  NULL ──(gate confirm OR Groups confirm OR backfill)──▶ <timestamp>  (terminal; never reverts)

domain_verifications row
  requested (otp_expires_at set, verified_at NULL)
    ├─(correct code before expiry)──▶ verified_at set (terminal, single-use)
    ├─(expiry passes)───────────────▶ effectively dead; user must request a new row
    └─(wrong code)───────────────────▶ unchanged, retry allowed until expiry/attempt limits
```

## Migration summary

One new migration, `<timestamp>_org_only_access.sql`:
1. `ALTER TABLE profiles ADD COLUMN org_verified_at TIMESTAMPTZ, ADD COLUMN org_verified_domain TEXT;`
2. `ALTER TABLE domain_verifications ALTER COLUMN requested_group_type DROP NOT NULL;` and replace the `chk_domain_verifications_type` CHECK to allow `NULL` alongside `'company'`/`'university'`.
3. Backfill: `UPDATE profiles SET org_verified_at = sub.verified_at, org_verified_domain = sub.domain FROM (SELECT DISTINCT ON (user_id) user_id, domain, verified_at FROM domain_verifications WHERE verified_at IS NOT NULL ORDER BY user_id, verified_at ASC) sub WHERE profiles.id = sub.user_id;`
