# Tasks: Dockerization

**Input**: Design documents from `specs/005-dockerization/`

**Prerequisites**: plan.md ✅ · spec.md ✅ · research.md ✅ · data-model.md ✅ · contracts/docker-setup.md ✅ · quickstart.md ✅

**Tests**: Not included — not requested in the specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete peer task)
- **[Story]**: Which user story this task belongs to (US1–US3)

---

## Phase 1: Setup

**Purpose**: Apply the one prerequisite code change and create the health check endpoint that Dockerfiles depend on. Must complete before any Dockerfile is written.

- [x] T001 Add `output: 'standalone'` to `apps/main/next.config.mjs` (add after existing `transpilePackages` line); verify with `pnpm --filter main build` — confirm `.next/standalone/server.js` exists before proceeding
- [x] T002 [P] Create Next.js health check route handler `apps/main/src/app/api/health/route.ts`: export `GET` returning `Response.json({ status: "ok", service: "main" })` — required by `HEALTHCHECK` in the frontend Dockerfile
- [x] T003 [P] Verify Python health endpoints are reachable: confirm `services/api/app/api/health.py` exports a router mounted at `/health` returning `{"status":"ok"}` and `services/ai/app/api/` has an equivalent; if missing in either service, create the missing `health.py` file and register its router in the respective `app/main.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create all Dockerfiles and `.dockerignore` files. These are shared dependencies for all three user stories — no compose or CI work can be validated without them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Create `services/api/Dockerfile`: `python:3.11-slim` base; `builder` stage copies uv binary (`COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv`), copies `pyproject.toml` and `uv.lock`, runs `uv sync --frozen --no-dev --no-editable`; `runner` stage copies `.venv` from builder and `app/` source, creates `appuser` (UID 1001), sets `ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1`, switches to `USER appuser`, adds `HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 CMD curl -f http://localhost:8000/health || exit 1`, exposes port 8000, sets `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]`
- [x] T005 [P] Create `services/ai/Dockerfile`: identical multi-stage pattern to T004 (`builder` via uv + `runner` with non-root `appuser`); same `HEALTHCHECK` pointing to `/health`; same `CMD` pattern — AI service uses the same FastAPI/uvicorn stack
- [x] T006 [P] Create `apps/main/Dockerfile` with monorepo-root build context: `node:20-alpine` base; `deps` stage enables pnpm (`corepack enable pnpm`) and runs `pnpm install --frozen-lockfile` from root `pnpm-lock.yaml`; `builder` stage copies `packages/`, `apps/main/`, and `node_modules` from deps stage, runs `pnpm --filter main build`; `runner` stage creates `nextjs` group and user (UID/GID 1001), copies `.next/standalone/`, `.next/static/` → `.next/static/`, and `public/` (if exists), sets `ENV NODE_ENV=production`, switches to `USER nextjs`, adds `HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD wget -qO- http://localhost:3000/api/health || exit 1`, exposes port 3000, sets `CMD ["node", "server.js"]`
- [x] T007 [P] Create `services/api/.dockerignore`: exclude `tests/`, `*.pyc`, `__pycache__/`, `.env*`, `.venv/`, `data/`, `*.ipynb`, `.mypy_cache/`, `.ruff_cache/`, `.git/`, `*.md`, `uv.lock` is intentionally NOT excluded (required by `uv sync --frozen`)
- [x] T008 [P] Create `services/ai/.dockerignore`: same rules as T007 plus `models/`, `notebooks/`, `pipelines/`, `*.pkl`, `*.joblib`, `scripts/` (model artifacts loaded at runtime from Supabase Storage — not baked in)
- [x] T009 [P] Create `.dockerignore` at repo root (scopes the monorepo-root build context for `apps/main`): exclude `node_modules/`, `**/.env*`, `.next/`, `specs/`, `docs/`, `**/*.test.*`, `**/*.spec.*`, `.git/`, `services/`, `supabase/`, `*.md` — keep `apps/`, `packages/`, `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `turbo.json`

**Checkpoint**: All three service images can be built locally with `docker build` and start without errors. Python services pass `docker inspect --format '{{.State.Health.Status}}'` returning `healthy`.

---

## Phase 3: User Story 1 — Developer Onboarding (Priority: P1) 🎯 MVP

**Goal**: Any developer with Docker + Supabase CLI can run `supabase start && docker compose up` to get the full platform running locally with hot-reload within 60 seconds.

**Independent Test**: Quickstart scenario 1 (full stack starts + all three health checks return 200), scenario 2 (nginx routes correctly), scenario 3 (hot-reload works in <5s).

- [ ] T010 Create `nginx/nginx.dev.conf`: define `upstream api_upstream { server api:8000; }`, `upstream ai_upstream { server ai:8000; }`, `upstream main_upstream { server main:3000; }`; single `server` block on port 80 with `location /api/ { proxy_pass http://api_upstream; }`, `location /ai/ { proxy_pass http://ai_upstream; }`, `location / { proxy_pass http://main_upstream; }`; add `gzip on`, `gzip_types text/html text/css application/json application/javascript`, `client_max_body_size 10m`, and proxy headers (`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`) in each location block
- [ ] T011 Create `docker-compose.yml` (development): define four services on network `fe-el-seka-dev`; `api` service builds `services/api/` via `build: { context: services/api }`, mounts `./services/api/app:/app/app` for hot-reload, sets `env_file: services/api/.env`; `ai` service mirrors `api` using `services/ai/` context and `./services/ai/app:/app/app` mount; `main` service builds with `build: { context: ., dockerfile: apps/main/Dockerfile }`, mounts `./apps/main/src:/app/src` and `./apps/main/public:/app/public`, sets `env_file: apps/main/.env`; `nginx` service uses `nginx:1.27-alpine`, mounts `./nginx/nginx.dev.conf:/etc/nginx/conf.d/default.conf:ro`, exposes `80:80`, depends_on all three app services; add header comment: `# Prerequisites: supabase start (runs Supabase CLI local DB before docker compose up)`
- [ ] T012 [P] [US1] Update `services/api/.env.example`: add `SUPABASE_LOCAL_URL=http://host.docker.internal:54321` (dev Docker override for Supabase CLI), `BACKEND_INTERNAL_URL=http://api:8000` (for service-to-service calls within compose network), `LOG_LEVEL=info`
- [ ] T013 [P] [US1] Update `services/ai/.env.example`: add `SUPABASE_LOCAL_URL=http://host.docker.internal:54321`, `MODEL_STORAGE_BUCKET=ai-models` (Supabase Storage bucket for model files), `LOG_LEVEL=info`
- [ ] T014 [P] [US1] Update `apps/main/.env.example`: add `NEXT_PUBLIC_API_URL=http://localhost` (base URL; empty path for local dev through nginx), `BACKEND_INTERNAL_URL=http://api:8000`

**Checkpoint**: `docker compose up --build` starts all 4 containers; `curl http://localhost/api/health`, `curl http://localhost/ai/health`, and `curl http://localhost/` all return 200. Editing a file in `services/api/app/` is reflected without `docker compose restart`.

---

## Phase 4: User Story 2 — Production Deployment (Priority: P2)

**Goal**: DevOps can pull pre-built images from GHCR, set production `.env` values, and run `docker compose -f docker-compose.prod.yml up -d` to deploy the platform to a Linux server.

**Independent Test**: Quickstart scenario 7 (production compose starts from pulled images, all health checks pass, non-root users confirmed per scenario 6).

- [ ] T015 Create `nginx/nginx.prod.conf`: identical routing rules to `nginx.dev.conf`; add a commented-out HTTPS server block skeleton (port 443, `ssl_certificate`, `ssl_certificate_key` placeholders) for future TLS termination — active config is HTTP only (port 80) for MVP
- [ ] T016 Create `docker-compose.prod.yml` (production): four services on network `fe-el-seka-prod`; all three app services use pre-built GHCR images (`image: ghcr.io/adamba4a777/fe-el-seka-api:latest` etc.) instead of `build:` blocks; no source volume mounts; each service has `restart: always` and `env_file: .env.prod`; add `deploy.resources.reservations.memory` for each service (api: 256M, ai: 512M, main: 128M, nginx: 64M); `nginx` service uses `nginx:1.27-alpine`, mounts `./nginx/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro`, exposes `80:80` and `443:443`

**Checkpoint**: `docker compose -f docker-compose.prod.yml up -d` starts cleanly using pulled images. `docker compose -f docker-compose.prod.yml ps` shows all services as `running` or `healthy`. No source code directories exist inside any running container (`docker compose exec api ls /app` shows only `app/` and `.venv/`).

---

## Phase 5: User Story 3 — CI/CD Pipeline (Priority: P3)

**Goal**: Every push to main and every pull request triggers a GitHub Actions workflow that builds all three Docker images with layer caching, runs Trivy vulnerability scans, and publishes images to GHCR only on merge to main.

**Independent Test**: Quickstart scenario 8 (open a PR, observe build + scan jobs; merge to main, confirm images appear in GHCR tagged with `latest` and `<sha>`).

- [ ] T017 Create `.github/workflows/docker.yml`: set triggers `on: { push: { branches: [main] }, pull_request: { branches: [main] } }`; add `permissions: { contents: read, packages: write }`; define three parallel build jobs (`build-api`, `build-ai`, `build-main`) each using `docker/setup-buildx-action@v3`, `docker/login-action@v3` (registry: ghcr.io, username: `${{ github.actor }}`, password: `${{ secrets.GITHUB_TOKEN }}`), and `docker/build-push-action@v5` with `cache-from: type=gha`, `cache-to: type=gha,mode=max`, `push: false` (builds but doesn't push — scan runs next), outputs image to local daemon; define three parallel scan jobs (`scan-api`, `scan-ai`, `scan-main`) each needing its build job, using `aquasecurity/trivy-action@0.24.0` with `exit-code: 1`, `severity: CRITICAL,HIGH`, `ignore-unfixed: false`; define one `push` job needing all three scan jobs with `if: github.ref == 'refs/heads/main'` that re-runs `docker/build-push-action@v5` with `push: true` and tags `ghcr.io/adamba4a777/fe-el-seka-<service>:latest` and `ghcr.io/adamba4a777/fe-el-seka-<service>:${{ github.sha }}`

**Checkpoint**: Open a pull request and confirm `Docker CI` workflow appears in GitHub Actions with all build + scan jobs running in parallel. Merge to main and confirm a `push` job runs and all three images appear in GHCR with both `latest` and `<sha>` tags.

---

## Phase 6: Polish & Validation

**Purpose**: Run all quickstart validation scenarios, confirm production image sizes, and document the one-time GHCR visibility setup.

- [ ] T018 Run quickstart scenario 1 (full stack cold start ≤ 60s) and scenario 2 (nginx routing) and scenario 3 (hot-reload ≤ 5s) against the development compose stack; record pass/fail
- [ ] T019 [P] Run quickstart scenario 4 (no secrets in image layers) and scenario 6 (non-root processes) against locally built production images; record pass/fail
- [ ] T020 [P] Run quickstart scenario 5 (production image sizes): confirm api < 300 MB, ai < 700 MB, main < 200 MB using `docker images`; if any exceed limit, add a comment to the respective Dockerfile identifying the largest layer with `docker history <image>`
- [ ] T021 Append "One-Time Setup: GHCR Package Visibility" note to `specs/005-dockerization/quickstart.md` confirming the manual step (already partially documented — verify the section is complete and accurate for the actual repo URL)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — T001 and T002/T003 run in parallel; T001 must complete before Phase 2
- **Phase 2 (Foundational)**: Depends on Phase 1 (T001 for standalone output, T002/T003 for health endpoints) — BLOCKS all user story phases
- **Phase 3 (US1)**: Depends on Phase 2; T010 (nginx.dev.conf) before T011 (compose references nginx config)
- **Phase 4 (US2)**: Depends on Phase 2; T015 (nginx.prod.conf) before T016 (compose references it); can start in parallel with Phase 3
- **Phase 5 (US3)**: Depends on Phase 2 only; fully independent of Phase 3 and Phase 4
- **Phase 6 (Polish)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only — deliver development compose stack
- **US2 (P2)**: Depends on Phase 2 only — production images are built from same Dockerfiles
- **US3 (P3)**: Depends on Phase 2 only — CI builds from same Dockerfiles; completely independent of US1/US2

### Within Each User Story

- Dockerfiles complete → health check reachable → compose/workflow references are valid

### Parallel Opportunities

- Phase 1: T002 and T003 parallel with each other; T001 sequential first
- Phase 2: T004 (api Dockerfile) → T005 (ai Dockerfile) + T006 (frontend Dockerfile) in parallel; T007/T008/T009 all parallel
- Phase 3: T012, T013, T014 (env example updates) all parallel after T011
- Phase 4: T015 then T016 (sequential)
- Phase 5: T017 (single task)
- Phase 6: T019 and T020 parallel; T018 sequential first; T021 sequential last

---

## Parallel Example: Phase 2 (Foundational)

```text
# All three Dockerfiles are independent — run in parallel:
T004  Create services/api/Dockerfile
T005  Create services/ai/Dockerfile
T006  Create apps/main/Dockerfile

# All three .dockerignore files are independent — run in parallel:
T007  Create services/api/.dockerignore
T008  Create services/ai/.dockerignore
T009  Create .dockerignore (repo root)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T009) — CRITICAL
3. Complete Phase 3: US1 — Developer Onboarding (T010–T014)
4. **STOP and VALIDATE**: Run quickstart scenarios 1, 2, 3
5. Demo: full local stack runs from `docker compose up`

### Incremental Delivery

1. Phase 1 + 2 → All Dockerfiles ready
2. Phase 3 (US1) → Developer onboarding works → **MVP Demo**
3. Phase 4 (US2) → Production deployment ready
4. Phase 5 (US3) → CI/CD pipeline live
5. Phase 6 → All scenarios validated

---

## Notes

- **No direct source code in production images** — the `.dockerignore` files (T007, T008, T009) and multi-stage builds enforce this
- **uv binary is copied, not installed** — `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` in each Python builder stage
- **Frontend build context is monorepo root** — `build: { context: ., dockerfile: apps/main/Dockerfile }` in compose; Dockerfile copies `packages/` for shared deps
- **Supabase CLI is outside compose** — no DB service in `docker-compose.yml`; `SUPABASE_LOCAL_URL` points to `http://host.docker.internal:54321`
- **nginx service names are DNS** — `api:8000`, `ai:8000`, `main:3000` in nginx config; never `localhost`
- **GHCR push only on main** — `if: github.ref == 'refs/heads/main'` on the push job in T017
- [P] tasks = different files, no dependency on incomplete peer tasks
- Each user story is independently completable and testable without requiring other stories to be built
