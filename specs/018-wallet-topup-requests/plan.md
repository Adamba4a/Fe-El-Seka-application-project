# Implementation Plan: Manual Wallet Top-Up via Vodafone Cash

**Branch**: `018-wallet-topup-requests` | **Date**: 2026-08-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-wallet-topup-requests/spec.md`

## Summary

Add a driver-initiated, admin-reviewed request layer in front of the existing `011-financial-system`
`ADMIN_CREDIT` wallet top-up path. Drivers submit an amount, a Vodafone Cash transaction reference,
and a screenshot; an admin visually verifies against the platform's real Vodafone Cash account and
approves (crediting the wallet through the existing, unmodified `wallet_service` functions inside one
DB transaction) or rejects (with a mandatory reason). A 3-strike resubmission cap locks abusive
drivers until an admin unlock. No new crediting logic, no payment gateway, no OCR/automated
verification — everything financial routes through code that already exists and is proven in
`011-financial-system`. Driver-facing surfaces (`apps/main`) ship bilingual EN/AR from day one via the
existing `017-arabic-rtl-localization` infrastructure; the admin queue (`apps/admin`) stays
English-only, consistent with 017's own scope decision to exclude the Admin Panel.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend, `services/api`), TypeScript / Node.js 20 (Next.js 14 frontend)

**Primary Dependencies**: FastAPI + asyncpg (raw SQL, no ORM — matches `011-financial-system`'s pattern for anything touching `driver_wallets`/`driver_ledger_entries`), `supabase-py` (Storage bucket calls only, via the existing `storage_service` module), Python `decimal.Decimal` for money, `next-intl` (existing, `apps/main` only), Supabase Auth JWT middleware

**Storage**: Supabase PostgreSQL — one new table (`wallet_topup_requests`), two new columns on `profiles` (`is_topup_locked`, `topup_lock_reset_at`), one new nullable column on `admin_audit_logs` (`topup_request_id`); one new seed row in the existing `platform_settings` table; one new private Storage bucket (`topup-proofs`)

**Testing**: pytest + httpx (backend unit + integration, mirrors `011-financial-system`); manual browser validation per `quickstart.md` (frontend flows, RTL/Arabic rendering)

**Target Platform**: Mobile-first web (Next.js 14, Tailwind CSS, shadcn/ui) for the driver-facing screens; desktop-first Admin Panel for the review queue; Linux server (FastAPI via uvicorn)

**Project Type**: Monorepo — `apps/main` (driver top-up request/history screens), `apps/admin` (review queue), `services/api` (FastAPI backend)

**Performance Goals**: All new endpoints p95 < 500ms under ≤1,000 active users (NFR-001); admin queue renders < 2s for up to 500 pending items (NFR-004)

**Constraints**:
- `amount_egp` stored as `NUMERIC(12,2)`, never `FLOAT`/`DOUBLE PRECISION` — matches `011-financial-system`
- The approval endpoint MUST reuse `wallet_service.get_wallet_with_lock()` / `increment_balance()` / `insert_ledger_entry(entry_type="ADMIN_CREDIT")` inside one `conn.transaction()` — no parallel crediting code (FR-009, NFR-006)
- `payment_reference` uniqueness (FR-005) and one-`PENDING`-per-driver (FR-004) are both enforced with partial unique indexes at the DB level, not only in application code (NFR-005)
- Screenshots stored in a new private bucket (`topup-proofs`), never publicly accessible (NFR-002)
- Driver-facing strings and formatting ship through `apps/main`'s existing `next-intl` catalogs and locale-aware formatters (FR-018, FR-019); the Admin Panel is explicitly out of scope for both, per 017's existing exclusion

**Scale/Scope**: ≤1,000 active drivers (same as `011-financial-system`); admin queue up to 500 pending requests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Driver-facing wallet top-up only; no change to ride discovery, matching, or booking flows. |
| ✅ | II — Route Intelligence Over Geographic Proximity | No routing/matching logic touched. |
| ✅ | III — Trust Before Transportation | Only verified drivers (existing `get_current_driver` gate) may submit; admin manually verifies proof before any credit; full audit trail via `admin_audit_logs` (FR-013). |
| ✅ | IV — AI-Augmented Transportation | No AI/ML in this feature by design (Out-of-Scope: no OCR/auto-approval) — consistent with Principle IV's "deterministic logic remains source of truth," nothing to violate. |
| ✅ | V — Mobile-First UX | Driver screens in `apps/main` follow the same mobile-first Tailwind/shadcn/ui patterns as the existing wallet page. |
| ✅ | VI — Modular Domain-Driven | Scoped entirely to Financial System / Platform Operations. No new domain concepts — it's a request-and-review layer in front of an existing domain capability. |
| ✅ | VII — Shared Foundations | Reuses existing `wallet_service`, `storage_service`, `fcm_service`, `audit_service`, `platform_settings`, and `next-intl` infrastructure rather than duplicating any of it. No new apps/packages. |

No violations. Complexity Tracking not required.

Re-checked after Phase 1 design (data-model.md, contracts/api.md): still no violations. The one
scope correction made during Phase 0 research (FR-018/FR-019 narrowed to driver-facing surfaces,
§3 in research.md) *reduces* footprint relative to the pre-research draft — it does not introduce a
new gate concern.

## Project Structure

### Documentation (this feature)

```text
specs/018-wallet-topup-requests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api.md           # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
└── tasks.md              # Phase 2 output (/speckit-tasks command — NOT created by /speckit-plan)
```

### Source Code (repository root)

Monorepo — Fe El Seka / Triplyy (Principle VII: Shared Foundations, Independent Applications).
This feature touches `services/api` (backend), `apps/main` (driver-facing UI), and `apps/admin`
(admin review queue). All paths below were verified against the current repository during Phase 0
research; new files/columns are marked **NEW**, changed existing files are marked **MODIFIED**.

```text
services/api/app/
├── models/
│   └── wallet_topup.py                       # NEW — Pydantic request/response models (mirrors models/wallet.py)
├── services/
│   ├── wallet_topup_service.py                # NEW — submit/list/cancel/approve/reject/unlock logic;
│   │                                           #       approve() calls the existing, unmodified
│   │                                           #       wallet_service.get_wallet_with_lock() /
│   │                                           #       increment_balance() / insert_ledger_entry()
│   ├── wallet_service.py                      # UNCHANGED — reused as-is (FR-009)
│   ├── storage_service.py                     # UNCHANGED — reused for topup-proofs bucket I/O
│   ├── audit_service.py                       # UNCHANGED — reused for admin_audit_logs writes
│   └── fcm_service.py                          # MODIFIED — add wallet_topup_approved /
│                                                #            wallet_topup_rejected entries to
│                                                #            _NOTIFICATION_TEMPLATES (en/ar)
└── api/
    ├── wallet_topup/
    │   └── router.py                           # NEW — driver-facing endpoints (settings, submit,
    │                                            #       list, cancel), get_current_driver-gated
    └── admin/
        └── wallet_topup_router.py              # NEW — admin endpoints (queue, approve, reject,
                                                 #       unlock), get_current_admin-gated

supabase/migrations/
├── 2026XXXXXXXXXX_create_wallet_topup_requests.sql   # NEW — table + indexes (data-model.md §1)
├── 2026XXXXXXXXXX_add_topup_lock_to_profiles.sql     # NEW — profiles.is_topup_locked / topup_lock_reset_at (§2)
├── 2026XXXXXXXXXX_add_topup_request_to_audit_logs.sql # NEW — admin_audit_logs.topup_request_id (§3)
├── 2026XXXXXXXXXX_seed_vodafone_cash_number.sql      # NEW — platform_settings seed row (§4)
└── 2026XXXXXXXXXX_create_topup_proofs_bucket.sql     # NEW — private Storage bucket (§5)

apps/main/src/                                  # Driver-facing (bilingual EN/AR, existing 017 infra)
├── app/(driver)/wallet/
│   ├── page.tsx                                # UNCHANGED — existing wallet screen (pattern to mirror)
│   └── topup/
│       ├── page.tsx                            # NEW — top-up request form (US1)
│       └── history/
│           └── page.tsx                        # NEW — driver's own request history + cancel (US3)
├── lib/api/
│   ├── wallet.ts                                # UNCHANGED
│   └── wallet-topup.ts                          # NEW — client for the 4 driver-facing endpoints
└── messages/
    ├── en.json                                  # MODIFIED — new `driver.walletTopup.*` keys (FR-018)
    └── ar.json                                  # MODIFIED — matching Arabic keys, no FR-011 fallback reliance

apps/admin/src/                                  # Admin queue (English-only, matches 017 exclusion)
├── app/(dashboard)/wallet-topup/
│   ├── page.tsx                                 # NEW — pending queue (US2), mirrors verification/page.tsx
│   └── history/
│       └── page.tsx                             # NEW — reviewed requests + inline "Unlock" action per
│                                                 #       locked driver row, mirroring the existing pattern
│                                                 #       in verification/history/page.tsx (handleUnlock)
└── lib/api/
    └── admin-wallet-topup.ts                    # NEW — client for the 4 admin endpoints, mirrors
                                                  #       admin-verification.ts (getQueue/approve/reject/unlock)
```

**Structure Decision**: Monorepo Option 4 (Fe El Seka's existing structure), using the real app
names `apps/main` and `apps/admin` — not the template's placeholder `apps/passenger`/`apps/driver`.
Backend logic lives in `services/api/app` (the actively-developed FastAPI service; the sibling
`backend/` directory is stale and out of scope). No new apps or packages are introduced; every new
file sits inside an existing app/service boundary, and the two new UI surfaces (driver top-up form
and history, admin review queue and history) directly mirror an existing sibling feature's file
layout (`apps/main/(driver)/wallet` and `apps/admin/(dashboard)/verification` respectively) rather
than inventing a new convention.

## Complexity Tracking

No Constitution Check violations. Not applicable.
