# Contract: Docker Setup

**Branch**: `005-dockerization` | **Date**: 2026-06-17

This document defines the interface contracts for all Docker-related artifacts: Dockerfile patterns, nginx routing, health check endpoints, and the GitHub Actions workflow API.

---

## 1. Dockerfile Contracts

### 1.1 Python Services (API + AI) — Build Interface

Both `services/api/Dockerfile` and `services/ai/Dockerfile` MUST satisfy this interface:

```
Build context:   services/<service>/
Required files:  pyproject.toml, uv.lock, app/
Build args:      none (all config via runtime env vars)
Exposed port:    8000
Final CMD:       uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Health check:    HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
                   CMD curl -f http://localhost:8000/health || exit 1
Non-root user:   USER appuser (UID 1001, created in runner stage)
```

**Stage naming contract** (required for GHA layer caching):
```
FROM python:3.11-slim AS builder
FROM python:3.11-slim AS runner
```

---

### 1.2 Frontend — Build Interface

`apps/main/Dockerfile` MUST satisfy this interface:

```
Build context:   . (monorepo root)
Dockerfile path: apps/main/Dockerfile
Required files:  package.json, pnpm-lock.yaml, apps/main/, packages/
Build args:      none
Exposed port:    3000
Final CMD:       node server.js
Working dir:     /app (runner stage)
Health check:    HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
                   CMD wget -qO- http://localhost:3000/api/health || exit 1
Non-root user:   USER nextjs (UID 1001, GID 1001)
```

**Prerequisite**: `apps/main/next.config.mjs` must contain `output: 'standalone'` before this Dockerfile is valid.

**Stage naming contract**:
```
FROM node:20-alpine AS deps
FROM node:20-alpine AS builder
FROM node:20-alpine AS runner
```

---

## 2. nginx Routing Contract

### Route Table

| Pattern | Match type | Upstream | Upstream port |
|---|---|---|---|
| `/api/` | Prefix | `api` | `8000` |
| `/ai/` | Prefix | `ai` | `8000` |
| `/` | Catch-all | `main` | `3000` |

### nginx.conf Skeleton

```nginx
upstream api_upstream  { server api:8000; }
upstream ai_upstream   { server ai:8000; }
upstream main_upstream { server main:3000; }

server {
    listen 80;
    
    gzip on;
    gzip_types text/html text/css application/json application/javascript;
    client_max_body_size 10m;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    location /api/ {
        proxy_pass http://api_upstream;
    }

    location /ai/ {
        proxy_pass http://ai_upstream;
    }

    location / {
        proxy_pass http://main_upstream;
    }
}
```

---

## 3. Health Check Endpoint Contract

All three services MUST expose a health check at `/health` (Python) or `/api/health` (Next.js).

### 3.1 API Service Health Check

```
GET /health
Authorization: none
Response 200:
  Content-Type: application/json
  Body: {"status": "ok", "service": "api"}
Response 503 (DB unreachable):
  Body: {"status": "degraded", "service": "api", "reason": "database_unavailable"}
```

### 3.2 AI Service Health Check

```
GET /health
Authorization: none
Response 200:
  Content-Type: application/json
  Body: {"status": "ok", "service": "ai"}
Response 503 (model not loaded):
  Body: {"status": "degraded", "service": "ai", "reason": "model_not_loaded"}
```

### 3.3 Frontend Health Check

```
GET /api/health
Authorization: none
Response 200:
  Content-Type: application/json
  Body: {"status": "ok", "service": "main"}
```

This Next.js Route Handler lives at `apps/main/src/app/api/health/route.ts`.

---

## 4. Compose Service Contract

Both compose files MUST define services with these names (used as DNS hostnames by nginx):

| Compose service name | DNS hostname | Container port |
|---|---|---|
| `api` | `api` | `8000` |
| `ai` | `ai` | `8000` |
| `main` | `main` | `3000` |
| `nginx` | `nginx` | `80` (host-mapped) |

**Network name**:
- Development: `fe-el-seka-dev`
- Production: `fe-el-seka-prod`

---

## 5. GitHub Actions Workflow Contract

### Workflow file: `.github/workflows/docker.yml`

**Triggers**:
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

**Required permissions block**:
```yaml
permissions:
  contents: read
  packages: write   # required for GHCR push
```

**Build job matrix (one per service)**:

| Job name | `service` | `context` | `dockerfile` |
|---|---|---|---|
| `build-api` | `api` | `services/api` | `services/api/Dockerfile` |
| `build-ai` | `ai` | `services/ai` | `services/ai/Dockerfile` |
| `build-main` | `main` | `.` (root) | `apps/main/Dockerfile` |

**Scan job (Trivy)**:
```yaml
- uses: aquasecurity/trivy-action@0.24.0
  with:
    image-ref: ${{ env.IMAGE_REF }}
    format: table
    exit-code: 1                  # fail workflow on findings
    severity: CRITICAL,HIGH
    ignore-unfixed: false
```

**Push condition** (all three images):
```yaml
if: github.ref == 'refs/heads/main'
```

**Image tags**:
```yaml
tags: |
  ghcr.io/adamba4a/fe-el-seka-${{ matrix.service }}:latest
  ghcr.io/adamba4a/fe-el-seka-${{ matrix.service }}:${{ github.sha }}
```

---

## 6. `.dockerignore` Contract

Each service must exclude these categories:

| Category | Patterns |
|---|---|
| Secrets | `.env`, `.env.*`, `*.pem`, `*.key` |
| VCS | `.git/`, `.gitignore` |
| Dev tooling | `.venv/`, `__pycache__/`, `*.pyc`, `node_modules/`, `.next/` |
| Tests | `tests/`, `**/*.test.*`, `**/*.spec.*` |
| IDE | `.vscode/`, `.idea/`, `*.iml` |
| Docs/Specs (root only) | `specs/`, `docs/`, `*.md` |
| Build artefacts | `dist/`, `build/`, `*.egg-info/` |
| ML artefacts (AI only) | `data/`, `models/`, `*.pkl`, `*.joblib`, `pipelines/` |
