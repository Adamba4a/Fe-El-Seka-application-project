# Quickstart Validation Guide: Manual Wallet Top-Up via Vodafone Cash

**Branch**: `018-wallet-topup-requests` | **Date**: 2026-08-08

This guide covers runnable validation scenarios that prove the feature works end-to-end. See
[data-model.md](data-model.md) for schema details and [contracts/api.md](contracts/api.md) for full
request/response shapes.

---

## Prerequisites

1. `011-financial-system` deployed and functional (driver wallet + `ADMIN_CREDIT` top-up path exist and work).
2. `018` migrations applied:
   ```bash
   supabase db push
   ```
3. Backend running locally:
   ```bash
   cd services/api && uvicorn app.main:app --reload --port 8000
   ```
4. A verified driver user (`driver_jwt`, `driver_id`) and an admin user (`admin_jwt`).
5. `platform_settings` seeded with a `vodafone_cash_number` row.

---

## Scenario 1 — Driver Submits a Top-Up Request (US1, SC-001)

**Step 1 — Read the Vodafone Cash number**:
```bash
curl http://localhost:8000/wallet/topup/settings -H "Authorization: Bearer <driver_jwt>"
```
Expected: `{ "vodafone_cash_number": "..." }`

**Step 2 — Submit a request**:
```bash
curl -X POST http://localhost:8000/wallet/topup \
  -H "Authorization: Bearer <driver_jwt>" \
  -F "amount_egp=200.00" \
  -F "payment_reference=TXN-QS-001" \
  -F "screenshot=@./sample.jpg;type=image/jpeg"
```
Expected: HTTP 201, `status = "PENDING"`.

**Step 3 — Verify wallet unchanged**:
```sql
SELECT balance_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: unchanged from before Step 2
```

**Step 4 — Verify FR-004 (one pending at a time)**:
```bash
curl -X POST http://localhost:8000/wallet/topup \
  -H "Authorization: Bearer <driver_jwt>" \
  -F "amount_egp=50.00" -F "payment_reference=TXN-QS-002" -F "screenshot=@./sample.jpg;type=image/jpeg"
```
Expected: HTTP 409 `pending_request_exists`.

**Step 5 — Verify FR-005 (duplicate reference)**: submit again as a *different* driver with
`payment_reference=TXN-QS-001`. Expected: HTTP 409, `error_code = DUPLICATE_PAYMENT_REFERENCE`.

---

## Scenario 2 — Admin Approves a Request (US2, SC-002, SC-003, NFR-006)

**Step 1 — View the queue**:
```bash
curl http://localhost:8000/admin/wallet-topup-requests -H "Authorization: Bearer <admin_jwt>"
```
Expected: the request from Scenario 1, Step 2.

**Step 2 — Approve it**:
```bash
curl -X POST http://localhost:8000/admin/wallet-topup-requests/<request_id>/approve \
  -H "Authorization: Bearer <admin_jwt>"
```
Expected: HTTP 200, `status = "APPROVED"`, `ledger_entry_id` present.

**Step 3 — Verify the credit landed exactly once**:
```sql
SELECT balance_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: increased by exactly 200.00

SELECT type, amount_egp FROM driver_ledger_entries
WHERE id = (SELECT ledger_entry_id FROM wallet_topup_requests WHERE id = '<request_id>');
-- Expected: one row, type='ADMIN_CREDIT', amount_egp=200.00
```

**Step 4 — Verify FR-011 (no repeat action)**:
```bash
curl -X POST http://localhost:8000/admin/wallet-topup-requests/<request_id>/approve \
  -H "Authorization: Bearer <admin_jwt>"
```
Expected: HTTP 409 `conflict`.

**Step 5 — Verify driver notification (FR-017 / SC-006)**: confirm a push notification was
dispatched to `driver_id` with `event_type = wallet_topup_approved` (check `fcm_service` logs or a
registered test device token).

---

## Scenario 3 — Admin Rejects, Driver Self-Cancels, Reference Reuse (US2, US3, FR-005, FR-007)

**Step 1**: Submit a second request as the driver with `payment_reference=TXN-QS-003`.

**Step 2 — Reject without a reason** (FR-010 guard):
```bash
curl -X POST http://localhost:8000/admin/wallet-topup-requests/<request_id_2>/reject \
  -H "Authorization: Bearer <admin_jwt>" -H "Content-Type: application/json" -d '{}'
```
Expected: HTTP 400 `validation_error`.

**Step 3 — Reject with a reason**:
```bash
curl -X POST http://localhost:8000/admin/wallet-topup-requests/<request_id_2>/reject \
  -H "Authorization: Bearer <admin_jwt>" -H "Content-Type: application/json" \
  -d '{"reason": "Amount mismatch"}'
```
Expected: HTTP 200, `status = "REJECTED"`.

**Step 4 — Verify reference reusable**: submit a third request reusing `payment_reference=TXN-QS-003`.
Expected: HTTP 201 (rejected requests' references are not "in use", FR-005).

**Step 5 — Cancel the new pending request** (FR-007):
```bash
curl -X POST http://localhost:8000/wallet/topup/<request_id_3>/cancel -H "Authorization: Bearer <driver_jwt>"
```
Expected: HTTP 200, `status = "CANCELLED"`. Driver may immediately submit a new request (FR-004 no longer blocks them).

---

## Scenario 4 — Resubmission Cap and Admin Unlock (FR-014/FR-015/FR-016, SC-007)

**Step 1**: Drive a driver's request through `REJECTED` three times in a row (submit → reject, ×3,
using fresh `payment_reference` values each time).

**Step 2 — Verify lockout**:
```bash
curl -X POST http://localhost:8000/wallet/topup \
  -H "Authorization: Bearer <driver_jwt>" \
  -F "amount_egp=10.00" -F "payment_reference=TXN-QS-LOCK" -F "screenshot=@./sample.jpg;type=image/jpeg"
```
Expected: HTTP 403 `submission_locked`, body includes `support_email`.

**Step 3 — Admin unlocks**:
```bash
curl -X POST http://localhost:8000/admin/wallet-topup-requests/drivers/<driver_id>/unlock \
  -H "Authorization: Bearer <admin_jwt>"
```
Expected: HTTP 200, `is_topup_locked = false`.

**Step 4 — Verify driver can submit again**: repeat Step 2's request. Expected: HTTP 201.

---

## Scenario 5 — Localization (FR-018, FR-019)

1. Set the driver's `apps/main` locale to Arabic. Load the top-up request screen and history screen.
   Expected: all labels/errors render in Arabic (no raw translation keys, no silent English fallback
   for this feature's own strings); layout mirrors RTL.
2. Trigger an approval and a rejection while the driver's device locale is Arabic. Expected: push
   notification title/body are in Arabic.
3. Load the admin review queue in `apps/admin`. Expected: English only, `en-EG` `Intl` formatting —
   unchanged from the rest of the Admin Panel.
