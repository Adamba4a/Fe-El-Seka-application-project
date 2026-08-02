# Feature Specification: Admin Operations (Full)

**Feature Branch**: `015-admin-operations`

**Created**: 2026-08-02

**Status**: Draft

**Input**: Phase 11 — Admin Operations (Full): a complete platform-operations dashboard with trend analytics, full user management (search, filter, unified activity view, suspend/reinstate), enhanced verification-queue tooling (search, aging, re-review), and financial reporting/administration (aggregate revenue and commission reporting, driver balance oversight).

---

## Business Objective *(mandatory)*

Turn the admin panel from a set of disconnected task queues into an operations console the platform team can actually run the business from. Phase 3 shipped a bare verification queue, Phase 8 added per-driver wallet top-up, and Phase 10 added a safety-moderation queue — each useful in isolation, but an admin today has no single view of platform health, no way to search or filter the user base, no aggregate financial picture, and no way to see a user's full activity (rides, bookings, ratings, reports, wallet) without hopping between screens. This phase closes that gap: a real overview dashboard with trends, complete user search/management, enhanced verification tooling with aging visibility, and a financial reporting layer that finally delivers the revenue/commission analytics both the constitution's auditability principle and the `011-financial-system` spec explicitly deferred to here.

**Constitutional Domain**: Platform Administration (Principle VII — Auditability; extends the admin surface established in Principle III — Trust Before Transportation)

**Affected Applications**: Admin Panel (all four capabilities below), Shared backend (FastAPI, read-only aggregation endpoints over existing tables).

---

## Clarifications

### Session 2026-08-02

- Q: Should the general suspend/reinstate action on the new user detail view (FR-009) be usable against admin-role accounts, given that suspension revokes active sessions and blocks re-authentication? → A: Block admin-targeting suspension entirely — accounts with `role = 'admin'` cannot be suspended through this mechanism; admin account status changes remain an out-of-band Supabase Auth operation (FR-009).
- Q: Should the financial report CSV export (FR-020) be treated as sensitive data requiring signed-URL/short-expiry handling similar to National ID documents, or as an ordinary direct file download? → A: Ordinary direct download — generated on-demand and streamed directly to the requesting admin's browser; no file is persisted server-side and no signed-URL mechanism is introduced beyond the existing admin-only endpoint authorization (NFR-007).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Operations Dashboard (Priority: P1)

An admin starts her shift and opens the admin panel home screen. Instead of four bare counters, she sees platform-wide KPIs for a selectable period (today, last 7 days, last 30 days): new users, rides created and completed, gross commission collected, and the current depth of every operational queue (pending verifications, open safety reports, drivers with a low or zero wallet balance). Below the KPIs, simple trend charts show rides-completed and commission-collected per day over the selected period, so she can spot a dip or spike at a glance before she goes looking for a cause.

**Why this priority**: This is the front door of the admin experience and the highest-leverage single change — every other capability in this phase (user management, verification, financial reporting) is something an admin discovers is *needed* by first seeing a number here that looks wrong. It is P1 because it is purely additive read/aggregation work over data that already exists from prior phases, making it the fastest path to a demonstrable improvement.

**Independent Test**: Seed a test environment with a mix of users, completed rides, commission ledger entries, pending verifications, and open reports across a 7-day window. Load the dashboard with the "last 7 days" period selected. Verify: each KPI tile matches a direct database count/sum for that window; the trend chart's daily data points sum to the same totals as the KPI tiles; changing the period selector to "last 30 days" recomputes all tiles and charts without requiring a hard refresh.

**Acceptance Scenarios**:

1. **Given** an admin on the dashboard home screen, **When** the page loads with the default period, **Then** it displays: total users (by role: passenger/driver/admin), rides created and rides completed in the period, total commission collected (EGP) in the period, count of pending verification submissions, count of open/under-review safety reports, and count of drivers whose available wallet balance is at or below zero.
2. **Given** the dashboard, **When** the admin selects a different period (today / last 7 days / last 30 days / last 90 days), **Then** every KPI and chart recomputes to reflect only activity within the newly selected window.
3. **Given** the dashboard's trend charts, **When** the admin views them, **Then** rides-completed and commission-collected are each plotted as one data point per day across the selected period, with no day silently omitted even if its value is zero.
4. **Given** any KPI tile, **When** the admin clicks it, **Then** she is taken to the relevant detail screen (e.g., the verification queue, the moderation queue, or the user list) pre-filtered to the underlying records where a sensible filter exists.
5. **Given** a non-admin authenticated user, **When** they attempt to call any dashboard aggregation endpoint, **Then** the system rejects the request with an authorization error.
6. **Given** the platform has zero activity in the selected period (e.g., a brand-new deployment), **When** the dashboard loads, **Then** all KPIs display zero and charts render an empty-state period rather than erroring.

---

### User Story 2 - Complete User Management (Priority: P2)

An admin needs to find a specific user reported by a support ticket. She types a partial name, phone number, or email into a search box on the user management screen and the matching user appears instantly, along with the rest of the user list, filterable by role and verification status and sortable by signup date. She opens the user's detail page and sees, in one place, their profile info, ride/booking history, ratings received and given, any reports filed against or by them, and — if they're a driver — their wallet balance and ledger. From that same page she suspends the account with a reason, and later reinstates it, without needing to jump to the separate safety-moderation queue used in Phase 10.

**Why this priority**: The existing user list (Phase 3) is a flat, unfiltered, unsearchable table — functionally a placeholder. As the user base grows past a handful of test accounts, finding and understanding a specific user becomes the single most common admin task, and today it requires manual scrolling and cross-referencing multiple screens. This is P2 because it depends on nothing new from Story 1 and delivers value the moment it ships, but ranks below the dashboard because it is a targeted lookup tool rather than the daily-use overview screen.

**Independent Test**: Seed at least 25 test users across all three roles with varying verification statuses. Search by a partial phone number matching exactly one user and verify only that user appears. Apply a role filter and a status filter together and verify the result set matches both conditions. Open a driver's detail page and verify ride history, ratings, reports, and wallet ledger all appear without additional navigation. Suspend the account with a reason and verify `verification_status` becomes `suspended` and the action appears in the audit log; reinstate and verify it returns to `verified`.

**Acceptance Scenarios**:

1. **Given** the user management screen, **When** the admin enters a search term matching a user's display name, phone number, or email (full or partial), **Then** the list narrows to users matching that term, updating as she types or on explicit submit.
2. **Given** the user list, **When** the admin applies a role filter (passenger/driver/admin), a verification-status filter, or both, **Then** only users matching all applied filters are shown, combinable with an active search term.
3. **Given** a filtered or unfiltered user list, **When** it contains more results than fit on one screen, **Then** the list is paginated (or infinitely scrollable) rather than rendering every user at once.
4. **Given** an admin viewing a specific user's detail page, **When** the page loads, **Then** it shows the user's profile fields, their ride history (as driver) or booking history (as passenger), their aggregate rating and individual ratings received, any safety reports filed by or against them, and — for drivers — their current wallet balance and recent ledger entries, all without navigating away from the page.
5. **Given** an admin on a passenger's or driver's detail page, **When** she suspends the account with a required reason, **Then** the user's `verification_status` becomes `suspended`, the action is recorded in the existing `admin_audit_logs` mechanism, and the user is blocked from creating new rides/bookings — reusing the exact suspension behavior established in `003-auth-verification` and `014-trust-community`, not a second parallel mechanism.
6. **Given** a suspended user's detail page, **When** the admin reinstates them with a required reason, **Then** `verification_status` returns to `verified` and the action is logged, identical to the existing reinstatement behavior.
7. **Given** a non-admin authenticated user, **When** they attempt to call the user search, filter, or detail endpoints directly, **Then** the system rejects the request with an authorization error.
8. **Given** an admin viewing a user's detail page for a user with no rides, bookings, ratings, or reports yet, **When** the page loads, **Then** each section displays an explicit empty state rather than an error or a blank gap.
9. **Given** an admin viewing the detail page of a user whose `role = 'admin'` (including her own account), **When** she attempts to invoke the suspend action, **Then** the system rejects the request without changing `verification_status`, and the suspend control is not offered for admin-role accounts in the first place.

---

### User Story 3 - Enhanced Verification Queue Tooling (Priority: P3)

An admin opens the verification queue and, instead of a plain oldest-first list, can search for a specific submission by the applicant's name or phone number, and see how long each submission has been waiting (its "age") with older-than-24-hours submissions visually flagged so nothing sits forgotten. She also opens the approved/rejected history, searches it the same way, and — for a user who was rejected but has since contacted support with a legitimate correction outside the normal 3-submission limit — she can grant one additional manual re-submission attempt directly from that user's verification history, reusing the existing unlock mechanism from `003-auth-verification` rather than a new one.

**Why this priority**: The core approve/reject workflow already exists and works from Phase 3; this story is a set of usability and visibility improvements on top of a queue that already functions, so it delivers real value but is not blocking anything else — hence P3.

**Independent Test**: Seed the pending queue with submissions of varying ages, including at least one older than 24 hours. Verify the aged submission is visually flagged. Search the pending queue by a partial applicant name and verify only matching submissions appear. Search the approval/rejection history the same way. For a locked-out user (3 failed submissions), use the manual unlock action from their verification record and verify their submission count resets, allowing exactly one further attempt.

**Acceptance Scenarios**:

1. **Given** the pending verification queue, **When** it renders, **Then** each submission displays how long it has been pending (e.g., "3 hours ago", "2 days ago"), and any submission pending longer than 24 hours is visually distinguished from newer ones.
2. **Given** the pending queue or the approved/rejected history, **When** the admin enters a search term matching an applicant's name or phone number, **Then** the visible list narrows to matching submissions only, without losing the existing oldest-first (queue) or most-recent-first (history) ordering.
3. **Given** the verification history, **When** the admin filters by outcome (approved / rejected), **Then** only submissions with that outcome are shown.
4. **Given** a user who has exhausted all 3 allowed verification submission attempts (per `003-auth-verification` FR-018), **When** an admin opens that user's verification record and takes the "unlock for re-submission" action, **Then** their submission count resets and they may submit exactly one additional attempt — this reuses the existing unlock mechanism, not a new one.
5. **Given** any verification search, filter, or unlock action, **When** invoked by a non-admin authenticated user, **Then** the system rejects the request with an authorization error.
6. **Given** an admin approves or rejects a submission from the enhanced queue view, **When** the action is taken, **Then** behavior is identical to the existing `003-auth-verification` approve/reject flow (status update, audit log entry, applicant notification) — this story changes discoverability and visibility only, not the underlying decision workflow.

---

### User Story 4 - Financial Reporting & Driver Balance Oversight (Priority: P4)

An admin responsible for the platform's finances opens the financial reporting screen and selects a date range. She sees total commission collected, total amount credited to drivers via top-ups, and net platform revenue for that range, broken down as a simple per-day or per-week series. She also sees a sortable list of all drivers with their current wallet balance, so she can immediately spot which drivers are at or near zero and likely to be blocked from creating new rides, without opening each driver's wallet individually. She exports the revenue report for the selected range as a downloadable file to share with the rest of the team.

**Why this priority**: This is explicitly the capability `011-financial-system` deferred with the note "financial reporting and analytics... are Phase 11 features" — it depends on the ledger data that phase already produces and is purely a reporting layer on top of it, making it safe to ship last since nothing else in this phase or in prior phases depends on it existing.

**Independent Test**: Seed a set of `ADMIN_CREDIT` and `COMMISSION_DEBIT` ledger entries across several drivers over a 2-week window. Open the financial report for that window and verify total commission collected equals the sum of `COMMISSION_DEBIT` entries, total credited equals the sum of `ADMIN_CREDIT` entries, and net revenue is reported as the commission total (top-ups are platform-to-driver transfers, not revenue). Verify the driver balance list matches each driver's current `balance_egp` and highlights any at or below zero. Export the report and verify the downloaded file's totals match the on-screen figures.

**Acceptance Scenarios**:

1. **Given** the financial reporting screen, **When** the admin selects a date range, **Then** the system displays total commission collected (sum of `COMMISSION_DEBIT` entries in range), total admin credits issued (sum of `ADMIN_CREDIT` entries in range), total admin corrective debits (sum of `ADMIN_DEBIT` entries in range), and net platform revenue (commission collected minus corrective debits attributable to commission errors), all scoped strictly to the selected range.
2. **Given** a selected date range, **When** the report renders, **Then** commission collected is also plotted as a simple per-day (or per-week, for ranges over 60 days) series so trends are visible, not just a single total.
3. **Given** the driver balance list, **When** it renders, **Then** every driver with a wallet record is listed with their current balance and reserved amount, sorted by balance ascending by default so the lowest-balance (most at-risk) drivers surface first.
4. **Given** the driver balance list, **When** a driver's available balance is at or below zero, **Then** that row is visually flagged as at-risk of being blocked from ride creation.
5. **Given** a generated financial report for a date range, **When** the admin requests an export, **Then** the system produces a downloadable file (e.g., CSV) whose totals match exactly what was shown on screen for that range.
6. **Given** a date range with no financial activity, **When** the report loads, **Then** all totals display as zero and the trend series renders as an empty period rather than erroring.
7. **Given** a non-admin authenticated user, **When** they attempt to call any financial reporting or export endpoint, **Then** the system rejects the request with an authorization error.

---

### Edge Cases

- What happens if an admin selects a dashboard/report period that spans a timezone boundary (e.g., "today")? Day boundaries are computed consistently in a single fixed reference timezone (Africa/Cairo, the platform's operating market) for every KPI, chart, and report, so totals are internally consistent across screens.
- What happens if a user is searched for by a phone number fragment that matches multiple users? All matches are returned in the filtered list; the admin distinguishes between them using name and role shown alongside.
- What happens if an admin tries to suspend a user who is already suspended, or reinstate a user who is already verified? The action is a no-op from the account-state perspective but is still logged as an explicit admin action with its reason, consistent with the audit trail principle.
- What happens if a driver's wallet record does not exist yet (never topped up, never created a ride)? They appear in the driver balance list with a balance of 0.00 EGP, consistent with the effective-zero behavior established in `011-financial-system`.
- What happens if the financial export is requested for a very large date range (e.g., all-time)? The export still succeeds but may take longer to generate; the admin is shown a generation-in-progress indicator rather than a frozen screen.
- What happens when two admins view the same user's detail page or the same dashboard simultaneously? Each sees an independently-read, current snapshot; there is no live-collaboration locking, consistent with how the existing verification and moderation queues already behave under concurrent admin access.
- What happens if an admin applies a search term that matches zero users, submissions, or drivers? The relevant list renders an explicit "no results" state rather than an empty table with no explanation.
- What happens to the enhanced verification queue's aging indicator if a submission is currently locked (user exhausted 3 attempts) rather than simply pending? Locked accounts are shown in a distinct "locked — awaiting manual unlock" state rather than being counted against the normal pending-age flag.
- What happens if an admin attempts to suspend another admin account, or their own, from the user detail view? The request is rejected and the suspend control is not shown for `role = 'admin'` targets at all — admin account status changes remain an out-of-band Supabase Auth operation, preventing any path to a platform-wide admin lockout (see Clarifications).
- What happens to an exported financial report file after the browser download completes? Nothing is retained server-side — the export is generated on-demand and streamed directly to the admin's browser with no persisted copy, so there is no server-side file to expire or clean up (see Clarifications).

---

## Requirements *(mandatory)*

### Functional Requirements

**Platform Operations Dashboard**

- **FR-001**: The system MUST provide an admin-only dashboard displaying, for an admin-selectable period (today / last 7 days / last 30 days / last 90 days): total users by role, rides created, rides completed, total commission collected, count of pending verification submissions, count of open or under-review safety reports, and count of drivers at or below a zero available wallet balance.
- **FR-002**: The system MUST render rides-completed and commission-collected as day-by-day trend series across the selected period, including days with zero activity.
- **FR-003**: Each dashboard KPI tile MUST link to the corresponding detail screen (verification queue, moderation queue, user list, or financial report), pre-filtered where a sensible filter exists.
- **FR-004**: Dashboard KPIs and charts MUST recompute against the newly selected period without requiring the admin to navigate away and back.

**Complete User Management**

- **FR-005**: The system MUST allow an admin to search the user list by partial or full match on display name, phone number, or email.
- **FR-006**: The system MUST allow an admin to filter the user list by role (passenger / driver / admin) and by verification status, combinable with an active search term.
- **FR-007**: The user list MUST be paginated (or equivalently incrementally loaded) rather than rendering the entire user base in a single unbounded response.
- **FR-008**: The system MUST provide a per-user detail view showing: profile information; ride history (if driver) or booking history (if passenger); aggregate rating and individual ratings received; safety reports filed by or against the user; and, for drivers, current wallet balance and recent ledger entries — all on one screen.
- **FR-009**: An admin MUST be able to suspend a user's account from the user detail view with a required reason, setting `verification_status = 'suspended'` and recording the action via the existing `admin_audit_logs` mechanism established in `003-auth-verification`, **except** for accounts with `role = 'admin'` — the suspend action MUST NOT be offered or permitted against any admin-role account, including the acting admin's own account, to prevent a platform-wide admin lockout (see Clarifications, Session 2026-08-02).
- **FR-010**: An admin MUST be able to reinstate a suspended user from the user detail view with a required reason, setting `verification_status = 'verified'` and recording the action via the same audit mechanism.
- **FR-011**: Suspension and reinstatement performed from the user detail view MUST have identical account-level effects (blocking/restoring ride and booking creation) as the equivalent actions already defined in `003-auth-verification` and `014-trust-community` — this is a second entry point to the same mechanism, not a new one.

**Enhanced Verification Queue Tooling**

- **FR-012**: The system MUST display, for each pending verification submission, an elapsed-time indicator ("age") since submission, and MUST visually distinguish submissions pending longer than 24 hours.
- **FR-013**: The system MUST allow an admin to search the pending queue and the approved/rejected history by applicant name or phone number.
- **FR-014**: The system MUST allow an admin to filter the verification history by outcome (approved / rejected).
- **FR-015**: The system MUST allow an admin to grant a locked-out user (one who has exhausted all 3 allowed submission attempts per `003-auth-verification` FR-018) exactly one additional submission attempt, reusing the existing unlock mechanism.
- **FR-016**: Approve/reject actions taken from the enhanced queue or history views MUST produce identical outcomes (status update, audit log entry, applicant notification) to the existing `003-auth-verification` verification workflow.

**Financial Reporting & Driver Balance Oversight**

- **FR-017**: The system MUST provide an admin-only financial report for an admin-selectable date range, showing: total commission collected (sum of `COMMISSION_DEBIT` ledger entries), total admin credits issued (sum of `ADMIN_CREDIT` entries), total admin corrective debits (sum of `ADMIN_DEBIT` entries), and net platform revenue for that range.
- **FR-018**: The financial report MUST render commission collected as a per-day series for ranges up to 60 days, and as a per-week series for longer ranges.
- **FR-019**: The system MUST provide a driver balance overview listing every driver with a wallet record, their current balance and reserved amount, sorted by balance ascending by default, with drivers at or below zero available balance visually flagged.
- **FR-020**: The system MUST allow an admin to export a generated financial report for a selected date range as a downloadable file whose totals match the on-screen figures exactly. The export MUST be generated on-demand and streamed directly to the requesting admin's browser; no export file is persisted server-side, consistent with treating this as an ordinary admin-panel download rather than as sensitive-document handling (see Clarifications, Session 2026-08-02).
- **FR-021**: Drivers without a wallet record MUST appear in the driver balance overview with an effective balance of 0.00 EGP, consistent with `011-financial-system`.

**Cross-Cutting**

- **FR-022**: All dashboard, user-management, verification-tooling, and financial-reporting endpoints introduced by this phase MUST be accessible only to authenticated users with the `admin` role; all other callers MUST receive an authorization error.
- **FR-023**: Every user suspension, reinstatement, or verification unlock action taken through the interfaces introduced in this phase MUST be recorded in the existing `admin_audit_logs` mechanism with admin identity, action type, target user, reason, and timestamp — no parallel audit mechanism is introduced.
- **FR-024**: All date/time period boundaries used in the dashboard and financial reports (e.g., "today", "last 7 days") MUST be computed in a single fixed reference timezone (Africa/Cairo) so totals are consistent across every screen.

### Key Entities

- **No new persisted entities are introduced by this phase.** Every capability is a read/aggregation and search/filter layer over data already established in prior phases:
  - `profiles` (`003-auth-verification`) — searched, filtered, and displayed in the user management views.
  - `verification_submissions` (`003-auth-verification`) — searched, filtered, and annotated with a computed age in the enhanced queue.
  - `admin_audit_logs` (`003-auth-verification`, extended in `014-trust-community`) — the single audit sink for all suspend/reinstate/unlock actions in this phase; no new action types are required.
  - `bookings`, `rides` (`004-ride-management`, `009-passenger-experience`) — aggregated for dashboard ride counts and displayed in per-user activity views.
  - `ratings`, `reports` (`014-trust-community`) — displayed in per-user activity views and aggregated for the dashboard's open-reports KPI.
  - `driver_wallets`, `DriverLedgerEntry` (`011-financial-system`) — aggregated for commission/revenue reporting and the driver balance overview; displayed per-user in the user detail view.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An admin can determine overall platform health (user growth, ride volume, revenue, and queue backlogs) for any of the four standard periods within 5 seconds of opening the dashboard, without navigating to a second screen.
- **SC-002**: An admin can locate a specific user by partial name, phone, or email and reach their full activity view in under 15 seconds, down from requiring manual scroll-and-scan through an unfiltered list today.
- **SC-003**: 100% of verification submissions pending longer than 24 hours are visually flagged, and zero submissions are missed due to lack of visibility (verified by seeding aged submissions and confirming each is flagged).
- **SC-004**: An admin can produce a financial report and export it for any date range within 10 seconds of selecting the range.
- **SC-005**: 100% of suspend, reinstate, and verification-unlock actions taken through this phase's interfaces are traceable to an admin identity, a reason, and a timestamp via the audit log.
- **SC-006**: Drivers at or below zero available balance are identifiable from the driver balance overview in a single view, with zero need to open individual driver wallets to find them.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Dashboard, user-search, verification-search, and financial-report endpoints MUST respond within 500ms at p95 for the standard periods/ranges (up to 90 days), under expected admin-panel load (single-digit concurrent admins).
- **NFR-002**: User list search and filter operations MUST return results within 300ms at p95 for a user base of up to 50,000 profiles.
- **NFR-003**: All aggregation queries introduced by this phase MUST be read-only against existing tables — this phase MUST NOT introduce write paths beyond the existing suspend/reinstate/unlock actions it re-exposes.
- **NFR-004**: Financial report exports MUST be generated without blocking the admin's ability to navigate elsewhere in the panel while generation is in progress for large ranges.
- **NFR-005**: All endpoints introduced by this phase MUST enforce admin-only access consistent with the existing admin authentication middleware from `003-auth-verification`; no new authentication mechanism is introduced.
- **NFR-006**: Every suspend, reinstate, and unlock action taken through this phase's interfaces MUST emit a structured log entry (admin identity, action type, target user, duration) consistent with the observability standard established in prior phases.
- **NFR-007**: Financial report exports MUST NOT be persisted server-side beyond the request/response cycle and MUST NOT introduce a signed-URL or private-storage mechanism — the export is an ordinary authenticated admin-panel download, not sensitive-document handling.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `003-auth-verification` — `profiles`, `verification_submissions`, `admin_audit_logs`, and the admin authentication/authorization middleware are reused directly; this phase adds no new admin identity or credentialing mechanism.
  - `004-ride-management` / `009-passenger-experience` — `rides` and `bookings` are the source of dashboard ride counts and per-user activity history.
  - `011-financial-system` — `driver_wallets` and `DriverLedgerEntry` are the source of all commission/revenue figures and the driver balance overview; this phase is the reporting layer that spec explicitly deferred.
  - `014-trust-community` — `ratings` and `reports` are the source of per-user activity history and the dashboard's open-reports KPI; the existing moderation queue continues to be the action surface for report-driven suspensions, while this phase adds a second, general-purpose suspend/reinstate entry point on the user detail page.

- **Data**:
  - Supabase PostgreSQL — no new tables or columns; this phase is read/aggregation queries plus reuse of existing write paths (suspend, reinstate, unlock, approve, reject).

---

## Out-of-Scope

- **Creating or managing additional admin operator accounts** — admin credentials remain provisioned out-of-band by a platform operator via Supabase Auth, per the existing `003-auth-verification` assumption; this phase does not add an in-panel "create admin user" flow.
- **Changing a user's fundamental role** (passenger ↔ driver ↔ admin) — role is assigned at onboarding and remains fixed; this phase manages account status (suspend/reinstate), not role reassignment.
- **Real-time/live-updating dashboard** — KPIs and charts reflect the state as of page load or an explicit refresh; push-based live updates are not required for this phase.
- **Automated alerting** (e.g., emailing an admin when a driver's balance goes negative or the verification queue backs up) — this phase surfaces the information visually; proactive automated notification to admins is a future extension.
- **Configurable or custom report builders** — the financial report and dashboard periods are fixed presets (today / 7 / 30 / 90 days); ad-hoc custom-metric report building is out of scope.
- **Multi-tier admin roles or permissions** (e.g., a "read-only auditor" role distinct from a full admin) — this phase continues the existing single-tier admin model established in `003-auth-verification` and reaffirmed in `014-trust-community`.
- **Demand forecasting, fraud detection, or AI-driven anomaly flagging on the dashboard** — these remain distinct future roadmap items (`Phase 13 — Advanced AI & Continuous Learning`); this phase's dashboard surfaces raw and aggregated counts only.

---

## Technical Considerations

- All dashboard KPIs, trend charts, and financial reports are computed via read-only aggregation queries against existing tables; no new tables, columns, or background jobs are required, keeping this phase a low-risk reporting layer on top of already-shipped, already-audited write paths.
- The user detail view's unified activity display (rides, bookings, ratings, reports, wallet) should compose existing per-domain queries rather than introducing a new denormalized "user activity" table, avoiding a second source of truth that could drift from the underlying domain tables.
- The 24-hour aging flag on pending verification submissions and the zero-balance flag on the driver overview are computed at query time from existing timestamp/balance columns, not maintained as separate stored flags.
- Financial report export generation should stream or batch large date ranges directly to the response rather than materializing the entire ledger in memory or writing an intermediate file to storage, consistent with the platform's existing performance-conscious patterns for ledger reads and with the export being treated as an ordinary download (NFR-007).
- Search across `profiles` and `verification_submissions` should use case-insensitive partial matching (e.g., `ILIKE` or equivalent), consistent with expected admin search ergonomics.

---

## Assumptions

- **Fixed reference timezone**: All "today"/period boundaries use Africa/Cairo, the platform's sole operating market, rather than per-admin browser timezone, so every admin sees identical totals.
- **Single-tier admin role, continued**: Any user with `profiles.role = 'admin'` has full access to every capability in this phase; there is no partial/read-only admin tier for MVP, consistent with `014-trust-community`'s assumption.
- **CSV as the export format**: A simple CSV export satisfies the financial reporting export requirement (FR-020); no PDF generation or scheduled/emailed report delivery is assumed.
- **Fixed period presets, not arbitrary ranges, for the dashboard**: Today / 7 / 30 / 90 days covers expected admin usage; the financial report screen alone supports an arbitrary admin-chosen date range, since financial reconciliation often needs non-standard windows (e.g., a specific week for a reconciliation task).
- **No new suspension category**: General-purpose suspension from the user detail page (FR-009), for passenger and driver accounts, uses the same `verification_status = 'suspended'` value as safety-driven suspension from the Phase 10 moderation queue; the system does not distinguish "why" a user is suspended beyond the free-text reason already captured in the audit log.
- **English-only admin UI**: Consistent with the platform's English-first MVP policy; Arabic/RTL remains deferred platform-wide.
- **Admin panel remains desktop-only**: Consistent with `003-auth-verification`'s assumption that the admin panel is used by internal staff on desktop browsers; no mobile-responsive admin requirement is introduced by this phase.
