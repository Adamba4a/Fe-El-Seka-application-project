# Quickstart: Dockerization

**Branch**: `005-dockerization` | **Date**: 2026-06-17

This guide covers 8 validation scenarios proving the Dockerization feature works end-to-end.

---

## Prerequisites

- Docker Engine 24+ and Docker Compose v2 (`docker compose version`)
- Supabase CLI (`supabase --version`)
- pnpm 8+ and Node 20+ (for pre-flight build check only)
- A populated `services/api/.env`, `services/ai/.env`, `apps/main/.env` (copy from `.env.example` files)

---

## Setup: Local Development Stack

```bash
# 1. Start Supabase local DB (runs its own Docker containers)
supabase start

# 2. Build and start the development stack
docker compose up --build

# 3. Confirm all 4 containers are running
docker compose ps
# Expected: api, ai, main, nginx — all "healthy" or "running"
```

---

## Scenario 1 — Full Stack Starts in Under 60 Seconds (SC-001)

**Goal**: Verify the development stack comes up cleanly from a cold start.

```bash
time docker compose up --build
# Expected: all services reachable within 60 seconds of compose completing
```

**Check**:
```bash
curl http://localhost/api/health      # → {"status":"ok","service":"api"}
curl http://localhost/ai/health       # → {"status":"ok","service":"ai"}
curl http://localhost/                # → HTTP 200 (Next.js HTML response)
```

**Pass criteria**: All three return 200. Total elapsed time < 60 seconds.

---

## Scenario 2 — nginx Routes Traffic Correctly (FR-006)

**Goal**: Confirm nginx routes `/api/`, `/ai/`, and `/` to the correct upstream.

```bash
# API backend
curl -v http://localhost/api/v1/health
# Expected: response from FastAPI (check "x-powered-by" or body shape)

# AI service
curl -v http://localhost/ai/health
# Expected: response from AI FastAPI

# Frontend
curl -v http://localhost/
# Expected: Next.js HTML (check for "<html" in response)
```

**Pass criteria**: Each path reaches the correct service — confirmed by response body, not just status code.

---

## Scenario 3 — Hot Reload in Development (US1 — Scenario 2 & 3)

**Goal**: Confirm source file edits are reflected without container restarts.

**Backend**:
```bash
# Edit a comment in services/api/app/api/health.py
# Check that the change is reflected in the running container (file is volume-mounted)
docker compose exec api python -c "import app.api.health; print('ok')"
```

**Frontend**:
```bash
# Edit apps/main/src/app/page.tsx — add a visible string
# Open http://localhost/ in browser — Next.js fast refresh should reflect change within 5 seconds
```

**Pass criteria**: Changes visible in < 5 seconds; no `docker compose restart` required.

---

## Scenario 4 — No Secrets in Production Image (SC-003, NFR-001)

**Goal**: Confirm no secret values are baked into any layer.

```bash
# Build production image locally
docker build -t test-api-secret-check -f services/api/Dockerfile services/api/

# Scan all layers for common secret patterns
docker history test-api-secret-check --no-trunc | grep -iE "(password|secret|key|token)"
# Expected: no matches

# Inspect env vars set at build time
docker inspect test-api-secret-check | jq '.[0].Config.Env'
# Expected: only PYTHONUNBUFFERED=1 and PATH — no secrets
```

**Pass criteria**: Zero secret-pattern matches in history or ENV layer.

---

## Scenario 5 — Production Image Sizes (SC-002)

**Goal**: Verify production images are within size limits.

```bash
# Build production images
docker build -t fe-el-seka-api:test -f services/api/Dockerfile services/api/
docker build -t fe-el-seka-ai:test -f services/ai/Dockerfile services/ai/
docker build -t fe-el-seka-main:test -f apps/main/Dockerfile .

docker images --format "{{.Repository}}\t{{.Size}}" | grep fe-el-seka
```

**Pass criteria**:
- `fe-el-seka-api` < 300 MB
- `fe-el-seka-ai` < 700 MB (ML deps are large; SC-002 targets are for api/frontend only)
- `fe-el-seka-main` < 200 MB

---

## Scenario 6 — Non-Root Container Processes (FR-003, NFR-002)

**Goal**: Confirm no container runs as root.

```bash
docker compose up -d
docker compose exec api whoami      # Expected: appuser
docker compose exec ai whoami       # Expected: appuser
docker compose exec main whoami     # Expected: nextjs
docker compose exec nginx whoami    # Expected: nginx (nginx image default)
```

**Pass criteria**: No service returns `root`.

---

## Scenario 7 — Production Compose Starts with Pre-Built Images (US2)

**Goal**: Simulate a production deploy using pulled images (not local builds).

```bash
# Pull published images (replace with real tag after first CI push)
docker pull ghcr.io/adamba4a/fe-el-seka-api:latest
docker pull ghcr.io/adamba4a/fe-el-seka-ai:latest
docker pull ghcr.io/adamba4a/fe-el-seka-main:latest

# Start production stack
docker compose -f docker-compose.prod.yml up -d

# Check health
curl http://localhost/api/health     # → 200
curl http://localhost/               # → 200
docker compose -f docker-compose.prod.yml ps
# Expected: all services "healthy"
```

**Pass criteria**: Stack starts from pulled images; no source code on host is accessed.

---

## Scenario 8 — CI Pipeline Builds, Scans, and Publishes (US3)

**Goal**: Verify the GitHub Actions workflow runs end-to-end on a push to `main`.

**Steps**:
1. Merge a trivial change to `main` (e.g., update a comment in `services/api/app/api/health.py`)
2. Navigate to the repository → Actions → `Docker CI` workflow
3. Observe jobs: `build-api`, `build-ai`, `build-main` (parallel) → `scan-api`, `scan-ai`, `scan-main` → `push`

**Pass criteria**:
- All build jobs complete with exit 0
- Trivy scans report 0 CRITICAL/HIGH CVEs (or fail the run if found)
- `push` job runs only on `main` merge (not on PR runs)
- Images appear in `ghcr.io/adamba4a` packages with both `latest` and `<sha>` tags

---

## Docker Setup Section (appended to quickstart reference)

### One-Time: Set GHCR Packages to Public

After the first successful CI push:
1. Go to `github.com/Adamba4a777` → **Packages**
2. Click each of `fe-el-seka-api`, `fe-el-seka-ai`, `fe-el-seka-main`
3. **Package settings** → **Change visibility** → **Public**

This enables production servers to `docker pull` without credentials.

### One-Time: Enable `next.config.mjs` Standalone Output

```js
// apps/main/next.config.mjs
const nextConfig = {
  output: 'standalone',           // ← add this line
  transpilePackages: ["@fe-el-seka/ui", "@fe-el-seka/shared"],
};
```

Verify the build works before proceeding:
```bash
pnpm --filter @fe-el-seka/main build
# Expected: .next/standalone/server.js exists
```
