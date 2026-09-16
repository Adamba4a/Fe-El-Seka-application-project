# Feature Specification: Performance Capacity

Created: 2026-09-16

## Business Objective
Measure Triplyy's real API capacity before increasing infrastructure, then provide a repeatable way to find the first bottleneck without creating production data.

**Constitutional Domain**: Shared Foundations. **Affected Applications**: API operations and production infrastructure.

## User Scenarios & Acceptance Criteria

### User Story 1 — Inspect live capacity (P1)
An operator can retrieve a protected, per-instance 15-minute request summary with throughput, error rate, p50/p95 latency, slowest endpoint groups, inflight requests, and database-pool occupancy.

1. Without the internal secret, metrics are rejected.
2. The response contains no request bodies, query strings, emails, access tokens, user IDs, or raw dynamic paths.
3. A slow or failing endpoint is included in p95/error measurements.

### User Story 2 — Run a safe capacity test (P1)
An operator can run a staged, read-only k6 test locally or against a non-production target. Production requires explicit opt-in and non-production tokens.

1. The script refuses a non-local target unless `ALLOW_PRODUCTION=true` is supplied.
2. It performs health and authorized read/search traffic only; no signup, booking, ride creation, wallet, location or admin mutation occurs.
3. It fails when latency/error thresholds are breached and emits a clear summary.

### User Story 3 — Scale from evidence (P2)
An operator has an ordered runbook for baseline, ramp, bottleneck identification, and Bunny/Supabase scaling.

## Functional Requirements
- FR-001: Record completed HTTP requests in a bounded in-memory rolling window of 15 minutes and 10,000 samples per worker.
- FR-002: Normalize endpoint labels and cap unknown routes as `/other` to prevent metric-cardinality or data-exposure problems.
- FR-003: Exclude the metrics route itself. Metrics are per process, not globally aggregated across replicas.
- FR-004: Protect `GET /api/internal/metrics` with the existing `X-Internal-Secret`; return 403 when missing, invalid or unconfigured.
- FR-005: Load traffic must use only explicit test accounts and never exercise write endpoints.

## Non-Functional Requirements
Metrics add no network calls, database writes or external dependencies in the request path. Recording is O(1). The endpoint exposes aggregate operational data only.

## Out of Scope
Autoscaling configuration changes, buying more capacity, production traffic generation, distributed metrics storage, alert paging, database schema changes, and application feature changes.
