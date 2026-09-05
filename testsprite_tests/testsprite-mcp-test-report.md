
# TestSprite AI Testing Report (MCP) — Backend, Consolidated (TC001–TC020)

---

## 1️⃣ Document Metadata
- **Project Name:** Fe El Seka app (Triplyy)
- **Date:** 2026-09-05
- **Scope:** Backend (port 8000) — Rides/OSRM, Bookings, Ratings, Reports, Admin Moderation, Admin Verification, Admin Wallet Top-up, Admin Withdrawal, Admin Sponsored Groups, Admin Loyalty, Admin Driver Wallet
- **Test accounts used (disposable, TestSprite-only):** driver `2b61b48e-1ec2-4cb3-b2c1-750d0f563bd6`, passenger `9e5b16eb-2edc-48f5-9ca3-5f7d3b0f240f`, admin `57b52643-a8c6-4150-b27e-8767187d2030` (`admin@triplyy.com`). No real/seed accounts were touched.
- **Prepared by:** TestSprite AI Team (execution) + Claude (diagnosis, fixture staging, consolidation)

---

## 2️⃣ Requirement Validation Summary

### Rides / OSRM
#### TC001 — Create ride with active vehicle and org-verified profile
- **Status:** ✅ Passed (via TestSprite pipeline)

### Bookings
#### TC002 — `POST /api/v1/bookings` create booking
- **Status:** ✅ Passed
#### TC003 — `GET /api/v1/bookings` list mine
- **Status:** ✅ Passed
#### TC004 — `GET /api/v1/bookings/{id}` detail
- **Status:** ✅ Passed
#### TC005 — `POST /api/v1/bookings/{id}/cancel`
- **Status:** ✅ Passed
#### TC006 — `POST /api/v1/bookings/{id}/seats` add seats
- **Status:** ✅ Passed

### Ratings
#### TC007 — `POST /api/v1/ratings` submit rating
- **Status:** ❌ Failed in TestSprite's generated test run, but **backend confirmed working**
- **Root cause:** TestSprite corrupted the passenger JWT while copying it into generated Python (dropped a "." separator, mangling adjacent base64 chars — confirmed byte-for-byte), causing a spurious 401. The generated test also asserted on field name `"rating"` instead of the actual API field `"stars"`.
- **Manual verification:** direct call to `POST /api/v1/ratings` with `{"ride_id","booking_id","stars":5,"comment"}` returns `201 {"rating_id","booking_id","revealed":false}` as designed.
- **Verdict:** TestSprite tooling artifact, not a backend bug.

### Reports
#### TC008 — `POST /api/v1/reports` submit report
- **Status:** ✅ Passed

### Admin Wallet Top-up
#### TC010 — Submit + admin approve
- **Status:** ✅ Passed
#### TC011 — Submit + admin reject
- **Status:** ❌ Failed only on a follow-on unlock assertion (submit=201, reject=200 both passed)
- **Root cause:** Test instruction told TestSprite to call `POST /api/admin/wallet-topup-requests/drivers/{id}/unlock` unconditionally, but that endpoint intentionally returns `409 {"error":"conflict","message":"Driver is not locked"}` unless 3 consecutive rejections already locked the driver (`wallet_topup_service.py:585-600`). This disposable driver only had 1 rejection in this run.
- **Verdict:** Correct, intentional backend behavior; not a bug. Core submit+reject flow verified passing.

### Admin Withdrawal
#### TC012 — Submit + admin approve
- **Status:** ✅ Passed
#### TC013 — Submit + admin reject
- **Status:** ✅ Passed

### Admin Sponsored Groups
#### TC009 — Create / upgrade sponsored group
- **Status:** ✅ Passed
#### TC014 — Create + add-funds
- **Status:** ❌ Failed only on a balance-field assertion (create=201, add-funds=200 both passed)
- **Root cause:** Generated test guessed 4 possible response field names (`funded_balance_egp`, `balance_egp`, `balance`, `current_balance`) for the add-funds response, none of which matched the real field. Confirmed via source (`services/api/app/models/group.py:125-127`, `AddFundsResponse`) that the actual field is `new_funded_balance_egp`.
- **Verdict:** Test field-name-guessing miss, not a backend bug. Endpoint itself verified functioning (200, cleanup deleted group as expected).

### Admin Loyalty
#### TC015 — Loyalty catalog create/update/delete
- **Status:** ✅ Passed
#### TC016 — Loyalty redeem + admin fulfill
- **Status:** ✅ Passed

### Admin Driver Wallet
#### TC009(dup)/TC008 — `GET /api/admin/users/{id}` driver wallet balance
- **Status:** ✅ Passed — confirmed served from embedded `driver_wallets` fields on the admin user-detail endpoint (no separate standalone endpoint exists; this is by design).

### Admin Moderation
#### TC017 — Mark under review + resolve (dismiss)
- **Status:** ✅ Passed
#### TC018 — Mark under review + resolve (suspend) + reinstate
- **Status:** ✅ Passed

### Admin Verification
#### TC019 — Submit + admin approve
- **Status:** ❌ Failed in TestSprite's generated test run, but **backend confirmed working**
- **Root cause:** TestSprite's internal double-execution behavior submitted twice; the second internal pass hit the intentional "You already have a submission under review" guard (`verification_service.py:92-107`) since the first pass's submission was still `pending_review`.
- **Manual verification:** `POST /api/verification/submit` (multipart, driver token) → `201 pending_review, attempt_number=1`; `POST /api/admin/verification/{id}/approve` (admin token) → `200 {"new_status":"verified"}`.
- **Verdict:** TestSprite tooling artifact, not a backend bug.

#### TC020 — 3× submit+reject cycle → lock → admin unlock
- **Status:** ❌ Failed in TestSprite's generated test run, but **backend confirmed working**
- **Root cause:** Same double-execution artifact, compounded by `verification_submissions.attempt_number` being hard-capped at 3 by a DB CHECK constraint (`attempt_number >= 1 AND attempt_number <= 3`). Repeated TestSprite runs against the same disposable driver account exhausted all 3 attempt slots across earlier attempts in this session, so later runs permanently hit `409 "Submission could not be recorded"` on insert — not a transient race, so no retry/backoff could ever succeed. Fixed by clearing the disposable driver's old `verification_submissions` rows (and their `admin_audit_logs` references) before re-testing.
- **Manual verification (full 3-cycle):**
  1. submit → `201 attempt_number=1` → admin reject → `200 is_locked=false`
  2. submit → `201 attempt_number=2` → admin reject → `200 is_locked=false`
  3. submit → `201 attempt_number=3` → admin reject → `200 is_locked=true`
  4. `POST /api/admin/verification/users/{id}/unlock` → `200 is_submission_locked=false`
- **Verdict:** TestSprite tooling artifact (double-execution + attempt-slot exhaustion from repeated test runs), not a backend bug. Full lock/unlock cycle confirmed working end-to-end.

---

## 3️⃣ Coverage & Matching Metrics

| Requirement Area        | Total Tests | ✅ Passed | ❌ Failed (tooling artifact, backend verified OK) |
|--------------------------|:-----------:|:---------:|:--------------------------------------------------:|
| Rides / OSRM             | 1           | 1         | 0 |
| Bookings                 | 5           | 5         | 0 |
| Ratings                  | 1           | 0         | 1 |
| Reports                  | 1           | 1         | 0 |
| Admin Wallet Top-up      | 2           | 1         | 1 |
| Admin Withdrawal         | 2           | 2         | 0 |
| Admin Sponsored Groups   | 2           | 1         | 1 |
| Admin Loyalty            | 2           | 2         | 0 |
| Admin Driver Wallet      | 1           | 1         | 0 |
| Admin Moderation         | 2           | 2         | 0 |
| Admin Verification       | 2           | 0         | 2 |
| **Total**                | **21**      | **16**    | **5** |

All 5 "failed" rows above were root-caused as TestSprite generated-code/tooling artifacts (JWT string corruption, double-execution races against single-slot stateful endpoints, and test-assertion field-name guesses) and were independently confirmed working via direct API verification against the same disposable test accounts. **Zero real backend bugs were found in this batch.**

---

## 4️⃣ Key Gaps / Risks
- **TestSprite generated-code reliability on stateful, single-slot endpoints** (verification submit, ratings with long JWTs) is the main source of false failures in this run — treat any TestSprite failure on these endpoint classes as needing manual confirmation before filing as a bug.
- **`verification_submissions.attempt_number` is capped at 3 for life** by DB CHECK constraint — by design a user gets exactly 3 verification attempts ever unless a row is manually cleared. Worth confirming this is the intended lifetime product behavior (vs. resetting per admin unlock) outside of testing context.
- **Groups domain-verification OTP flow** was not re-run through TestSprite's own pipeline this session (requires reading a DB-only OTP hash mid-flow); it was previously manually verified in Phase 1 and is not re-covered here.
- **Frontend testing (main app port 3000, admin app port 3001)** remains out of scope for this backend-focused pass and has not been started.
