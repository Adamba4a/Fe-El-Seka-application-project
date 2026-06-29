# Quickstart Validation Guide: Financial System (Phase 8)

**Branch**: `011-financial-system` | **Date**: 2026-06-29

This guide covers runnable validation scenarios that prove the financial system works end-to-end. See [data-model.md](data-model.md) for schema details and [contracts/api.md](contracts/api.md) for full request/response shapes.

---

## Prerequisites

1. Phase 7 deployed and all existing tests passing (ride completion endpoint functional)
2. Phase 8 migrations applied:
   ```bash
   supabase db push
   # or: supabase migration up
   ```
3. Backend running locally:
   ```bash
   cd services/api && uvicorn app.main:app --reload --port 8000
   ```
4. Test fixtures available (or use Supabase Studio to seed):
   - A verified driver user (`driver_user_id`)
   - An admin user (`admin_user_id`) with admin role
   - A completed ride associated with the driver

---

## Scenario 1 — Commission Deduction on Ride Completion

Validates spec User Story 1 / SC-001 / SC-002.

**Setup**: Create a ride with 4 seats and `fuel_cost_egp = 40.00`. Confirm 2 bookings on the ride. Ensure the driver has ≥ 8.00 EGP available balance (top up if needed using Scenario 2 first).

**Step 1 — Verify reservation created at ride creation**:
```sql
SELECT reserved_amount_egp FROM commission_reservations WHERE ride_id = '<ride_id>';
-- Expected: 8.00
```
```sql
SELECT balance_egp, reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: reserved_egp includes 8.00
```

**Step 2 — Complete the ride**:
```bash
curl -X POST http://localhost:8000/rides/<ride_id>/complete \
  -H "Authorization: Bearer <driver_jwt>"
```
Expected: HTTP 200

**Step 3 — Verify commission settled**:
```sql
-- Reservation deleted
SELECT COUNT(*) FROM commission_reservations WHERE ride_id = '<ride_id>';
-- Expected: 0

-- Two COMMISSION_DEBIT entries of 2.00 EGP each (40 × 0.20 / 4)
SELECT type, amount_egp, booking_id FROM driver_ledger_entries
WHERE ride_id = '<ride_id>' ORDER BY created_at;
-- Expected: 2 rows, type=COMMISSION_DEBIT, amount_egp=2.00

-- Wallet balance decreased by 4.00; reserved_egp decreased by 8.00
SELECT balance_egp, reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: balance_egp decreased by 4.00; reserved_egp decreased by 8.00
```

**Step 4 — Verify atomicity** (optional negative test): Inject a failure inside `deduct_commission()` (e.g., temporary DB error). Verify ride stays `in_progress` and no ledger entries are created.

---

## Scenario 2 — Admin Top-Up

Validates spec User Story 2 / SC-004.

```bash
curl -X POST http://localhost:8000/admin/drivers/<driver_id>/wallet/topup \
  -H "Authorization: Bearer <admin_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"amount_egp": "200.00", "note": "Bank transfer received"}'
```

**Expected response** (HTTP 200):
```json
{ "new_balance_egp": "200.00", "amount_credited_egp": "200.00" }
```

**Verify in DB**:
```sql
SELECT type, amount_egp, created_by, note FROM driver_ledger_entries
WHERE driver_id = '<driver_id>' ORDER BY created_at DESC LIMIT 1;
-- Expected: type=ADMIN_CREDIT, amount_egp=200.00, created_by=<admin_user_id>

SELECT balance_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: 200.00
```

**Negative test — non-admin cannot top up**:
```bash
curl -X POST http://localhost:8000/admin/drivers/<driver_id>/wallet/topup \
  -H "Authorization: Bearer <driver_jwt>" \
  -d '{"amount_egp": "50.00"}'
# Expected: HTTP 403
```

---

## Scenario 3 — Driver Views Wallet

Validates spec User Story 3.

```bash
curl http://localhost:8000/drivers/me/wallet \
  -H "Authorization: Bearer <driver_jwt>"
```

**Expected**: HTTP 200 with `balance_egp`, `reserved_egp`, `available_egp`, and `entries` array ordered `created_at DESC`.

**Verify available balance math**:
```
available_egp = balance_egp - reserved_egp
```
Both values must be non-negative and consistent with the DB.

**Negative test — driver cannot access another driver's wallet**:
```bash
curl http://localhost:8000/drivers/<other_driver_id>/wallet \
  -H "Authorization: Bearer <driver_jwt>"
# Expected: HTTP 403 or 404
```

---

## Scenario 4 — Balance Enforcement at Ride Creation

Validates spec User Story 4 / SC-005.

**Setup**: Set driver wallet to exactly 10.00 EGP (one top-up of 10.00, or adjust to reach this).

**Step 1 — Create Ride 1 (fuel_cost = 20.00 EGP, commission = 4.00 EGP)**:
```bash
curl -X POST http://localhost:8000/rides/ \
  -H "Authorization: Bearer <driver_jwt>" \
  -H "Content-Type: application/json" \
  -d '{ ... ride payload with route resulting in fuel_cost_egp ≈ 20.00 ... }'
# Expected: HTTP 201; CommissionReservation of 4.00 created
```

```sql
SELECT balance_egp, reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: balance_egp=10.00, reserved_egp=4.00 → available=6.00
```

**Step 2 — Attempt Ride 2 (fuel_cost = 40.00 EGP, commission = 8.00 EGP > 6.00 available)**:
```bash
curl -X POST http://localhost:8000/rides/ \
  -H "Authorization: Bearer <driver_jwt>" \
  -d '{ ... ride payload with fuel_cost_egp ≈ 40.00 ... }'
# Expected: HTTP 422
```

**Expected 422 body**:
```json
{
  "error_code": "INSUFFICIENT_WALLET_BALANCE",
  "detail": {
    "available_egp": "6.00",
    "required_commission_egp": "8.00"
  }
}
```

**Step 3 — Create Ride 2 (fuel_cost = 25.00 EGP, commission = 5.00 EGP ≤ 6.00 available)**:
```bash
# Expected: HTTP 201; available balance drops to 1.00 EGP
```

**Step 4 — Cancel Ride 1; verify reservation released**:
```bash
curl -X POST http://localhost:8000/rides/<ride1_id>/cancel \
  -H "Authorization: Bearer <driver_jwt>"
```
```sql
SELECT reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: decreased by 4.00 (Ride 1's reservation); available now 5.00 EGP
```

---

## Scenario 5 — Concurrent Ride Creation (Race Condition Test)

Validates NFR-008 / SC-005.

**Setup**: Driver with 10.00 EGP. Two simultaneous ride creation requests, each requiring 6.00 EGP commission.

**Run**: Submit both requests at the same time (e.g., via parallel `curl` or an integration test with two concurrent coroutines).

**Expected**: Exactly one request succeeds (HTTP 201); the other returns HTTP 422 with `INSUFFICIENT_WALLET_BALANCE`. No over-commitment.

**Verify**:
```sql
SELECT COUNT(*) FROM commission_reservations WHERE driver_id = '<driver_id>';
-- Expected: 1 (only one reservation created)

SELECT reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: 6.00 (one reservation only)
```

---

## Scenario 6 — Ledger Immutability

Validates NFR-005 / SC-003.

```bash
# Attempt to UPDATE a ledger entry directly via the app role connection
psql "$DATABASE_URL" -c "UPDATE driver_ledger_entries SET amount_egp = 0 WHERE id = '<entry_id>';"
# Expected: ERROR: permission denied for table driver_ledger_entries

psql "$DATABASE_URL" -c "DELETE FROM driver_ledger_entries WHERE id = '<entry_id>';"
# Expected: ERROR: permission denied for table driver_ledger_entries
```

---

## Scenario 7 — Admin Corrective Debit (Adjust)

Validates FR-014.

**Setup**: Driver balance = 50.00 EGP, reserved = 8.00 EGP, available = 42.00 EGP.

**Try to debit 45.00 EGP (exceeds available)**:
```bash
curl -X POST http://localhost:8000/admin/drivers/<driver_id>/wallet/adjust \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"amount_egp": "45.00", "note": "test"}'
# Expected: HTTP 422 — "Maximum allowable debit is 42.00 EGP"
```

**Debit exactly 42.00 EGP (at the cap)**:
```bash
curl -X POST http://localhost:8000/admin/drivers/<driver_id>/wallet/adjust \
  -H "Authorization: Bearer <admin_jwt>" \
  -d '{"amount_egp": "42.00", "note": "reversal of erroneous top-up"}'
# Expected: HTTP 200; new_balance_egp = 8.00; new_available_egp = 0.00
```

```sql
SELECT balance_egp, reserved_egp FROM driver_wallets WHERE driver_id = '<driver_id>';
-- Expected: balance_egp=8.00, reserved_egp=8.00 → available=0.00
```

---

## Integrity Check (SC-006)

Run after any set of operations to verify all three wallet equations hold:

```sql
-- Check 1: balance_egp matches ledger sum
SELECT
  w.driver_id,
  w.balance_egp AS stored_balance,
  COALESCE(SUM(CASE WHEN e.type = 'ADMIN_CREDIT' THEN e.amount_egp
                    WHEN e.type IN ('COMMISSION_DEBIT', 'ADMIN_DEBIT') THEN -e.amount_egp
               END), 0) AS computed_balance,
  w.balance_egp - COALESCE(SUM(CASE WHEN e.type = 'ADMIN_CREDIT' THEN e.amount_egp
                                     WHEN e.type IN ('COMMISSION_DEBIT', 'ADMIN_DEBIT') THEN -e.amount_egp
                                END), 0) AS discrepancy
FROM driver_wallets w
LEFT JOIN driver_ledger_entries e ON e.driver_id = w.driver_id
GROUP BY w.driver_id, w.balance_egp
HAVING ABS(w.balance_egp - COALESCE(SUM(...), 0)) > 0.00;
-- Expected: 0 rows (no discrepancies)

-- Check 2: reserved_egp matches active reservations
SELECT
  w.driver_id,
  w.reserved_egp AS stored_reserved,
  COALESCE(SUM(cr.reserved_amount_egp), 0) AS computed_reserved
FROM driver_wallets w
LEFT JOIN commission_reservations cr ON cr.wallet_id = w.id
GROUP BY w.driver_id, w.reserved_egp
HAVING w.reserved_egp != COALESCE(SUM(cr.reserved_amount_egp), 0);
-- Expected: 0 rows

-- Check 3: No orphaned reservations
SELECT cr.id, cr.ride_id, r.status
FROM commission_reservations cr
JOIN rides r ON r.id = cr.ride_id
WHERE r.status IN ('completed', 'cancelled');
-- Expected: 0 rows
```
