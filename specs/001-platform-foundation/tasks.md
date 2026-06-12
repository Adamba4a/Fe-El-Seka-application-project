# Tasks: Platform Foundation

**Input**: Design documents from `specs/001-platform-foundation/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/health-check.md ✅ | quickstart.md ✅

**Tests**: Not included — no test tasks requested in spec. Pytest and Vitest are configured in Phase 2 (framework only; no test files written in Phase 1).

**Organization**: Tasks grouped by user story (US1 → US4 in priority order) after shared setup and foundational phases.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no blocking dependencies)
- **[USX]**: Maps to user story from spec.md
- Exact file paths included in every task description

---

## Phase 1: Setup (Root Workspace)

**Purpose**: Create the root monorepo skeleton — workspace config, pipeline definition, shared ignore rules. No apps or services yet.

- [ ] T001 Create monorepo root directory skeleton: `apps/main/`, `apps/admin/`, `packages/ui/src/components/`, `packages/shared/src/types/`, `packages/shared/src/utils/`, `services/api/app/core/`, `services/api/app/api/`, `services/api/tests/`, `services/ai/app/core/`, `services/ai/app/api/`, `services/ai/tests/`, `.github/workflows/`
- [ ] T002 Create root `package.json` declaring `"private": true`, `"name": "fe-el-seka"`, and top-level scripts: `dev` (concurrently starts all 4 services), `build` (delegates to turbo), `lint` (delegates to turbo), `typecheck` (delegates to turbo)
- [ ] T003 Create `pnpm-workspace.yaml` declaring `packages: ["apps/*", "packages/*"]` — Python services are NOT in the pnpm workspace
- [ ] T004 Create `turbo.json` defining three pipeline tasks with dependency graph: `lint` (no deps, parallel), `typecheck` (depends on `^build` of workspace deps), `build` (depends on `^build`, outputs `.next/**` and `dist/**`)
- [ ] T005 Create root `.gitignore` covering: `node_modules/`, `.next/`, `.turbo/`, `dist/`, `.env`, `.env.local`, `.env.*.local`, `__pycache__/`, `*.pyc`, `.venv/`, `.mypy_cache/`, `*.egg-info/`
- [ ] T006 [P] Create root `.env.example` documenting all required variable names across all services: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`, `API_VERSION`, `AI_VERSION`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that MUST be complete before any user story can be implemented. Creates the Supabase project skeleton and shared TypeScript base config.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T007 Run `supabase init` from repo root to generate `supabase/config.toml` and the empty `supabase/migrations/` directory; commit the generated files
- [ ] T008 [P] Create root `tsconfig.base.json` with TypeScript strict mode settings (`"strict": true`, `"target": "ES2022"`, `"moduleResolution": "bundler"`) and path aliases for `@fe-el-seka/ui` and `@fe-el-seka/shared` workspace packages
- [ ] T009 [P] Create `services/api/pyproject.toml` declaring uv as package manager and listing runtime deps: `fastapi>=0.111`, `uvicorn[standard]`, `asyncpg`, `pydantic-settings`, and dev deps: `ruff`, `mypy`, `pytest`, `pytest-asyncio`
- [ ] T010 [P] Create `services/ai/pyproject.toml` declaring uv as package manager and listing runtime deps: `fastapi>=0.111`, `uvicorn[standard]`, `pydantic-settings`, and dev deps: `ruff`, `mypy`, `pytest`, `pytest-asyncio`

**Checkpoint**: `supabase/config.toml` exists; `tsconfig.base.json` exists; both Python `pyproject.toml` files exist and `uv sync` runs without errors in each service directory.

---

## Phase 3: User Story 1 — Developer Onboarding (Priority: P1) 🎯 MVP

**Goal**: A developer can clone the repo, copy `.env.example` files, run `pnpm install && pnpm dev`, and reach all four services in a browser within 15 minutes. Missing env vars produce a named error, not a silent failure.

**Independent Test**: Fresh clone → `pnpm install` → `pnpm dev` → `localhost:3000` loads, `localhost:3001` loads, `localhost:8000` responds, `localhost:8001` responds. Remove one env var → service exits with `"Missing required environment variable: <NAME>"`.

### Implementation for User Story 1

- [ ] T011 [US1] Initialize `apps/main` as a Next.js 14 App Router project: create `apps/main/package.json` (`name: "@fe-el-seka/main"`, `scripts: {dev, build, lint, typecheck}`), `apps/main/next.config.ts` (TypeScript config, no experimental flags), `apps/main/tailwind.config.ts` (content paths covering `src/**/*.{ts,tsx}` and `packages/ui/src/**/*.tsx`)
- [ ] T012 [P] [US1] Create `apps/main/tsconfig.json` extending `../../tsconfig.base.json`, adding Next.js plugin and path alias `@/*` → `./src/*`
- [ ] T013 [P] [US1] Create `apps/main/src/app/layout.tsx` — root layout with `<html lang="en">` and `<body>` importing global Tailwind CSS; create `apps/main/src/app/globals.css` with Tailwind directives
- [ ] T014 [P] [US1] Create `apps/main/src/app/page.tsx` — minimal default landing page returning an `<h1>Fe El Seka</h1>` (no content, just structural correctness to prove app loads)
- [ ] T015 [US1] Create `apps/main/src/lib/env.ts` — validate all required environment variables at module load time using `pydantic`-style validation (check each `process.env.NEXT_PUBLIC_*` is defined; throw `Error("Missing required environment variable: <NAME>")` listing the first missing variable by exact name)
- [ ] T016 [P] [US1] Create `apps/main/.env.example` listing: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`
- [ ] T017 [US1] Initialize `apps/admin` as a Next.js 14 App Router project: create `apps/admin/package.json` (`name: "@fe-el-seka/admin"`, same scripts), `apps/admin/next.config.ts`, `apps/admin/tailwind.config.ts` (same Tailwind content paths as main but for admin `src/`)
- [ ] T018 [P] [US1] Create `apps/admin/tsconfig.json` extending `../../tsconfig.base.json` with Next.js plugin and `@/*` → `./src/*`
- [ ] T019 [P] [US1] Create `apps/admin/src/app/layout.tsx`, `apps/admin/src/app/globals.css`, and `apps/admin/src/app/page.tsx` (minimal admin landing page: `<h1>Fe El Seka Admin</h1>`)
- [ ] T020 [P] [US1] Create `apps/admin/src/lib/env.ts` — same env validation pattern as apps/main; validate `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_API_URL`
- [ ] T021 [P] [US1] Create `apps/admin/.env.example`
- [ ] T022 [US1] Create `services/api/app/core/config.py` — Pydantic `BaseSettings` class loading `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `API_VERSION` from environment; set `model_config = SettingsConfigDict(env_file=".env")` so missing vars raise `ValidationError` at startup with the variable name
- [ ] T023 [P] [US1] Create `services/api/app/core/database.py` — asyncpg connection pool; `create_pool()` called during FastAPI lifespan startup; pool stored in app state; `ping()` helper used by health check
- [ ] T024 [US1] Create `services/api/app/main.py` — FastAPI app with `lifespan` context manager: instantiate `Settings()` (validates env on startup, raises `ValidationError` with variable name on missing var), call `create_pool()`, register routers; set `title="Fe El Seka API"`, `version=settings.API_VERSION`
- [ ] T025 [P] [US1] Create `services/api/.env.example`
- [ ] T026 [US1] Create `services/ai/app/core/config.py` — Pydantic `BaseSettings` loading `AI_VERSION`; missing var raises `ValidationError` at startup
- [ ] T027 [P] [US1] Create `services/ai/app/main.py` — FastAPI app with lifespan; instantiate `Settings()` on startup; set `title="Fe El Seka AI Service"`, `version=settings.AI_VERSION`
- [ ] T028 [P] [US1] Create `services/ai/.env.example`
- [ ] T029 [US1] Add `concurrently` as a root dev dependency; update root `package.json` `dev` script to start all four services in parallel: `next dev --port 3000` (apps/main), `next dev --port 3001` (apps/admin), `uvicorn app.main:app --port 8000 --reload` (services/api), `uvicorn app.main:app --port 8001 --reload` (services/ai), with labelled prefixes for readable output

**Checkpoint**: `pnpm install && pnpm dev` starts all four services. `localhost:3000` and `localhost:3001` load in browser. Unsetting any required env var causes that service to exit with the variable name in the error message.

---

## Phase 4: User Story 2 — Database & Geospatial Readiness (Priority: P2)

**Goal**: PostGIS extension active, base schema (`users`, `rides`, `bookings`) deployed via Supabase migrations, and both services expose a working health check endpoint returning `{status, database, version}`.

**Independent Test**: `supabase db reset` applies all migrations without errors. Spatial SQL query returns a numeric distance. `curl localhost:8000/health` returns `{"status":"ok","database":"connected","version":"0.1.0"}` within 1 second.

### Implementation for User Story 2

- [ ] T030 [US2] Create `supabase/migrations/20260612000000_enable_extensions.sql`: `CREATE EXTENSION IF NOT EXISTS postgis;` and `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";` — enables spatial and UUID support before any table creation
- [ ] T031 [US2] Create `supabase/migrations/20260612000001_foundation_schema.sql` with the full base schema per data-model.md:
  - `users` table: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `phone VARCHAR(20) UNIQUE NOT NULL`, `role VARCHAR(20) NOT NULL CHECK (role IN ('passenger','driver','both'))`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `rides` table: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `driver_id UUID NOT NULL REFERENCES users(id)`, `origin GEOMETRY(POINT,4326) NOT NULL`, `destination GEOMETRY(POINT,4326) NOT NULL`, `departure_at TIMESTAMPTZ NOT NULL`, `status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','cancelled','completed'))`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `bookings` table: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `ride_id UUID NOT NULL REFERENCES rides(id)`, `passenger_id UUID NOT NULL REFERENCES users(id)`, `status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','cancelled','completed'))`, `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - GIST indices: `rides_origin_gist_idx` on `rides(origin)`, `rides_destination_gist_idx` on `rides(destination)`
  - BTREE indices: `rides_driver_id_idx`, `rides_departure_at_idx`, `bookings_ride_id_idx`, `bookings_passenger_id_idx`
  - Enable RLS: `ALTER TABLE users ENABLE ROW LEVEL SECURITY; ALTER TABLE rides ENABLE ROW LEVEL SECURITY; ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;`
  - Stub permissive policies: `CREATE POLICY "allow_all_phase1" ON users FOR ALL USING (true); CREATE POLICY "allow_all_phase1" ON rides FOR ALL USING (true); CREATE POLICY "allow_all_phase1" ON bookings FOR ALL USING (true);`
- [ ] T032 [US2] Create `services/api/app/api/health.py` — `GET /health` endpoint per contracts/health-check.md: probe database with `await pool.execute("SELECT 1")` with 500 ms timeout; return `{"status": "ok"|"degraded", "database": "connected"|"disconnected", "version": settings.API_VERSION}`; catches `asyncpg.PostgresConnectionError` and sets status to degraded without raising
- [ ] T033 [US2] Register health router in `services/api/app/main.py`: `app.include_router(health_router)` — no prefix, health endpoint available at `GET /health`
- [ ] T034 [P] [US2] Create `services/ai/app/api/health.py` — `GET /health` endpoint returning same contract shape: `{"status": "ok", "database": "connected", "version": settings.AI_VERSION}` (AI service has no DB in Phase 1; database field always "connected")
- [ ] T035 [P] [US2] Register health router in `services/ai/app/main.py`: `app.include_router(health_router)`

**Checkpoint**: `supabase db reset` → zero errors. `SELECT ST_Distance(ST_SetSRID(ST_MakePoint(31.2357,30.0444),4326)::geography, ST_SetSRID(ST_MakePoint(31.2197,30.0561),4326)::geography)` returns ~2200 m. `curl localhost:8000/health` → `{"status":"ok","database":"connected","version":"0.1.0"}` in under 1 second.

---

## Phase 5: User Story 3 — Shared Package Reuse (Priority: P3)

**Goal**: `packages/ui` exports `Button` and `Input` components; `packages/shared` exports `User`, `Ride`, `Booking` TypeScript types. Both apps import from shared packages and compile without errors.

**Independent Test**: `pnpm turbo typecheck` exits with code 0 across all workspace packages. A type error introduced in `packages/shared` surfaces in both `apps/main` and `apps/admin` on the next typecheck run.

### Implementation for User Story 3

- [ ] T036 [US3] Create `packages/ui/package.json`: `name: "@fe-el-seka/ui"`, `exports: {"./button": "./src/components/button.tsx", "./input": "./src/components/input.tsx", ".": "./src/index.ts"}`, `peerDependencies: {"react": "^18", "react-dom": "^18"}`
- [ ] T037 [P] [US3] Create `packages/ui/tsconfig.json` extending `../../tsconfig.base.json` with `"jsx": "react-jsx"` and `"include": ["src"]`
- [ ] T038 [P] [US3] Create `packages/ui/src/components/button.tsx` — typed Button component: `interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: "default" | "outline" | "ghost"; size?: "sm" | "md" | "lg"; }` with Tailwind class variants applied via `cn()` helper; export named `Button`
- [ ] T039 [P] [US3] Create `packages/ui/src/components/input.tsx` — typed Input component: `interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}` with Tailwind styling; export named `Input`
- [ ] T040 [P] [US3] Create `packages/ui/src/lib/utils.ts` — `cn()` helper using `clsx` and `tailwind-merge` for conditional class merging; used by Button and Input components
- [ ] T041 [P] [US3] Create `packages/ui/src/index.ts` — barrel re-export: `export { Button } from "./components/button"; export { Input } from "./components/input";`
- [ ] T042 [P] [US3] Add `clsx` and `tailwind-merge` as dependencies in `packages/ui/package.json`; run `pnpm install` from root to link workspace
- [ ] T043 [US3] Create `packages/shared/package.json`: `name: "@fe-el-seka/shared"`, `exports: {"./types": "./src/types/index.ts", "./utils": "./src/utils/index.ts", ".": "./src/index.ts"}`
- [ ] T044 [P] [US3] Create `packages/shared/tsconfig.json` extending `../../tsconfig.base.json`
- [ ] T045 [P] [US3] Create `packages/shared/src/types/index.ts` — TypeScript interfaces matching data-model.md: `UserRole` (`"passenger" | "driver" | "both"`), `RideStatus` (`"active" | "paused" | "cancelled" | "completed"`), `BookingStatus` (`"pending" | "confirmed" | "cancelled" | "completed"`), `User` (id, phone, role, created_at), `Ride` (id, driver_id, departure_at, status, created_at — geometry fields typed as `{ type: "Point"; coordinates: [number, number] }`), `Booking` (id, ride_id, passenger_id, status, created_at)
- [ ] T046 [P] [US3] Create `packages/shared/src/utils/index.ts` — placeholder utility exports: `formatPhone(phone: string): string` (returns phone as-is for now), `formatDate(date: string): string` (returns ISO string)
- [ ] T047 [P] [US3] Create `packages/shared/src/index.ts` — barrel export: `export * from "./types"; export * from "./utils";`
- [ ] T048 [US3] Add `"@fe-el-seka/ui": "workspace:*"` and `"@fe-el-seka/shared": "workspace:*"` as dependencies in both `apps/main/package.json` and `apps/admin/package.json`; run `pnpm install` from root
- [ ] T049 [US3] Import and render `Button` from `@fe-el-seka/ui` in `apps/main/src/app/page.tsx`; import `User` type from `@fe-el-seka/shared` and declare a typed constant — confirms cross-package imports compile
- [ ] T050 [P] [US3] Import and render `Input` from `@fe-el-seka/ui` in `apps/admin/src/app/page.tsx`; import `Ride` type from `@fe-el-seka/shared` — confirms both apps resolve shared packages

**Checkpoint**: `pnpm turbo typecheck` → exit code 0, zero errors across all 4 workspace packages. Introducing a deliberate type error in `packages/shared/src/types/index.ts` causes typecheck to fail in both `apps/main` and `apps/admin`.

---

## Phase 6: User Story 4 — CI/CD Pipeline Validation (Priority: P4)

**Goal**: GitHub Actions CI runs on every PR targeting `main`. Secret detection (Gitleaks) blocks all other jobs if triggered. Lint, type-check, and build for TypeScript workspace and Python services all complete within 10 minutes total.

**Independent Test**: Open a PR with a deliberate lint error → CI fails on the lint job, PR merge is blocked. Open a PR with a valid change → all 4 CI jobs pass in under 10 minutes.

### Implementation for User Story 4

- [ ] T051 [US4] Create `eslint.config.mjs` at repo root — flat config extending `@eslint/js` recommended and `typescript-eslint` strict preset; configure `files: ["apps/**/*.{ts,tsx}", "packages/**/*.{ts,tsx}"]`; add Next.js core-web-vitals rules for apps
- [ ] T052 [P] [US4] Add `lint` script to all TypeScript `package.json` files: `apps/main` (`next lint`), `apps/admin` (`next lint`), `packages/ui` (`eslint src`), `packages/shared` (`eslint src`)
- [ ] T053 [P] [US4] Create `services/api/ruff.toml` — select rules `["E", "W", "F", "I"]` (pyflakes, pycodestyle, isort); `target-version = "py311"`; `line-length = 88`
- [ ] T054 [P] [US4] Create `services/ai/ruff.toml` — identical ruff configuration as services/api
- [ ] T055 [P] [US4] Create `services/api/mypy.ini` — `[mypy]` section: `strict = True`, `python_version = 3.11`, `ignore_missing_imports = True`; `[[mypy.overrides]]` for `asyncpg.*` with `ignore_missing_imports = True`
- [ ] T056 [P] [US4] Create `services/ai/mypy.ini` — same mypy configuration as services/api
- [ ] T057 [P] [US4] Create `.gitleaks.toml` at repo root — configure `[[allowlists]]` to exclude `.env.example` files from secret detection (they contain placeholder strings, not real secrets) and suppress any false positives from test fixture data
- [ ] T058 [US4] Create `.github/workflows/ci.yml` with:
  - `on: pull_request: branches: [main]`
  - `job: secret-scan` — uses `gitleaks/gitleaks-action@v2` with `GITHUB_TOKEN` secret; blocks all downstream jobs on failure
  - `job: ci-typescript` — `needs: secret-scan`; steps: checkout, setup pnpm, cache pnpm store, `pnpm install --frozen-lockfile`, `pnpm turbo lint typecheck build`; `timeout-minutes: 10`
  - `job: ci-api` — `needs: secret-scan`; steps: checkout, setup Python 3.11, install uv, `uv sync` in `services/api/`, `ruff check .`, `mypy app/`; `timeout-minutes: 5`
  - `job: ci-ai` — `needs: secret-scan`; steps: checkout, setup Python 3.11, install uv, `uv sync` in `services/ai/`, `ruff check .`, `mypy app/`; `timeout-minutes: 5`
- [ ] T059 [US4] Add `typecheck` script to each TypeScript `package.json`: `apps/main` (`tsc --noEmit`), `apps/admin` (`tsc --noEmit`), `packages/ui` (`tsc --noEmit`), `packages/shared` (`tsc --noEmit`)
- [ ] T060 [P] [US4] Create `CONTRIBUTING.md` at repo root documenting: branch naming convention, required PR status checks (`secret-scan`, `ci-typescript`, `ci-api`, `ci-ai`), and instructions for configuring GitHub branch protection rules on `main`

**Checkpoint**: Push to a test branch → CI starts in GitHub Actions → all 4 jobs complete → total runtime under 10 minutes. Introduce a deliberate lint error in `apps/main/src/app/page.tsx` → `ci-typescript` job fails → PR merge blocked.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation sweep confirming all success criteria pass end-to-end.

- [ ] T061 Run the complete `quickstart.md` validation sequence: confirm all 8 items in the validation checklist pass (`pnpm install && pnpm dev`, health checks, `supabase db reset` + spatial query, `pnpm turbo typecheck`, `pnpm turbo build`, `pnpm turbo lint`, env var enforcement, `gitleaks detect`)
- [ ] T062 [P] Create `README.md` at repo root: project overview, monorepo structure diagram (apps/, packages/, services/, supabase/), prerequisites list, 5-step quickstart (clone → copy env → `pnpm install` → `supabase db reset` → `pnpm dev`), links to `specs/001-platform-foundation/plan.md` and `quickstart.md`
- [ ] T063 [P] Verify SC-007 locally: run `gitleaks detect --source . --verbose` from repo root; confirm zero secrets detected in any committed file
- [ ] T064 Final build and type sweep: run `pnpm turbo lint typecheck build` from repo root; confirm exit code 0, zero errors, SC-002 and SC-004 pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — blocks all user story phases
- **Phase 3 (US1)**: Depends on Phase 2 — can start as soon as foundational phase is complete
- **Phase 4 (US2)**: Depends on Phase 2; also depends on `services/api` app entry point from Phase 3 (T024) for health check wiring
- **Phase 5 (US3)**: Depends on Phase 2; can run fully in parallel with Phase 4
- **Phase 6 (US4)**: Depends on Phase 3 (apps must exist to lint them); can start after Phase 3 checkpoint
- **Phase 7 (Polish)**: Depends on all prior phases complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — no dependency on other user stories
- **US2 (P2)**: Starts after Phase 2; requires `services/api/app/main.py` (T024) and `services/api/app/core/database.py` (T023) from US1 to exist before wiring health check — coordinate T030–T035 after T024
- **US3 (P3)**: Starts after Phase 2 — fully independent of US1 and US2
- **US4 (P4)**: Starts after US1 checkpoint — apps must exist for lint configuration to reference

### Within Each Phase

- All [P] tasks within a phase can run in parallel (different files, no blocking dependency)
- Non-[P] tasks within a phase must run after the tasks they depend on

### Parallel Opportunities

- T008, T009, T010 in Phase 2 can all run simultaneously
- T012–T016 for apps/main and T018–T021 for apps/admin in Phase 3 can run simultaneously as separate streams
- T034–T035 (AI health check) in Phase 4 can run in parallel with T030–T033 (API health check)
- T037–T042 (packages/ui) and T044–T047 (packages/shared) in Phase 5 can run simultaneously
- US3 (Phase 5) and US2 (Phase 4) can be worked in parallel by different developers after Phase 2 completes

---

## Parallel Example: User Story 1 (Two Developer Streams)

```
Stream A (apps/main):                    Stream B (apps/admin):
T011 Initialize apps/main               T017 Initialize apps/admin
T012 [P] tsconfig                       T018 [P] tsconfig
T013 [P] layout.tsx                     T019 [P] layout + page
T014 [P] page.tsx                       T020 [P] env.ts
T015 env.ts (after T013, T014)          T021 [P] .env.example
T016 [P] .env.example

Stream C (services/api):                Stream D (services/ai):
T022 config.py                          T026 config.py
T023 [P] database.py                    T027 [P] main.py
T024 main.py (after T022, T023)         T028 [P] .env.example
T025 [P] .env.example

All streams → T029 Root dev script (after all services exist)
```

## Parallel Example: User Story 3 (Phase 5)

```
Stream A (packages/ui):                 Stream B (packages/shared):
T036 package.json                       T043 package.json
T037 [P] tsconfig                       T044 [P] tsconfig
T038 [P] button.tsx                     T045 [P] types/index.ts
T039 [P] input.tsx                      T046 [P] utils/index.ts
T040 [P] utils.ts (cn helper)           T047 [P] index.ts barrel
T041 [P] index.ts barrel
T042 [P] add clsx + tw-merge

Merge → T048 Add workspace deps to both apps
      → T049 Import in apps/main (after T048)
      → T050 [P] Import in apps/admin (after T048)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) — ~1 hour
2. Complete Phase 2 (Foundational) — ~30 minutes
3. Complete Phase 3 (US1 — Developer Onboarding) — ~3–4 hours
4. **STOP and VALIDATE**: Run `pnpm dev`, confirm all 4 services start, confirm env var enforcement works
5. Foundation is ready for Phase 2 (AI Foundation) work to begin in parallel

### Incremental Delivery

1. Phase 1 + 2 → Root workspace ready
2. Phase 3 (US1) → All services start locally — **first milestone**
3. Phase 4 (US2) → Database schema deployed, health checks live — **second milestone**
4. Phase 5 (US3) → Shared packages working — **third milestone**
5. Phase 6 (US4) → CI pipeline active — **fourth milestone**
6. Phase 7 (Polish) → All success criteria verified — **Phase 1 complete**

### Parallel Team Strategy

With two developers:

1. Both complete Phase 1 + 2 together (~1.5 hours)
2. Developer A: Phase 3 (US1) — app initialization
3. Developer B: Phase 5 (US3) — shared packages (can start after Phase 2)
4. After Phase 3 checkpoint: Developer B adds Phase 4 (US2) database + health check
5. After Phase 5 checkpoint: Developer A adds Phase 6 (US4) CI/CD
6. Both run Phase 7 validation together

---

## Notes

- All [P] tasks involve different files with no blocking inter-dependencies within the same phase
- Each user story phase has an explicit checkpoint — stop and validate before proceeding
- Supabase migration filenames use timestamp prefix `YYYYMMDDHHMMSS` — do not rename after creation
- Python services are managed with uv, not pnpm — run `uv sync` and `uvicorn` from within each service directory
- The `concurrently` root dev script (T029) requires all service `package.json` files to exist (from US1) before it can reference app-level commands
- `.gitleaks.toml` allowlists (T057) must be committed before the CI workflow (T058) is pushed, or the first CI run may flag `.env.example` files
