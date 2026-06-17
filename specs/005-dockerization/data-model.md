# Data Model: Dockerization

**Branch**: `005-dockerization` | **Date**: 2026-06-17

This document defines the structural entities introduced or modified by the Dockerization phase: Docker images, compose services, environment variable interfaces, and GitHub Actions workflow structure.

---

## 1. Docker Images

Three production images are defined. Each follows the multi-stage build pattern.

### 1.1 API Image (`fe-el-seka-api`)

| Attribute | Value |
|---|---|
| Registry path | `ghcr.io/adamba4a/fe-el-seka-api:<tag>` |
| Build context | `services/api/` |
| Dockerfile | `services/api/Dockerfile` |
| Base image (builder) | `python:3.11-slim` + uv binary from `ghcr.io/astral-sh/uv:latest` |
| Base image (runner) | `python:3.11-slim` |
| Exposed port | `8000` |
| Non-root user | `appuser` (UID 1001) |
| Health check | `GET /health` → `{"status": "ok"}` |
| Tags on push | `latest`, `<full-commit-sha>` |

**Build stages**:
1. `builder` — copies `pyproject.toml`, `uv.lock`; runs `uv sync --frozen --no-dev --no-editable`
2. `runner` — copies `.venv` from builder + `app/` source; sets `ENV PATH`, `PYTHONUNBUFFERED=1`

**Excluded by `.dockerignore`**: `tests/`, `*.pyc`, `__pycache__/`, `.env*`, `.venv/`, `data/`, `*.ipynb`, `.mypy_cache/`, `.ruff_cache/`

---

### 1.2 AI Service Image (`fe-el-seka-ai`)

| Attribute | Value |
|---|---|
| Registry path | `ghcr.io/adamba4a/fe-el-seka-ai:<tag>` |
| Build context | `services/ai/` |
| Dockerfile | `services/ai/Dockerfile` |
| Base image (builder) | `python:3.11-slim` + uv binary |
| Base image (runner) | `python:3.11-slim` |
| Exposed port | `8000` |
| Non-root user | `appuser` (UID 1001) |
| Health check | `GET /health` → `{"status": "ok"}` |
| Tags on push | `latest`, `<full-commit-sha>` |

**Build stages**: identical pattern to API image (builder + runner via uv).

**Note**: AI service uses heavy dependencies (XGBoost, scikit-learn, pandas, numpy). The builder stage installs all of these into `.venv`; runner stage copies only `.venv` and `app/`. Model artefacts (`.pkl`, `.joblib`) are loaded at runtime from Supabase Storage — not baked into the image.

**Excluded by `.dockerignore`**: same as API image, plus `models/`, `notebooks/`, `*.pkl`, `*.joblib`, `pipelines/`

---

### 1.3 Frontend Image (`fe-el-seka-main`)

| Attribute | Value |
|---|---|
| Registry path | `ghcr.io/adamba4a/fe-el-seka-main:<tag>` |
| Build context | `.` (monorepo root — required for `packages/` shared deps) |
| Dockerfile | `apps/main/Dockerfile` |
| Base image (deps + builder) | `node:20-alpine` |
| Base image (runner) | `node:20-alpine` |
| Exposed port | `3000` |
| Non-root user | `nextjs` (UID 1001, GID 1001) |
| Health check | `GET /api/health` |
| Tags on push | `latest`, `<full-commit-sha>` |

**Build stages**:
1. `deps` — installs `node_modules` from root `pnpm-lock.yaml` with `pnpm install --frozen-lockfile`
2. `builder` — runs `pnpm --filter main build`; produces `.next/standalone/`
3. `runner` — copies `.next/standalone/`, `.next/static/`, `public/`; runs `node server.js`

**Prerequisite**: `output: 'standalone'` must be set in `apps/main/next.config.mjs` before this image can be built.

**Excluded by `.dockerignore`** (at monorepo root for this build): `node_modules/`, `.next/`, `**/.env*`, `**/*.test.*`, `**/*.spec.*`, `.git/`, `specs/`, `docs/`

---

## 2. Compose Services

Two compose files share the same service definitions with different configuration.

### 2.1 Development Compose (`docker-compose.yml`)

| Service | Image source | Volumes | Purpose |
|---|---|---|---|
| `api` | Build `services/api/` | `./services/api/app:/app/app` | FastAPI with hot-reload |
| `ai` | Build `services/ai/` | `./services/ai/app:/app/app` | AI service with hot-reload |
| `main` | Build `.` (root) | `./apps/main/src:/app/src`, `./apps/main/public:/app/public` | Next.js with hot-reload |
| `nginx` | `nginx:1.27-alpine` | `./nginx/nginx.dev.conf:/etc/nginx/conf.d/default.conf` | Reverse proxy |

**Network**: `fe-el-seka-dev` (bridge)

**Ports**: nginx exposes `80:80` only. Individual services expose no host ports.

**Supabase**: Not in compose. Developer runs `supabase start` before `docker compose up`. `SUPABASE_URL` points to `http://host.docker.internal:54321`.

---

### 2.2 Production Compose (`docker-compose.prod.yml`)

| Service | Image | Restart | `mem_reservation` |
|---|---|---|---|
| `api` | `ghcr.io/adamba4a/fe-el-seka-api:latest` | `always` | 256 MB |
| `ai` | `ghcr.io/adamba4a/fe-el-seka-ai:latest` | `always` | 512 MB |
| `main` | `ghcr.io/adamba4a/fe-el-seka-main:latest` | `always` | 128 MB |
| `nginx` | `nginx:1.27-alpine` | `always` | 64 MB |

**Network**: `fe-el-seka-prod` (bridge)

**Ports**: nginx exposes `80:80` and `443:443`.

**No source mounts** — production containers are fully self-contained.

---

## 3. nginx Routing Contract

| Path prefix | Upstream service | Upstream port | Notes |
|---|---|---|---|
| `/api/` | `api` | `8000` | FastAPI — strips no prefix; `api` sees full `/api/` path |
| `/ai/` | `ai` | `8000` | AI service — strips no prefix |
| `/` (catch-all) | `main` | `3000` | Next.js — handles all other paths |

**Additional nginx config**:
- `gzip on` for `text/html`, `text/css`, `application/json`, `application/javascript`
- `proxy_set_header Host $host`
- `proxy_set_header X-Real-IP $remote_addr`
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`
- `proxy_set_header X-Forwarded-Proto $scheme`
- `client_max_body_size 10m` (National ID image uploads go through the API)

---

## 4. Environment Variable Interface

Each service declares its required environment variables. All are injected via `env_file` in compose — never hardcoded.

### 4.1 API Service (`services/api/.env.example`)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ | Supabase project URL (local: `http://host.docker.internal:54321`) |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key (bypasses RLS) |
| `SUPABASE_JWT_SECRET` | ✅ | JWT secret for verifying Supabase Auth tokens |
| `RESEND_API_KEY` | ✅ | Resend transactional email API key |
| `WEBHOOK_SECRET` | ✅ | Secret for validating Supabase Database Webhook calls |
| `NEXT_PUBLIC_API_URL` | ❌ | Not used server-side; documented for reference |
| `LOG_LEVEL` | ❌ | Default: `info` |

### 4.2 AI Service (`services/ai/.env.example`)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | For fetching model artefacts from Supabase Storage |
| `MODEL_STORAGE_BUCKET` | ✅ | Supabase Storage bucket name for model files |
| `LOG_LEVEL` | ❌ | Default: `info` |

### 4.3 Frontend (`apps/main/.env.example`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL (public — exposed to browser) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Supabase anonymous key (public) |
| `NEXT_PUBLIC_API_URL` | ✅ | Base URL for API calls (e.g., `http://localhost` in dev, `https://domain.com` in prod) |
| `NEXT_PUBLIC_NOMINATIM_URL` | ✅ | Nominatim reverse geocoding URL |

### 4.4 Docker-Specific Variables (dev only)

| Variable | Used by | Description |
|---|---|---|
| `SUPABASE_LOCAL_URL` | api, ai | `http://host.docker.internal:54321` — Supabase CLI local endpoint |
| `BACKEND_INTERNAL_URL` | (internal) | `http://api:8000` — for service-to-service calls within the compose network |

---

## 5. GitHub Actions Workflow Structure

### `.github/workflows/docker.yml`

```
Trigger: push to main / PR targeting main

Jobs:
  build-api    → Build services/api image (GHA cache)
  build-ai     → Build services/ai image (GHA cache)  [parallel with build-api]
  build-main   → Build apps/main image (GHA cache)    [parallel with build-api]

  scan-api     → Trivy scan api image (needs: build-api)
  scan-ai      → Trivy scan ai image  (needs: build-ai)   [parallel with scan-api]
  scan-main    → Trivy scan main image (needs: build-main) [parallel with scan-api]

  push         → GHCR push all 3 images (needs: scan-api, scan-ai, scan-main)
               → Runs ONLY if: github.ref == 'refs/heads/main'
               → Tags: latest + github.sha
```

**GHCR authentication**: `docker/login-action@v3` with `registry: ghcr.io`, `username: ${{ github.actor }}`, `password: ${{ secrets.GITHUB_TOKEN }}`. The automatic `GITHUB_TOKEN` has `packages: write` permission; no PAT needed for a public repo.

**Image visibility**: GHCR packages default to private on first push. After the first push, each package must be manually set to Public in the GitHub repository's Packages settings (one-time operation).
