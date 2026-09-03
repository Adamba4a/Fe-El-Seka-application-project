# Implementation Plan: Fraud Signal Capture

**Branch**: `030-fraud-signal-capture` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/030-fraud-signal-capture/spec.md`

## Summary

Add a new `fraud_signals` table that records one hashed-device/hashed-IP row per trust-relevant event (signup,
login, ride posting, booking creation). Each of the four request handlers gets a `Request` parameter (to read the
source IP and an optional `X-Device-Id` header) and a `BackgroundTasks` parameter, firing a best-effort
`fraud_signal_service.record_signal(...)` call after the handler's existing logic succeeds — mirroring the
established `match_logging_service.persist_match_events` pattern (013-match-learning-foundation) exactly, called
via `background_tasks.add_task(...)` rather than the `asyncio.create_task` mechanism 029 used. Both the device ID
and the IP are hashed with server-side-keyed HMAC-SHA256 before being persisted — never the raw values. One new
Supabase Postgres table and one new service module (`fraud_signal_service.py`); `services/ai` and the frontend
`apps/main` client (device-ID header generation, tracked as a separate task) are the only other touchpoints.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend) — plus one small `apps/main` (Next.js/TypeScript) client
change to attach the `X-Device-Id` header (research.md R5), tracked as its own task in `tasks.md`.

**Primary Dependencies**: FastAPI (`BackgroundTasks`, `Request`), `asyncpg` (raw SQL, no ORM), Python stdlib
`hmac`/`hashlib` (research.md R2) — no new third-party dependencies.

**Storage**: Supabase PostgreSQL — 1 new table: `fraud_signals`. No changes to `users`/`profiles`, `rides`, or
`bookings`.

**Testing**: pytest + `asyncpg` test-DB fixtures (existing `services/api` convention); no new test tooling.

**Target Platform**: Linux server (FastAPI via uvicorn) — `services/api`, plus a minimal `apps/main` client
interceptor addition.

**Project Type**: Monorepo — primarily backend (`services/api`), with one small shared client-side addition in
`apps/main` (Principle VII). `services/ai` is unmodified.

**Performance Goals**: Zero added synchronous latency to any of the four instrumented request paths (signal write
is fire-and-forget via `BackgroundTasks`, per FR-005/NFR-001 — same mechanism as `persist_match_events`).

**Constraints**:
- Signal persistence MUST NOT block, delay, or fail any of the four instrumented requests (FR-005, FR-006) —
  implemented via `background_tasks.add_task`, wrapped in its own try/except inside the service function so it can
  never raise into the caller (mirrors `persist_match_events`'s own try/except).
- Only one-way HMAC-SHA256 digests are ever stored, never raw device ID or IP (FR-002, FR-003, NFR-004) — the HMAC
  secret lives in `Settings` (`app/core/config.py`), server-side config only, never in client code or a DB column
  (NFR-003).
- `X-Device-Id` is optional; its absence never blocks a request and stores `hashed_device_id = NULL` (FR-002,
  Edge Cases).
- `request.client.host` is used as-is for the source IP — uvicorn's existing `--proxy-headers
  --forwarded-allow-ips=*` startup flags already resolve it correctly behind the reverse proxy (research.md R3);
  no manual `X-Forwarded-For` parsing is added.
- `asyncpg` raw SQL only, no ORM, per existing `services/api` convention.
- No retention/purge job for this table (spec Out-of-Scope) — unlike 029-driver-gps-trace-history, rows are kept
  indefinitely.
- No new passenger- or driver-facing UI, and no user-visible indication signal capture is happening (spec
  Out-of-Scope) — the only client change is an outgoing-request header, invisible in the UI.

**Scale/Scope**: One new migration file; one new service module; four existing request handlers extended across
three router files (`auth/router.py` ×2 endpoints, `rides/router.py` ×1, `bookings/router.py` ×1); one small
`apps/main` client-side change to attach the device-ID header.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | No change to the driver-creates/passenger-joins model. Purely additive instrumentation on existing auth/ride/booking paths. |
| ✅ | II — Route Intelligence Over Geographic Proximity | No matching/ranking logic touched. |
| ✅ | III — Trust Before Transportation | Core domain — directly builds the data foundation for future fraud/trust detection, without itself making any trust decision (no scoring, no blocking, no flagging — spec Out-of-Scope). |
| ✅ | IV — AI-Augmented Transportation | Directly closes data-collection gap #3 from the 2026-09-03 roadmap audit, the named blocker for the roadmap's TBD `fraud-detection` item — "training data cannot be reconstructed retroactively," same rationale as 013 and 029. `services/ai` remains unmodified. |
| ✅ | V — Mobile-First UX | No UI changes (Out-of-Scope) beyond an invisible outgoing-request header. N/A. |
| ✅ | VI — Modular Domain-Driven Architecture | Scoped entirely to the AI Integration / Trust & Community domain, touching only the four existing request paths it instruments. |
| ✅ | VII — Shared Foundations, Independent Applications | The `apps/main` header-attachment change is a shared client concern (single app serving both passenger/driver roles); no new apps or services. |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/030-fraud-signal-capture/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   └── data-schema.md       # Phase 1 output — DB schema as the future fraud-detection consumer contract
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Database Migration ────────────────────────────────────────────────────────
supabase/migrations/
└── 20260903000002_fraud_signal_capture.sql
                             # NEW — fraud_signals table, indexes on
                             #       (hashed_device_id) WHERE NOT NULL, (hashed_ip),
                             #       and (user_id, created_at). RLS enabled with no
                             #       public policies (service-role only, same
                             #       pattern as match_events/driver_location_history).

# ── Backend — New Service ─────────────────────────────────────────────────────
services/api/app/services/
└── fraud_signal_service.py
                             # NEW — record_signal(event_type, user_id, device_id,
                             #       ip_address) -> fire-and-forget entry point,
                             #       hashes device_id/ip_address via HMAC-SHA256
                             #       before insert; called via
                             #       background_tasks.add_task from each of the
                             #       four instrumented handlers (mirrors
                             #       match_logging_service.persist_match_events).

# ── Backend — Config — Extended ───────────────────────────────────────────────
services/api/app/core/config.py
                             # EXTEND — add fraud_signal_hmac_secret: str field to
                             #   Settings (same pattern as internal_secret /
                             #   webhook_secret).

# ── Backend — Extended ────────────────────────────────────────────────────────
services/api/app/api/auth/router.py
                             # EXTEND — request_otp/verify_otp (signup) and
                             #   sign_in_with_password (login): add `request:
                             #   Request` and `background_tasks: BackgroundTasks`
                             #   params, fire record_signal after each existing
                             #   call succeeds.

services/api/app/api/rides/router.py
                             # EXTEND — create_ride: same addition, event_type
                             #   'ride_posted'.

services/api/app/api/bookings/router.py
                             # EXTEND — book_ride: same addition, event_type
                             #   'booking_created'.

# ── Frontend — Extended ───────────────────────────────────────────────────────
apps/main/src/lib/api/
                             # EXTEND — the shared fetch/client wrapper: generate
                             #   and persist (e.g. localStorage) a per-install
                             #   UUID on first use, attach it as X-Device-Id on
                             #   outgoing requests (research.md R5). Exact file
                             #   TBD at /speckit-tasks time — depends on this
                             #   app's existing HTTP client wrapper location.

# ── No changes ─────────────────────────────────────────────────────────────────
services/api/app/services/auth_service.py
                             # UNCHANGED — the Supabase Auth calls this feature
                             # instruments, not modifies.
services/ai/                # UNCHANGED — instrumentation only (see spec
                             # Out-of-Scope); the future fraud-detection model is
                             # a separate, later roadmap item.
apps/admin/                  # UNCHANGED — no admin-facing surface for this
                             # feature (spec Out-of-Scope).
```

**Structure Decision**: Option 4 (Monorepo), primarily backend with one small shared-client addition. The new
service module follows the existing `services/api/app/services/` pattern (alongside `match_logging_service.py`,
`location_history_service.py`). No new Pydantic request/response models are needed for the four instrumented
endpoints — the device ID arrives via a request header, not a body field (research.md R4), and the new table is
written via raw SQL from within the service layer, never exposed through any API response.

## Complexity Tracking

*No Constitution Check violations — this section is not required.*
