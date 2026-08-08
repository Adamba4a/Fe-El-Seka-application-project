# Tasks: Manual Wallet Top-Up via Vodafone Cash

**Input**: Design documents from `specs/018-wallet-topup-requests/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/api.md ✅ | quickstart.md ✅

**Tests**: Not included — not explicitly requested in spec.md, matching the convention already used in `011-financial-system` and `003-auth-verification`. Run `quickstart.md`'s 5 scenarios manually after each phase checkpoint.

**Organization**: Tasks are grouped by user story (from spec.md, priorities P1/P2/P3) to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies within the phase)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup (Database Schema)

**Purpose**: Create all new SQL migration files per `data-model.md`. These are independent file-creation tasks — apply them together once all exist.

- [X] T001 [P] Create `supabase/migrations/20260808000001_create_wallet_topup_requests.sql` — `wallet_topup_requests` table per `data-model.md` §1 (all columns, `status` CHECK, `rejection_reason` CHECK); partial unique index `uq_topup_reference_active` on `payment_reference WHERE status IN ('PENDING','APPROVED')`; partial unique index `uq_topup_one_pending_per_driver` on `driver_id WHERE status = 'PENDING'`; index `idx_topup_pending_queue` on `created_at WHERE status = 'PENDING'`; index `idx_topup_driver_history` on `(driver_id, created_at DESC)`; RLS: driver SELECT/INSERT own rows (`driver_id = auth.uid()`), driver UPDATE own row only while `status = 'PENDING'` (cancel path); no admin policy needed (admin endpoints use the service-role key, per `data-model.md` §1)
- [X] T002 [P] Create `supabase/migrations/20260808000002_add_topup_lock_to_profiles.sql` — `ALTER TABLE profiles ADD COLUMN is_topup_locked BOOLEAN NOT NULL DEFAULT FALSE, ADD COLUMN topup_lock_reset_at TIMESTAMPTZ NULL` per `data-model.md` §2
- [X] T003 [P] Create `supabase/migrations/20260808000003_add_topup_request_to_audit_logs.sql` — `ALTER TABLE admin_audit_logs ADD COLUMN topup_request_id UUID NULL REFERENCES wallet_topup_requests(id)` per `data-model.md` §3
- [X] T004 [P] Create `supabase/migrations/20260808000004_seed_vodafone_cash_number.sql` — `INSERT INTO platform_settings (key, value) VALUES ('vodafone_cash_number', '<placeholder-number>') ON CONFLICT (key) DO NOTHING` per `data-model.md` §4
- [X] T005 [P] Create `supabase/migrations/20260808000005_create_topup_proofs_bucket.sql` — private Storage bucket `topup-proofs` (mirrors the existing `identity-documents` bucket migration's structure: bucket row + no public-read policy) per `data-model.md` §5
- [X] T006 Apply all Phase 1 migrations: `supabase db push` (run after T001–T005 are complete); verify `wallet_topup_requests` exists with correct indexes/RLS, `profiles`/`admin_audit_logs` have their new columns, the `vodafone_cash_number` row exists in `platform_settings`, and the `topup-proofs` bucket exists and is private

**Checkpoint**: All new schema objects exist in the database with correct constraints, indexes, and RLS policies.

---

## Phase 2: Foundational (Shared Backend Infrastructure)

**Purpose**: Core Pydantic schemas and shared service-module scaffolding that ALL three user stories depend on. No user story work can begin until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 Create `services/api/app/models/wallet_topup.py` — Pydantic schemas mirroring `models/wallet.py`'s style: `TopupSettingsResponse` (`vodafone_cash_number: str`); `TopupSubmitResponse` (`id`, `status`, `amount_egp: Decimal`, `payment_reference`, `created_at`); `TopupHistoryItem` + `TopupHistoryResponse` (`items`, `pagination`, `is_locked: bool`); `TopupCancelResponse` (`id`, `status`); `AdminTopupQueueItem` + `AdminTopupQueueResponse` (`total`, `page`, `items`); `AdminTopupApproveResponse` (`id`, `status`, `ledger_entry_id`, `new_balance_egp: Decimal`, `reviewed_by`, `reviewed_at`); `AdminTopupRejectRequest` (`reason: str`, non-empty) + `AdminTopupRejectResponse` (adds `driver_locked: bool`); `AdminTopupHistoryItem` + `AdminTopupHistoryResponse`; `AdminTopupUnlockResponse` (`driver_id`, `is_topup_locked`); all `Decimal` fields use `max_digits`/`decimal_places` constraints matching `wallet.py`
- [X] T008 Create `services/api/app/services/wallet_topup_service.py` — scaffold module with shared helpers used by every story: `_get_vodafone_cash_number(conn) -> str` (mirrors `verification_service._get_support_email()` exactly: read `platform_settings` row by key, same fallback-if-missing behavior); `_is_topup_locked(conn, driver_id) -> bool` (reads `profiles.is_topup_locked`); `_rejected_count_since_reset(conn, driver_id) -> int` (per `research.md` §5: `SELECT count(*) FROM wallet_topup_requests WHERE driver_id = $1 AND status = 'REJECTED' AND created_at > COALESCE((SELECT topup_lock_reset_at FROM profiles WHERE id = $1), '-infinity')`)
- [X] T009 [P] Extend `services/api/app/services/fcm_service.py` — add `wallet_topup_approved` and `wallet_topup_rejected` entries to `_NOTIFICATION_TEMPLATES` with `en`/`ar` title/body tuples (per `research.md` §9), matching the existing dict shape used by `rating_prompt`/`moderation_outcome`
- [X] T010 [P] Extend `services/api/app/services/audit_service.py` `append_log()` — add an optional `topup_request_id: str | None = None` parameter, included in the inserted `admin_audit_logs` row alongside the existing optional `submission_id`/`report_id` parameters (per `research.md` §8); no change to required parameters or the `action_type` CHECK values used

**Checkpoint**: `wallet_topup.py` schemas and `wallet_topup_service.py`'s shared helpers are importable with no errors; `fcm_service` and `audit_service` extensions don't break any existing caller (both new parameters are optional/additive).

---

## Phase 3: User Story 1 — Driver Submits a Top-Up Request (Priority: P1) 🎯 MVP

**Goal**: A driver can view the platform's Vodafone Cash number and submit a top-up request (amount, reference, screenshot) that lands as `PENDING` without touching their wallet balance.

**Independent Test**: `quickstart.md` Scenario 1 — submit a request, verify `status = PENDING` and wallet balance unchanged; verify FR-004 (409 on a second pending submission), FR-005 (409 on duplicate reference).

### Implementation for User Story 1

- [ ] T011 [US1] Implement `services/api/app/services/wallet_topup_service.get_settings(conn) -> dict` in `services/api/app/services/wallet_topup_service.py` — calls `_get_vodafone_cash_number()` (T008)
- [ ] T012 [US1] Implement `services/api/app/services/wallet_topup_service.submit_request(conn, driver_id, amount_egp, payment_reference, screenshot_file) -> dict` in `services/api/app/services/wallet_topup_service.py` — validates `amount_egp > 0` and non-empty `payment_reference` (FR-003); checks `_is_topup_locked()` (T008) and raises a `submission_locked` error including `_get_vodafone_cash_number`'s sibling support-email setting if locked (FR-014/FR-015); checks for an existing `PENDING` row for the driver and raises `pending_request_exists` if found (FR-004, backed by T001's unique index for the race case); uploads the screenshot via `storage_service.upload_file()` to the `topup-proofs` bucket at `{driver_id}/{request_id}.{ext}` (per `data-model.md` §5); inserts the `wallet_topup_requests` row with `status='PENDING'`; catches the T001 unique-violation on `payment_reference` and re-raises as `duplicate_payment_reference` (`error_code = DUPLICATE_PAYMENT_REFERENCE`, FR-005)
- [ ] T013 [US1] Create `services/api/app/api/wallet_topup/router.py` — `GET /wallet/topup/settings` (any authenticated driver, calls T011) and `POST /wallet/topup` (`get_current_driver`-gated, `multipart/form-data`, calls T012); map service-layer errors to HTTP 422/403/409 per `contracts/api.md`'s driver-facing error table
- [ ] T014 [US1] Register the new router in `services/api/app/main.py` — `app.include_router(wallet_topup_router, prefix="/wallet/topup", tags=["wallet-topup"])` alongside the existing `wallet` router registration
- [ ] T015 [P] [US1] Create `apps/main/src/lib/api/wallet-topup.ts` — `getSettings(token)` and `submitRequest(token, formData)` client functions, mirroring `apps/main/src/lib/api/wallet.ts`'s fetch/error-handling pattern
- [ ] T016 [P] [US1] Add `driver.walletTopup.*` translation keys to `apps/main/messages/en.json` and `apps/main/messages/ar.json` — form labels, the Vodafone Cash number label, and validation/error messages for `pending_request_exists`/`duplicate_payment_reference`/`submission_locked` (FR-018; both locales required, no relying on the FR-011 fallback from `017-arabic-rtl-localization`)
- [ ] T017 [US1] Create `apps/main/src/app/(driver)/wallet/topup/page.tsx` — client component mirroring `apps/main/src/app/(driver)/wallet/page.tsx`'s structure (`useTranslations("driver.walletTopup")`, Supabase session token via existing `createClient()`/`getToken()` helper); displays the Vodafone Cash number (T015's `getSettings`), a form (amount, reference, screenshot file input), submits via T015's `submitRequest`, shows the resulting "Pending review" state; uses the existing locale-aware currency formatter from `017-arabic-rtl-localization` for the entered amount (FR-019)

**Checkpoint**: A driver can load the top-up screen, see the Vodafone Cash number, and submit a request that appears as `PENDING`; SC-001 is verifiable end-to-end via manual UI testing plus `quickstart.md` Scenario 1's curl/SQL checks.

---

## Phase 4: User Story 2 — Admin Reviews and Approves/Rejects a Top-Up Request (Priority: P2)

**Goal**: An admin can see pending requests oldest-first, approve one (crediting the wallet atomically through the existing `wallet_service` functions), or reject one with a mandatory reason — and unlock a driver who hit the resubmission cap.

**Independent Test**: `quickstart.md` Scenario 2 (approve: wallet credited exactly once, ledger entry linked, FR-011 blocks a repeat action, driver notified) and Scenario 3 Steps 1–3 (reject requires a reason). `quickstart.md` Scenario 4 (lockout + unlock) once T012's lock check (US1) and this phase's reject/unlock logic are both in place.

### Implementation for User Story 2

- [ ] T018 [US2] Implement `services/api/app/services/wallet_topup_service.list_pending_queue(conn, page, limit) -> dict` in `services/api/app/services/wallet_topup_service.py` — joins `wallet_topup_requests` (`status='PENDING'`, ordered `created_at ASC` per FR-008) with `profiles` for driver name/phone, and generates a signed screenshot URL via `storage_service.generate_signed_url()` for each item
- [ ] T019 [US2] Implement `services/api/app/services/wallet_topup_service.approve_request(conn, request_id, admin_id) -> dict` in `services/api/app/services/wallet_topup_service.py` — inside one `conn.transaction()`: `SELECT ... FOR UPDATE` the request row, raise `not_found`/`conflict` if missing/not-`PENDING` (FR-011); call `wallet_service.get_wallet_with_lock()`, `wallet_service.increment_balance()`, `wallet_service.insert_ledger_entry(entry_type="ADMIN_CREDIT", created_by=admin_id, note=f"wallet_topup_request:{request_id}")` — the exact same three calls used by `api/admin/wallet_router.py`'s existing `topup_wallet` endpoint, per `research.md` §1 (FR-009, NFR-006); update the request row to `status='APPROVED'`, `reviewed_by=admin_id`, `reviewed_at=now()`, `ledger_entry_id=<new entry id>`; set `profiles.topup_lock_reset_at = now()` for the driver (resets their rejection cycle per FR-014); call `audit_service.append_log(..., action_type='approved', topup_request_id=request_id)` (T010); call `fcm_service.send_push_notifications(conn, driver_id, 'wallet_topup_approved', {...})` (T009) after the transaction commits
- [ ] T020 [US2] Implement `services/api/app/services/wallet_topup_service.reject_request(conn, request_id, admin_id, reason) -> dict` in `services/api/app/services/wallet_topup_service.py` — validates `reason` is non-empty (FR-010); inside one `conn.transaction()`: `SELECT ... FOR UPDATE` the request row, raise `not_found`/`conflict` if missing/not-`PENDING` (FR-011); update to `status='REJECTED'`, `rejection_reason=reason`, `reviewed_by=admin_id`, `reviewed_at=now()`; call T008's `_rejected_count_since_reset()` — if the count reaches 3, set `profiles.is_topup_locked = TRUE` (FR-014) and include `driver_locked: true` in the response; call `audit_service.append_log(..., action_type='rejected', topup_request_id=request_id)` (T010); call `fcm_service.send_push_notifications(conn, driver_id, 'wallet_topup_rejected', {"reason": reason})` (T009) after commit
- [ ] T021 [US2] Implement `services/api/app/services/wallet_topup_service.list_review_history(conn, page, outcome, q) -> dict` and `unlock_driver(conn, driver_id, admin_id) -> dict` in `services/api/app/services/wallet_topup_service.py` — history joins reviewed (`APPROVED`/`REJECTED`) requests with `profiles.is_topup_locked` as `driver_is_locked`, optional `outcome`/`q` filters (per `contracts/api.md`'s `GET /admin/wallet-topup-requests/history`); `unlock_driver` sets `profiles.is_topup_locked = FALSE, topup_lock_reset_at = now()`, raises `conflict` if the driver isn't currently locked (per `contracts/api.md`), and calls `audit_service.append_log(..., action_type='unlocked')` (FR-016)
- [ ] T022 [US2] Create `services/api/app/api/admin/wallet_topup_router.py` — `GET /admin/wallet-topup-requests` (T018), `GET /admin/wallet-topup-requests/history` (T021), `POST /admin/wallet-topup-requests/{request_id}/approve` (T019), `POST /admin/wallet-topup-requests/{request_id}/reject` (T020), `POST /admin/wallet-topup-requests/drivers/{driver_id}/unlock` (T021); all `get_current_admin`-gated (FR-012); map service-layer errors to HTTP 400/403/404/409 per `contracts/api.md`'s admin error tables
- [ ] T023 [US2] Register the new admin router in `services/api/app/main.py` — `app.include_router(admin_wallet_topup_router, prefix="/admin/wallet-topup-requests", tags=["admin-wallet-topup"])` alongside the existing `admin/wallet_router.py` registration
- [ ] T024 [P] [US2] Create `apps/admin/src/lib/api/admin-wallet-topup.ts` — `getQueue(token, page)`, `getHistory(token, page, outcome?, q?)`, `approve(token, id)`, `reject(token, id, reason)`, `unlock(token, driverId)` client functions, mirroring `apps/admin/src/lib/api/admin-verification.ts`'s exact fetch/auth-header/error-handling pattern
- [ ] T025 [US2] Create `apps/admin/src/app/(dashboard)/wallet-topup/page.tsx` — pending queue UI mirroring `apps/admin/src/app/(dashboard)/verification/page.tsx` (table of driver name/phone/amount/reference/screenshot/submitted-at, oldest-first, approve/reject actions with a mandatory-reason prompt on reject); English-only, `en-EG` `Intl` formatting for amounts/timestamps (FR-019)
- [ ] T026 [US2] Create `apps/admin/src/app/(dashboard)/wallet-topup/history/page.tsx` — reviewed-requests list with an inline "Unlock for re-submission" button shown when `driver_is_locked` is true, mirroring `apps/admin/src/app/(dashboard)/verification/history/page.tsx`'s `handleUnlock` pattern exactly

**Checkpoint**: An admin can approve a pending request (wallet credited exactly once, driver notified), reject one with a reason, and unlock a driver who was locked after 3 rejections; SC-002/SC-003/SC-005/SC-006/SC-007 are verifiable via `quickstart.md` Scenarios 2 and 4.

---

## Phase 5: User Story 3 — Driver Views Top-Up History and Cancels a Pending Request (Priority: P3)

**Goal**: A driver can see all their own top-up requests (any status) and cancel a still-`PENDING` one, freeing them to resubmit immediately.

**Independent Test**: `quickstart.md` Scenario 3 — list history with mixed statuses, cancel a pending request, verify the reused `payment_reference` becomes submittable again (FR-005) and a new submission is no longer blocked by FR-004.

### Implementation for User Story 3

- [ ] T027 [US3] Implement `services/api/app/services/wallet_topup_service.list_driver_history(conn, driver_id, page, per_page) -> dict` in `services/api/app/services/wallet_topup_service.py` — `wallet_topup_requests` filtered to `driver_id`, newest-first (per `data-model.md`'s `idx_topup_driver_history`), includes `is_locked` (T008's `_is_topup_locked`) in the response per `contracts/api.md`
- [ ] T028 [US3] Implement `services/api/app/services/wallet_topup_service.cancel_request(conn, request_id, driver_id) -> dict` in `services/api/app/services/wallet_topup_service.py` — raises `forbidden` if the row's `driver_id` doesn't match the caller (FR-006); raises `not_cancellable` if `status != 'PENDING'`; else updates to `status='CANCELLED'`
- [ ] T029 [US3] Add `GET /wallet/topup` and `POST /wallet/topup/{request_id}/cancel` to `services/api/app/api/wallet_topup/router.py` (both `get_current_driver`-gated, calling T027/T028); map errors to HTTP 403/409 per `contracts/api.md`
- [ ] T030 [P] [US3] Add `getHistory(token, page)` and `cancelRequest(token, requestId)` to `apps/main/src/lib/api/wallet-topup.ts` (T015)
- [ ] T031 [US3] Create `apps/main/src/app/(driver)/wallet/topup/history/page.tsx` — lists the driver's own requests (amount, reference, status, rejection reason when present, timestamps via the locale-aware formatter per FR-019) with a cancel action on `PENDING` rows, mirroring `apps/main/src/app/(driver)/wallet/page.tsx`'s visibility-change-triggered refetch pattern; add remaining `driver.walletTopup.history.*` / cancellation-confirmation keys to `apps/main/messages/{en,ar}.json` (T016, FR-018)

**Checkpoint**: All three user stories work independently and together; `quickstart.md` Scenarios 1–5 all pass.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and consistency pass across all three stories.

- [ ] T032 [P] Confirm `apps/main/src/app/(driver)/wallet/page.tsx` links to the new `/wallet/topup` screen (e.g., a "Top Up" button/link), so the new flow is reachable from the existing wallet view
- [ ] T033 Run all 5 `quickstart.md` scenarios end-to-end against a locally migrated database and confirm every expected HTTP status/body/SQL check matches
- [ ] T034 Verify NFR-001/NFR-004 informally (endpoint response times, queue render time) are reasonable under local testing; no dedicated load-testing infra is in scope for this feature

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T007's models don't strictly need the DB, but T008's helpers query tables created in Phase 1) — BLOCKS all user stories
- **User Stories (Phase 3–5)**: All depend on Foundational (Phase 2) completion
  - US1 (Phase 3) has no dependency on US2/US3 — can be built and demoed alone (MVP)
  - US2 (Phase 4) depends on US1 existing requests to review, but its own code (T018–T026) has no hard code dependency on US1's files beyond the shared T007/T008 foundation
  - US3 (Phase 5) depends on US1's `submit_request`/router existing (to have something to list/cancel) but its code (T027–T031) is otherwise independent of US2
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each Phase

- Backend service functions before backend router wiring
- Backend router registration before frontend API client work (frontend needs real endpoints to call, though the client file itself can be scaffolded in parallel)
- Frontend API client before frontend page component
- Translation keys ([P] with backend work) before/alongside the page component that uses them

### Parallel Opportunities

- All Phase 1 migration files (T001–T005) can be written in parallel — different files, no dependencies
- T009 and T010 (Phase 2) can run in parallel with each other and with T007/T008 — different files
- Within each user story phase, the frontend API-client task is marked [P] since it touches a different file than the backend router task it pairs with (the client can be written against the documented contract before the backend is finished, then verified once both exist)

---

## Parallel Example: Phase 1 (Setup)

```bash
Task: "Create supabase/migrations/20260808000001_create_wallet_topup_requests.sql"
Task: "Create supabase/migrations/20260808000002_add_topup_lock_to_profiles.sql"
Task: "Create supabase/migrations/20260808000003_add_topup_request_to_audit_logs.sql"
Task: "Create supabase/migrations/20260808000004_seed_vodafone_cash_number.sql"
Task: "Create supabase/migrations/20260808000005_create_topup_proofs_bucket.sql"
```

## Parallel Example: Phase 3 (US1)

```bash
Task: "Create apps/main/src/lib/api/wallet-topup.ts"
Task: "Add driver.walletTopup.* keys to apps/main/messages/en.json and ar.json"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `quickstart.md` Scenario 1 independently
5. Deploy/demo if ready — drivers can submit requests even before the admin queue exists (they'll just accumulate as `PENDING`)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 → Validate with Scenario 1 → Demo (MVP!)
3. Add US2 → Validate with Scenarios 2 and 4 → Demo (requests can now actually be approved/rejected)
4. Add US3 → Validate with Scenario 3 → Demo (drivers get self-service history/cancel)
5. Polish (Phase 6) → Validate with all of `quickstart.md`

### Solo Developer Strategy

Given the dependency chain (US2 needs US1's requests to review, US3 needs US1's submit path to exist),
build in priority order P1 → P2 → P3 exactly as phased above rather than parallelizing across stories.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- FR-009/NFR-006 (T019) is the single highest-risk task — it must reuse `wallet_service`'s existing functions inside one transaction, not introduce a parallel crediting path; verify against `quickstart.md` Scenario 2 Step 3 before considering Phase 4 done
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
