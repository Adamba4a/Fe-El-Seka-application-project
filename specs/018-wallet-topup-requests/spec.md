# Feature Specification: Manual Wallet Top-Up via Vodafone Cash

**Feature Branch**: `018-wallet-topup-requests`

**Created**: 2026-08-08

**Status**: Draft

**Input**: Phase 15 — Digital Payments (interim). The platform cannot yet integrate Paymob or Fawry because it lacks the tax card and company bank account those gateways require. In the interim, drivers top up their platform wallet by sending money to the platform's Vodafone Cash number and submitting proof of payment (transaction reference + screenshot) in-app; an admin reviews the proof and credits the wallet through the existing admin top-up mechanism.

---

## Clarifications

### Session 2026-08-08

- Q: Should this flow be driver-only, or should passengers also get wallets/top-up? → A: Driver-only. The existing wallet system (`011-financial-system`) has no passenger wallet concept — passengers continue paying drivers in cash at pickup. This feature only adds a self-service, proof-of-payment front end in front of the existing driver `ADMIN_CREDIT` top-up path; it does not introduce a new payment concept.
- Q: Should there be a limit on how many times a driver can resubmit after a rejection? → A: Cap at 3 total attempts per cycle (1 initial + 2 resubmissions), then lock until an admin unlocks the driver — mirroring the identity-verification submission cap already established in `003-auth-verification` (FR-018/FR-038).

---

## Business Objective *(mandatory)*

Give drivers a way to top up their own platform wallet without waiting on an admin to arrange an offline bank transfer or cash handoff, while the platform still lacks the tax card and company bank account required for Paymob/Fawry/InstaPay merchant integration. Drivers send money to the platform's published Vodafone Cash number, then submit the transaction reference number and a screenshot as proof; an admin visually verifies the proof against what the platform's Vodafone Cash account actually received and approves or rejects it. Approval credits the driver's wallet through the same `ADMIN_CREDIT` ledger path already established in `011-financial-system` — this feature adds a request-and-review layer in front of that existing mechanism, it does not replace or duplicate it.

Without this phase, every top-up requires a driver to reach an admin out-of-band and the admin to manually type an amount on trust, with no proof trail beyond the admin's own memory of the conversation. This phase gives drivers self-service initiation and gives admins a reviewable, auditable proof-of-payment queue — closing the gap until a real payment gateway is financially/legally onboardable.

**Constitutional Domain**: Financial System / Platform Operations

**Affected Applications**: Main App (driver top-up request screen); Admin Panel (top-up request review queue); FastAPI backend (top-up request service, calling the existing Phase 8 wallet-credit path).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Driver Submits a Top-Up Request (Priority: P1)

Ahmed wants to add money to his driver wallet. He opens the top-up screen and sees the platform's Vodafone Cash number. He sends 200 EGP via his Vodafone Cash app, then returns to Fe El Seka, enters 200.00 EGP, types in the transaction reference number from his Vodafone Cash confirmation SMS, and uploads a screenshot of the transaction. The system creates a pending request — his wallet balance does not change yet — and he sees a "Pending review" status.

**Why this priority**: This is the entire value proposition of the feature — without a driver-initiated request with proof attached, there is nothing for an admin to review, and drivers are no better off than the current admin-arranges-everything-offline flow. All other stories exist to serve this one.

**Independent Test**: As an authenticated driver, submit a top-up request with a positive amount, a reference number, and a valid screenshot. Verify: a `WalletTopupRequest` is created with `status = PENDING`; the driver's wallet `balance_egp` is unchanged; the request appears in the driver's own top-up history with the amount, reference, and "Pending review" status.

**Acceptance Scenarios**:

1. **Given** an authenticated, verified driver on the top-up screen, **When** they enter a positive amount, a transaction reference number, and upload a screenshot (JPEG or PNG, ≤10 MB), **Then** a `WalletTopupRequest` is created with `status = PENDING`, `driver_id` set to the requester, and the driver's wallet balance is unchanged.
2. **Given** a driver submitting a top-up request with a zero, negative, or missing amount, **When** the form is submitted, **Then** the system rejects the request with a validation error before any record is created.
3. **Given** a driver submitting a request without a reference number or without a screenshot, **When** the form is submitted, **Then** the system rejects the request — both fields are required; no partial `WalletTopupRequest` is created.
4. **Given** a driver who already has a `PENDING` `WalletTopupRequest`, **When** they attempt to submit another one, **Then** the system rejects the new submission with a message pointing to the existing pending request and its submitted amount; the driver may cancel the existing request (Story 3) to unblock a new submission.
5. **Given** a driver submitting a reference number that matches another driver's currently `PENDING` or `APPROVED` request, **When** the form is submitted, **Then** the system rejects the submission with `error_code = DUPLICATE_PAYMENT_REFERENCE`; no record is created. This prevents one real transfer's screenshot from being used to claim credit twice.
6. **Given** any non-driver authenticated user (passenger, admin), **When** they attempt to call the top-up request submission endpoint, **Then** the system returns HTTP 403.

---

### User Story 2 — Admin Reviews and Approves/Rejects a Top-Up Request (Priority: P2)

An admin opens the top-up review queue and sees Ahmed's pending request: 200.00 EGP, reference number, and the uploaded screenshot, oldest requests first. The admin checks the platform's actual Vodafone Cash account and confirms a matching 200 EGP transfer with the same reference number. The admin approves the request. Ahmed's wallet is credited 200.00 EGP through the same `ADMIN_CREDIT` path used for offline top-ups, and the request is marked `APPROVED` with the admin's identity and timestamp. If instead the admin cannot find a matching transfer, they reject the request with a reason ("No matching transfer found for this reference"); no credit is applied.

**Why this priority**: The review-and-credit step is what makes the request in Story 1 actually worth anything to the driver. It is P2, not P1, because it depends on Story 1 producing a request to review, and because the underlying crediting mechanism it calls (`ADMIN_CREDIT` top-up) already exists and is proven in `011-financial-system` — this story is "wire the queue to the existing mechanism," not "build a new one."

**Independent Test**: As an admin, open the review queue with at least one pending request. Approve it. Verify: the driver's wallet `balance_egp` increases by exactly the requested amount; exactly one `ADMIN_CREDIT` ledger entry is created referencing the admin's user ID; the `WalletTopupRequest` transitions to `APPROVED` with `reviewed_by` and `reviewed_at` set. Separately, reject a different pending request with a reason. Verify: the driver's wallet balance is unchanged; the request transitions to `REJECTED` with the reason stored.

**Acceptance Scenarios**:

1. **Given** an admin viewing a `PENDING` `WalletTopupRequest`, **When** they approve it, **Then** within a single atomic operation: the driver's wallet is credited exactly `amount_egp` via the existing Phase 8 `ADMIN_CREDIT` top-up path (no separate crediting logic is introduced); the request transitions to `APPROVED`; `reviewed_by` is set to the admin's user ID and `reviewed_at` to the current timestamp; the resulting ledger entry's ID is stored on the request for traceability.
2. **Given** an admin viewing a `PENDING` `WalletTopupRequest`, **When** they reject it without entering a reason, **Then** the system blocks the rejection — a reason is mandatory, mirroring the identity-verification review flow in `003-auth-verification`.
3. **Given** an admin viewing a `PENDING` `WalletTopupRequest`, **When** they reject it with a reason, **Then** the request transitions to `REJECTED` with the reason, `reviewed_by`, and `reviewed_at` stored; no wallet credit occurs; the driver may submit a new request (with a new or corrected reference number, since the rejected request's reference is no longer "in use").
4. **Given** a `WalletTopupRequest` that has already been approved or rejected, **When** an admin attempts to approve or reject it again, **Then** the system returns a clear error and takes no action — review actions are not repeatable on an already-decided request.
5. **Given** any non-admin authenticated user, **When** they attempt to call the review (approve/reject) endpoints, **Then** the system returns HTTP 403.
6. **Given** the review queue, **When** it is rendered, **Then** pending requests are shown oldest-first, each with the driver's name, phone number, requested amount, reference number, screenshot, and submission timestamp.

---

### User Story 3 — Driver Views Top-Up History and Cancels a Pending Request (Priority: P3)

Ahmed checks his top-up history and sees his 200 EGP request is still "Pending review," alongside a past request that was approved and one that was rejected with the reason "Screenshot unreadable." Realizing he entered the wrong reference number on a brand-new pending request, he cancels it himself before the admin reviews it, then resubmits with the correct reference.

**Why this priority**: Transparency and the ability to self-correct reduce admin load (fewer avoidable rejections reaching the queue) and driver frustration, but the platform functions correctly without this — an admin can still reject a bad submission. P3 because it is a quality-of-life addition on top of Stories 1–2, not a blocker for the core flow.

**Independent Test**: As a driver with one pending, one approved, and one rejected `WalletTopupRequest`, open the top-up history. Verify all three are listed with correct status and details. Cancel the pending one. Verify its status becomes `CANCELLED`, no wallet change occurs, and the driver can immediately submit a new request (Story 1, Acceptance Scenario 4 no longer blocks them).

**Acceptance Scenarios**:

1. **Given** a driver with a mix of `PENDING`, `APPROVED`, and `REJECTED` top-up requests, **When** they open their top-up history, **Then** all requests are listed newest-first with amount, reference number, status, submission timestamp, and (for rejected requests) the rejection reason.
2. **Given** a driver's own `PENDING` request, **When** they cancel it, **Then** it transitions to `CANCELLED`; no wallet change occurs; the driver may immediately submit a new request, and the cancelled request's reference number is no longer considered "in use" for the duplicate-reference check.
3. **Given** a request that is already `APPROVED` or `REJECTED`, **When** the driver attempts to cancel it, **Then** the system rejects the cancellation — only `PENDING` requests can be cancelled.
4. **Given** any user other than the request's own driver, **When** they attempt to cancel it, **Then** the system returns HTTP 403.

---

### Edge Cases

- What if the amount a driver enters doesn't match what the admin actually sees received on the platform's Vodafone Cash account? The admin rejects the request with a reason (e.g., "Amount mismatch — received 150 EGP, requested 200 EGP"); the driver resubmits with the correct amount, referencing the same real transfer if the reference number is not already tied to another decided request.
- What if the uploaded screenshot is blurry or unreadable? The admin rejects with a reason asking for a clearer screenshot; no credit is applied.
- What if two different drivers submit the same reference number, one by genuine typo? The second submission is blocked at write time by the duplicate-reference check (Story 1, Scenario 5); that driver must correct the reference number or contact support if they believe it is genuinely unique.
- What if the platform's Vodafone Cash number changes? The admin updates the configurable setting (FR-001); already-`PENDING` requests remain valid for review since the review checks the amount and reference against the platform's Vodafone Cash transaction history, not which number is currently displayed to new requesters.
- What if a driver never had a wallet record before (never topped up, never completed a ride)? Approval reuses the existing Phase 8 behavior (`011-financial-system` FR-001): the wallet record is created automatically on this first credit.
- What if an admin approves a request and the underlying wallet-credit call fails partway (e.g., database error)? The entire approval MUST be atomic — either both the ledger entry and the request's `APPROVED` status are committed, or neither is; a failed approval leaves the request `PENDING` for retry, not silently `APPROVED` without a credited wallet.
- What if a driver's 3rd `REJECTED` outcome in a cycle occurs? The driver is submission-locked (FR-014); they see a message directing them to platform support (FR-015); only an admin unlock (FR-016) restores their ability to submit a new request.

---

## Requirements *(mandatory)*

### Functional Requirements

**Platform Payment Info**

- **FR-001**: The system MUST display the platform's Vodafone Cash number to drivers on the top-up request screen. This number MUST be stored as a configurable admin setting (not hard-coded), mirroring the configurable support-email pattern established in `003-auth-verification` (FR-037).

**Driver Request Submission**

- **FR-002**: The system MUST provide an authenticated endpoint for verified drivers to submit a `WalletTopupRequest` containing: a positive `amount_egp`, a transaction reference number (free text, required), and a screenshot image (JPEG or PNG, ≤10 MB, matching the document-upload limits in `003-auth-verification` FR-014). Submission MUST NOT credit the wallet — the resulting record is created with `status = PENDING`.
- **FR-003**: Submission requests with a zero, negative, or missing `amount_egp`, or a missing reference number, or a missing screenshot, MUST be rejected with a validation error before any record is created.
- **FR-004**: A driver MUST NOT have more than one `PENDING` `WalletTopupRequest` at a time. A new submission attempt while one is already pending MUST be rejected with a message identifying the existing pending request.
- **FR-005**: A submission whose reference number matches the reference number of any other `PENDING` or `APPROVED` `WalletTopupRequest` (regardless of which driver submitted it) MUST be rejected with `error_code = DUPLICATE_PAYMENT_REFERENCE`; no record is created. Reference numbers belonging to `REJECTED` or `CANCELLED` requests are not considered "in use" and may be reused in a new submission.
- **FR-006**: A driver MUST only be able to view and manage their own `WalletTopupRequest` records. Requests for another driver's records MUST be rejected with HTTP 403.

**Driver Self-Cancellation**

- **FR-007**: A driver MUST be able to cancel their own `WalletTopupRequest` while it is `PENDING`. Cancellation sets `status = CANCELLED`; no wallet change occurs. Requests that are already `APPROVED` or `REJECTED` MUST NOT be cancellable.

**Admin Review**

- **FR-008**: The system MUST provide an admin-only queue endpoint listing `PENDING` `WalletTopupRequest` records, ordered oldest-first, including the driver's name, phone number, `amount_egp`, reference number, screenshot, and submission timestamp.
- **FR-009**: The system MUST provide an admin-only approval endpoint that, for a `PENDING` request, atomically: (a) invokes the existing Phase 8 `ADMIN_CREDIT` wallet top-up path (`011-financial-system` FR-010) for `amount_egp` on the request's driver, with `created_by` set to the reviewing admin and a `note` referencing the `WalletTopupRequest` ID; (b) sets the request's `status = APPROVED`, `reviewed_by`, `reviewed_at`, and `ledger_entry_id` (the ID of the resulting `ADMIN_CREDIT` ledger entry). This endpoint MUST NOT implement a second, independent wallet-crediting code path — it calls the same function/service that `011-financial-system`'s admin top-up endpoint uses.
- **FR-010**: The system MUST provide an admin-only rejection endpoint that, for a `PENDING` request, requires a mandatory rejection reason and sets `status = REJECTED`, `reviewed_by`, `reviewed_at`, and the stored reason. No wallet change occurs.
- **FR-011**: Approval or rejection of a `WalletTopupRequest` that is not currently `PENDING` MUST be rejected with a clear error; review actions are not repeatable on an already-decided request.
- **FR-012**: Only authenticated users with the admin role MUST be permitted to call the queue, approval, and rejection endpoints; all other authenticated users MUST receive HTTP 403.
- **FR-013**: All admin review actions (approve, reject) MUST be logged with the admin's identity, timestamp, and the target request ID, mirroring the audit requirement in `003-auth-verification` (FR-034).

**Abuse Prevention (Resubmission Cap)**

- **FR-014**: The system MUST cap a driver at 3 `REJECTED` `WalletTopupRequest` outcomes within their current cycle. A cycle begins at account creation and resets immediately whenever the driver has an `APPROVED` request or is unlocked by an admin (FR-016). `CANCELLED` requests (self-cancelled by the driver before review, per FR-007) do NOT count toward this cap — only admin-`REJECTED` outcomes do, since self-correction should not be penalized. Reaching the 3rd `REJECTED` outcome in a cycle blocks the driver from submitting any further `WalletTopupRequest` until an admin unlocks them.
- **FR-015**: When a driver is submission-locked (FR-014), the system MUST display a message directing them to the platform support contact for manual assistance, reusing the configurable support-contact mechanism established in `003-auth-verification` (FR-037).
- **FR-016**: An admin MUST be able to unlock a submission-locked driver, resetting their cycle so they may submit again, mirroring the unlock capability in `003-auth-verification` (FR-038).

**Driver Notification**

- **FR-017**: When a `WalletTopupRequest` is approved or rejected, the system MUST notify the requesting driver via the existing push-notification infrastructure (`010-realtime-transportation`), including the rejection reason when applicable.

**Localization**

- **FR-018**: All new driver-facing strings introduced by this feature — the driver top-up request form (including the platform Vodafone Cash number label and validation/error messages such as the duplicate-reference and pending-request-exists errors), the driver's top-up history and cancellation confirmation, and approval/rejection push notifications (FR-017) — MUST ship with both English and Arabic translations from initial release, using the translation-catalog mechanism established in `017-arabic-rtl-localization`. None of this feature's driver-facing strings may rely on the FR-011 English-fallback behavior from `017-arabic-rtl-localization` as a substitute for shipping an Arabic translation; that fallback exists for translation lag on unrelated content, not as the default path for new features. The admin review queue (Admin Panel) remains English-only, consistent with `017-arabic-rtl-localization`'s existing scope decision that the Admin Panel is excluded from localization (its internal staff users are English-comfortable); this feature does not introduce Arabic support or new i18n infrastructure to `apps/admin`.
- **FR-019**: All EGP amounts and timestamps shown to drivers by this feature (requested amount, top-up history, notification content, in `apps/main`) MUST use the locale-aware currency and date formatting already established for driver wallet views in `017-arabic-rtl-localization`, rather than introducing separate formatting logic. The admin review queue (`apps/admin`) MUST format amounts and timestamps using the same fixed `en-EG` `Intl` formatting convention already used by the existing admin wallet views (e.g., `AdminLedgerTable`), not a new formatting approach.

### Key Entities

- **WalletTopupRequest**: A driver-initiated, admin-reviewed request to credit the driver's existing Phase 8 wallet. Attributes: `id` (UUID); `driver_id` (UUID, foreign key → users); `amount_egp` (decimal 10,2 — the amount the driver claims to have sent); `payment_reference` (text — the Vodafone Cash transaction reference number, unique among `PENDING`/`APPROVED` requests); `screenshot_url` (private storage reference — proof-of-payment image, same access-control model as `003-auth-verification` identity documents); `status` (enum: `PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`); `rejection_reason` (text, nullable — set only when `status = REJECTED`); `reviewed_by` (UUID, nullable — the admin user ID); `reviewed_at` (timestamp, nullable); `ledger_entry_id` (UUID, nullable, foreign key → `driver_ledger_entries` — set only on approval, linking the request to the `ADMIN_CREDIT` entry it produced); `created_at`; `updated_at`.

- **Platform Vodafone Cash Number** (configurable setting, not a new table if an existing settings mechanism is reused): the wallet number drivers are instructed to send money to. Admin-editable; not hard-coded.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A driver can complete a top-up request submission (view number, enter amount and reference, upload screenshot) in under 3 minutes.
- **SC-002**: An admin can review and action (approve or reject) a pending top-up request in under 2 minutes from opening it in the queue.
- **SC-003**: 100% of `APPROVED` requests have exactly one corresponding `ADMIN_CREDIT` ledger entry whose `amount_egp` matches the request's `amount_egp` exactly, traceable via `ledger_entry_id`.
- **SC-004**: Zero `APPROVED` or `PENDING` requests ever share the same `payment_reference` value — verified by the uniqueness constraint holding under concurrent submission attempts.
- **SC-005**: 100% of approve/reject actions are attributed to a specific admin identity and timestamp in the audit trail.
- **SC-006**: Drivers receive a notification for 100% of approved or rejected requests within normal push-notification delivery latency.
- **SC-007**: 100% of drivers who accumulate 3 `REJECTED` outcomes within a cycle are blocked from further submission until an admin unlock — verified by zero successful submissions from a locked driver until an unlock action is recorded for them.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Top-up request submission and review endpoints MUST respond within 500ms at p95 under normal load (≤1,000 active users).
- **NFR-002**: Proof-of-payment screenshots MUST be stored with private access control; no publicly guessable URL may grant access, matching `003-auth-verification` NFR-002.
- **NFR-003**: Approval and rejection actions MUST be idempotent — acting on an already-decided request MUST return a clear error, not silently succeed or double-credit the wallet.
- **NFR-004**: The admin review queue MUST render within 2 seconds for up to 500 pending requests, matching `003-auth-verification` NFR-006.
- **NFR-005**: The uniqueness constraint on `payment_reference` among `PENDING`/`APPROVED` requests MUST be enforced at the database level (not only in application code), to prevent a race between two concurrent submissions with the same reference number from both succeeding.
- **NFR-006**: The approval endpoint's wallet-credit step and the request's status update MUST execute within the same database transaction as the underlying Phase 8 `ADMIN_CREDIT` ledger write; if either fails, both roll back and the request remains `PENDING`.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `011-financial-system` (Phase 8) — this feature's approval action calls the existing `ADMIN_CREDIT` wallet top-up path directly; it does not introduce a new crediting mechanism. Requires the driver wallet, ledger, and admin top-up endpoint to already exist and be unmodified in their guarantees (immutability, atomicity).
  - `003-auth-verification` (Phase 3) — reuses the admin role system for review-endpoint authorization, the private document-storage pattern for screenshots, and the driver authentication/verification gate (only verified drivers may submit top-up requests).
  - `010-realtime-transportation` (Phase 7) — reuses the existing push-notification (FCM) infrastructure to notify drivers of approval/rejection.
  - `017-arabic-rtl-localization` (Phase 14) — this feature's new driver-facing screens (driver top-up form, top-up history) and notifications MUST use the existing translation-catalog, RTL-layout, and locale-aware currency/date formatting infrastructure rather than shipping English-only or introducing a separate formatting approach (FR-018, FR-019). The admin review queue is out of scope for this dependency, matching 017's existing Admin Panel exclusion.

- **External**:
  - Vodafone Cash — no API or merchant integration. Verification is entirely manual: an admin visually cross-checks the platform's own Vodafone Cash transaction history against submitted requests. No InstaPay, Paymob, or Fawry integration is included in this phase.

- **Data**:
  - `driver_wallets` and `driver_ledger_entries` (from `011-financial-system`) — this feature writes to them only through the existing top-up service function, never directly.

---

## Out-of-Scope

- **Automated/API-based payment verification** — no Vodafone Cash merchant API, webhook, or SMS-parsing integration. This entire feature exists specifically because that kind of automated verification is not available to the platform yet; review is manual by design.
- **Paymob, Fawry, or InstaPay gateway integration** — deferred until the business obtains a tax card and company bank account; this feature is the interim measure, not a replacement.
- **Passenger wallets or passenger top-up** — passengers continue paying drivers in cash at pickup, per `011-financial-system`'s existing scope. Confirmed out of scope per this spec's clarification.
- **Automatic approval or OCR-based screenshot verification** — every request requires manual admin review for this phase; no confidence-scoring or auto-approval path.
- **Refunds** — if a request is rejected after money was genuinely sent (e.g., driver error in the amount/reference), resolution between the driver and the platform happens offline; the system does not process refunds, matching the existing refund exclusion in `011-financial-system`.
- **Multiple or region-specific platform Vodafone Cash numbers** — a single platform-wide number for MVP.
- **Admin corrective adjustments to an already-approved request** — if an admin approves in error, the existing `ADMIN_DEBIT` corrective-adjustment endpoint from `011-financial-system` (FR-014) is used exactly as it is today; this feature does not add a new correction mechanism.

---

## Technical Considerations

- The approval endpoint MUST call the same wallet-crediting service function that `011-financial-system`'s `POST /admin/drivers/{driver_id}/wallet/topup` endpoint uses, passing the reviewing admin's ID and a note referencing the `WalletTopupRequest` ID — not a parallel implementation. This keeps the ledger-integrity guarantees (`011-financial-system` SC-006) intact without re-deriving them for this feature.
- The `payment_reference` uniqueness constraint should be implemented as a partial unique index scoped to `status IN ('PENDING', 'APPROVED')`, so that `REJECTED`/`CANCELLED` requests don't permanently block reuse of a reference number, matching FR-005.
- Screenshot storage should reuse the same private storage bucket/access-control pattern already established for identity documents in `003-auth-verification`, rather than introducing a new storage convention.
- The platform Vodafone Cash number should be stored using the same configurable-setting mechanism as the support email address in `003-auth-verification` (FR-037), so it can be updated without a deploy.
- All new driver-facing strings (form labels, validation/error messages, notification text, in `apps/main`) must be added as translation keys in both locale catalogs from `017-arabic-rtl-localization` as part of this feature's own implementation — they are new keys, not something the completed Phase 14 work retroactively covers. Driver-facing layout components MUST be built with the shared RTL-aware components/utilities from that phase rather than fixed-direction styling, so mirroring and currency/date formatting are correct by default (per that phase's FR-015 flexible-sizing and mirroring-by-default approach). The admin review queue (`apps/admin`) is plain English/LTR, consistent with the existing Admin Panel and 017's exclusion of it — no translation keys or RTL components are needed there.
- The resubmission-cap cycle (FR-014) can be computed on demand from the driver's own `WalletTopupRequest` history (count `REJECTED` records since their most recent `APPROVED` record or admin-unlock event) rather than requiring a new persisted counter column; if a stored counter is used instead for query performance, it MUST be kept consistent with that same derivation rule.

---

## Assumptions

- **Driver-only for this phase**: Per this spec's clarification, only drivers (who already have wallets per `011-financial-system`) can submit top-up requests. Passengers are unaffected.
- **No system-enforced minimum or maximum top-up amount**: Beyond requiring a positive amount (FR-003), the system does not cap or floor the requested amount. The admin's manual review against the platform's actual Vodafone Cash transaction history is the practical control, not a numeric limit.
- **No auto-expiry of pending requests**: A `PENDING` request remains in the queue indefinitely until an admin acts or the driver cancels it, matching the un-timed queue behavior of the identity-verification review flow in `003-auth-verification`.
- **Reference number is free text, not format-validated**: Vodafone Cash confirmation SMS reference formats are not treated as a stable, documented format to validate against; the field only needs to be present and unique among active requests.
- **One review action reviewer**: Approve/reject decisions are made by any authenticated admin user; there is no per-request reviewer assignment or second-approval workflow for MVP, consistent with `011-financial-system`'s existing single-admin-approval model.
