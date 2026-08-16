# Research: Manual Wallet Top-Up via Vodafone Cash

**Feature**: `018-wallet-topup-requests` | **Date**: 2026-08-08

No `[NEEDS CLARIFICATION]` markers remain in `spec.md` after `/speckit-clarify`. This document records
the concrete implementation decisions made by inspecting the actual codebase (not the spec's
prose alone) before design.

---

## 1. Wallet-crediting reuse (FR-009)

**Decision**: The approval endpoint calls `wallet_service.get_wallet_with_lock()`,
`wallet_service.increment_balance()`, and `wallet_service.insert_ledger_entry(entry_type="ADMIN_CREDIT", ...)`
— the exact same three calls, in the exact same order, that
`POST /admin/drivers/{driver_id}/wallet/topup` (`services/api/app/api/admin/wallet_router.py:71-100`)
already makes inside one `conn.transaction()` block.

**Rationale**: There is no single "top-up" service function to call — the existing admin endpoint
itself is the orchestration of three granular `wallet_service` functions inside a router-level
transaction. FR-009's "calls the same function/service" requirement is satisfied by reusing those
same granular functions from the new approval endpoint's own transaction block, not by having one
endpoint call another over HTTP. This keeps `wallet_service.py` as the single source of ledger-write
logic (no new crediting code), matching how `adjust_wallet` (ADMIN_DEBIT) already reuses the same
functions for a sibling operation.

**Alternatives considered**: Extracting a new `wallet_service.credit_wallet_admin(...)` helper that
both the existing admin endpoint and the new approval endpoint call. Rejected for this feature — it
would require touching and re-testing the already-shipped `011-financial-system` endpoint, which is
out of proportion to this feature's scope. Calling the three existing functions directly is a pure
addition with zero risk to the existing endpoint.

---

## 2. Data access pattern: asyncpg vs. supabase-py

**Decision**: Use the `services/api/app/core/database.get_pool()` asyncpg pool (raw SQL, `conn.transaction()`,
`SELECT ... FOR UPDATE`) for every endpoint that touches `wallet_topup_requests` — submission, cancel,
admin queue, approve, reject — not the `supabase-py` client used by `verification_service.py`.

**Rationale**: `011-financial-system` established asyncpg + explicit row locks as the required pattern
for anything that reads or writes `driver_wallets`/`driver_ledger_entries`, specifically because
`supabase-py`'s PostgREST-based client cannot express `SELECT ... FOR UPDATE` or a multi-statement
transaction. The approval endpoint here *must* lock the wallet row and write the ledger entry and the
request's new status atomically (NFR-006) — so it must be asyncpg. For consistency (one code path,
one set of DB helpers, no mixed-client bugs), the rest of this feature's endpoints use asyncpg too,
even though submission/cancel/queue don't themselves need row locks (queue listing does need a stable
one-driver-one-pending guarantee, provided by a DB constraint — see §4).

**Alternatives considered**: Following `verification_service.py`'s `supabase-py` pattern for the
non-money endpoints (submit, cancel, queue) since they're structurally closer to identity
verification than to wallet mutation. Rejected — splitting the feature's own service module across
two DB clients for no functional benefit adds cognitive overhead for one module; asyncpg can express
everything supabase-py can here.

---

## 3. Admin Panel localization scope (FR-018, FR-019) — spec correction

**Finding**: `017-arabic-rtl-localization` explicitly scoped the Admin Panel *out* of Arabic/RTL
support (`specs/017-arabic-rtl-localization/spec.md` line 225: "Admin Panel localization — the Admin
Panel remains English-only for this iteration"). Confirmed in code: `apps/admin` has no `next-intl`
dependency, no `messages/*.json` catalogs, and its existing wallet views (`AdminLedgerTable.tsx`)
hardcode `Intl.NumberFormat("en-EG", ...)` / `.toLocaleString("en-EG", ...)` directly rather than using
a shared locale-aware formatter.

The original spec draft's FR-018/FR-019 (written during `/speckit-specify`/`/speckit-clarify`, before
this codebase-level research) required the admin review queue to also ship Arabic translations "using
the translation-catalog mechanism established in 017" — infrastructure that does not exist for
`apps/admin`. This was a spec defect, not a deliberate scope decision.

**Resolution** (confirmed with user during `/speckit-plan`): `spec.md` FR-018/FR-019 and the related
Dependencies/Technical Considerations bullets were corrected to scope the bilingual EN/AR requirement
to driver-facing surfaces only (`apps/main`: top-up form, history, cancellation, push notifications).
The admin review queue (`apps/admin`) stays English-only and keeps its existing fixed `en-EG` `Intl`
formatting convention — consistent with 017's own rationale that Admin Panel staff are English-comfortable.
This removes any need to introduce `next-intl`/RTL infrastructure into `apps/admin` for this feature.

---

## 4. Concurrency-safe "one PENDING request per driver" (FR-004)

**Decision**: Enforce FR-004 at the database level with a partial unique index:
`CREATE UNIQUE INDEX ON wallet_topup_requests (driver_id) WHERE status = 'PENDING'`, in addition to an
application-level pre-check for a fast, friendly error message.

**Rationale**: Matches this feature's own NFR-005 philosophy (uniqueness enforced at the DB level, not
only in application code, to close a TOCTOU race between two concurrent submissions) and the identical
pattern already used for `payment_reference` uniqueness (FR-005/NFR-005). A partial unique index is the
same technique, applied to a second column.

**Alternatives considered**: Application-level check only (`SELECT ... WHERE status='PENDING'` before
insert). Rejected — same race window that NFR-005 explicitly calls out for `payment_reference`; no
reason to accept it here when the identical fix is one more partial index.

---

## 5. Resubmission-cap cycle tracking (FR-014/FR-015/FR-016)

**Decision**: Add two columns to `profiles`: `is_topup_locked BOOLEAN NOT NULL DEFAULT FALSE` and
`topup_lock_reset_at TIMESTAMPTZ NULL`. On the 3rd `REJECTED` outcome since the later of
`topup_lock_reset_at` and account creation, set `is_topup_locked = TRUE`. On admin unlock or on any
`APPROVED` outcome, set `topup_lock_reset_at = now()` (and `is_topup_locked = FALSE` on unlock).
The "3rd rejection" count itself is computed on demand with
`SELECT count(*) FROM wallet_topup_requests WHERE driver_id = $1 AND status = 'REJECTED' AND created_at > COALESCE($2, '-infinity')`
— no persisted counter column, per the spec's own Technical Considerations note that a derived count
is preferred over a stored counter unless required for performance (it isn't, at ≤1,000 active drivers).

**Rationale**: Mirrors `003-auth-verification`'s existing `profiles.is_submission_locked` boolean +
admin-unlock pattern as closely as possible, using a **separate** pair of columns rather than reusing
`is_submission_locked` — identity verification and wallet top-up are independent cycles per this
feature's own clarification ("mirroring... cap," not reusing the same lock), and conflating them would
incorrectly lock/unlock a driver's identity submissions when only their top-up cycle changed (or vice
versa). `verification_service.py` derives its own 3rd-attempt check from `attempt_number` on the
submission row rather than a separate counter — the `topup_lock_reset_at` boundary column here plays
the equivalent boundary-marking role without needing an `attempt_number` column on
`wallet_topup_requests`, since `CANCELLED` requests (which don't count) make a strictly incrementing
attempt number awkward to keep aligned with the "REJECTED-only" counting rule.

**Alternatives considered**: A persisted `topup_rejected_count` counter incremented on each rejection
and reset on approval/unlock. Rejected per the spec's explicit preference for on-demand derivation
at this scale; a counter adds a second source of truth that must stay in sync with the ledger of
requests, for no measurable performance benefit at ≤1,000 drivers.

---

## 6. Screenshot storage (FR-002, NFR-002)

**Decision**: New private Supabase Storage bucket `topup-proofs`, uploaded/downloaded/signed via the
existing `storage_service.upload_file()` / `storage_service.download_file()` /
`storage_service.generate_signed_url()` functions (all already bucket-name-parameterized — no code
changes needed to those functions, only a new bucket and new call sites).

**Rationale**: Directly mirrors `003-auth-verification`'s `identity-documents` bucket pattern
(NFR-002's own stated requirement). A dedicated bucket (rather than reusing `identity-documents`)
keeps payment-proof images access-scoped separately from identity documents, which is good hygiene
given they have different retention/access-audit needs, and costs nothing extra since the storage
helpers are already generic.

---

## 7. Platform Vodafone Cash number setting (FR-001)

**Decision**: Reuse the existing generic `platform_settings (key TEXT PRIMARY KEY, value TEXT)` table
(already seeded with `support_email`) with a new row, `key = 'vodafone_cash_number'`. Read via a small
`_get_vodafone_cash_number()` helper in the new service module, mirroring
`verification_service._get_support_email()` exactly (same table, same `.single()` read, same
fallback-if-missing behavior).

**Rationale**: `platform_settings` already exists precisely for this kind of admin-editable, non-hardcoded
value; no new table needed. Note: there is currently **no admin UI or endpoint** to edit
`platform_settings` rows — `support_email` is edited directly at the database level today. FR-001's
"admin-editable" requirement is satisfied the same way (direct DB edit by a platform operator), matching
`003-auth-verification` FR-037's actual (not aspirational) implementation. Building a settings-editor UI
is out of scope for both 003 and this feature.

**Alternatives considered**: A dedicated `PATCH /admin/settings/vodafone-cash-number` endpoint. Rejected
as scope creep — no equivalent exists for `support_email` today, and the spec does not require an
in-app editor, only that the value isn't hard-coded in application code.

---

## 8. Admin audit logging (FR-013)

**Decision**: Reuse the existing `admin_audit_logs` table and `audit_service.append_log()` function.
Requires one small migration: add a nullable `topup_request_id UUID REFERENCES wallet_topup_requests(id)`
column (mirroring the existing nullable `submission_id`/`report_id` columns already on that table) and
extend `audit_service.append_log()` with an optional `topup_request_id` parameter. The existing
`action_type` values (`'approved'`, `'rejected'`, `'unlocked'`) are reused as-is — the new
`topup_request_id` column is what disambiguates a top-up review action from an identity-verification
review action, so no CHECK constraint change is needed.

**Rationale**: `admin_audit_logs` is already a generic per-admin-action audit trail; the existing schema
just needs one more optional target-reference column, the same shape as its two existing ones. This
satisfies FR-013 (mirrors 003 FR-034) without introducing a second audit table.

---

## 9. Driver push notifications (FR-017)

**Decision**: Call the existing `fcm_service.send_push_notifications(conn, driver_id, event_type, data_payload)`
with two new `event_type` values, `wallet_topup_approved` and `wallet_topup_rejected`, added to
`fcm_service._NOTIFICATION_TEMPLATES` with `en`/`ar` title/body pairs (same dict shape as the existing
`rating_prompt`, `moderation_outcome`, etc. entries). The rejection notification's `data_payload`
includes the rejection reason (already-translated server-side title/body carries the templated
message; `data_payload` carries the raw reason string for the client to display alongside it, matching
how `moderation_outcome` passes structured data today).

**Rationale**: This is the existing, only notification mechanism in the codebase (`010-realtime-transportation`).
`_select_template()` already implements the FR-011-style English-fallback via `_DEFAULT_TEMPLATE` for
unmapped event types — but per this feature's FR-018, the two new event types get real `ar` entries
from day one rather than relying on that fallback.

---

## Summary of new/changed backend surface

| Component | Change |
|---|---|
| `services/api/app/models/wallet_topup.py` | **NEW** — Pydantic request/response schemas |
| `services/api/app/services/wallet_topup_service.py` | **NEW** — submission/cancel/queue/approve/reject/lock logic |
| `services/api/app/api/wallet_topup/router.py` | **NEW** — driver-facing endpoints (submit, list own, cancel) |
| `services/api/app/api/admin/wallet_topup_router.py` | **NEW** — admin queue/approve/reject/unlock endpoints |
| `services/api/app/services/wallet_service.py` | Unchanged — reused as-is (§1) |
| `services/api/app/services/storage_service.py` | Unchanged — reused as-is with a new bucket name (§6) |
| `services/api/app/services/fcm_service.py` | Extended — two new `_NOTIFICATION_TEMPLATES` entries (§9) |
| `services/api/app/services/audit_service.py` | Extended — optional `topup_request_id` param (§8) |
| `supabase/migrations/*` | **NEW** — `wallet_topup_requests` table, `topup-proofs` bucket, `profiles.is_topup_locked`/`topup_lock_reset_at`, `admin_audit_logs.topup_request_id`, RLS policies, `platform_settings` seed row |
| `apps/main` | **NEW** — driver top-up request screen, history screen, translation keys (`apps/main/messages/{en,ar}.json`) |
| `apps/admin` | **NEW** — review queue screen, English-only, following existing admin wallet-page conventions |
