# Contract: Health Check Endpoints

**Branch**: `001-platform-foundation` | **Date**: 2026-06-12
**Spec**: [../spec.md](../spec.md) | FR-004, FR-012, SC-006

---

## Overview

Both `services/api` (backend) and `services/ai` (AI scaffold) expose a health check endpoint. The contract is identical for both services. Consumers (CI pipelines, load balancers, monitoring) use this endpoint to determine service readiness.

---

## Endpoint

```
GET /health
```

**Authentication**: None required. Health check is public.

**Rate limiting**: Not applied in Phase 1.

---

## Response — Healthy

**HTTP Status**: `200 OK`

**Content-Type**: `application/json`

```json
{
  "status": "ok",
  "database": "connected",
  "version": "0.1.0"
}
```

---

## Response — Degraded (database unreachable)

**HTTP Status**: `200 OK`

The service stays running and returns 200 even when degraded, so that load balancers and monitoring tools can distinguish between "service is down" (connection refused / timeout) and "service is up but a dependency is degraded" (200 with `"status": "degraded"`).

```json
{
  "status": "degraded",
  "database": "disconnected",
  "version": "0.1.0"
}
```

---

## Response — Service Down

**HTTP Status**: No response (connection refused or TCP timeout)

This case is handled at the infrastructure/load-balancer level, not by the application.

---

## Field Definitions

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `status` | string | `"ok"` \| `"degraded"` | Overall service health. Degraded if any critical dependency is unavailable. |
| `database` | string | `"connected"` \| `"disconnected"` | Result of the last database connectivity probe. |
| `version` | string | semver string | Service version from package metadata (e.g., `pyproject.toml` version field). |

---

## Timing Requirement

The health check endpoint MUST respond within **1 second** under normal conditions (SC-006). The database probe MUST use a short timeout (≤500 ms) to avoid blocking the response if the database is slow or unreachable.

---

## Services Using This Contract

| Service | Path | Base URL (local dev) |
|---------|------|----------------------|
| Backend API | `services/api` | `http://localhost:8000/health` |
| AI Service Scaffold | `services/ai` | `http://localhost:8001/health` |

---

## Versioning

This contract is internal-only for Phase 1. No API versioning prefix (`/v1/`) is applied to the health check. When the API is versioned in a future phase, health check remains at `/health` (not `/v1/health`).
