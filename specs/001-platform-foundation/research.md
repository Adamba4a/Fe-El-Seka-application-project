# Research: Platform Foundation

**Branch**: `001-platform-foundation` | **Date**: 2026-06-12

---

## Decision 1: Monorepo Workspace Manager

**Decision**: pnpm workspaces + Turborepo

**Rationale**: pnpm is the de-facto standard for Next.js monorepos as of 2024. It provides strict dependency isolation, the fastest install times of any Node.js package manager, and first-class workspace support. Turborepo sits on top to provide build caching, task pipelining, and affected-build detection — reducing CI times significantly as the monorepo grows. The combination is used in production by Vercel (Next.js authors) and is the recommended approach in the Next.js 14 documentation for monorepos.

**Alternatives considered**:
- npm workspaces: no build caching, slower installs, no pipeline definition
- Yarn Berry: comparable capabilities, but pnpm has surpassed it in ecosystem adoption
- Nx: more powerful but significantly heavier; overkill for 2-app monorepo at MVP stage

**Configuration files**: `pnpm-workspace.yaml` at root, `turbo.json` for pipeline definition, `package.json` at root for shared scripts.

---

## Decision 2: Python Dependency Management

**Decision**: uv (Astral)

**Rationale**: uv is the modern replacement for pip/virtualenv/pip-tools, written in Rust. It is 10–100× faster than pip for dependency resolution and installation. It produces a lockfile (`uv.lock`) for reproducible installs. It handles virtual environment creation automatically. As of 2025, uv has become the recommended tool for new Python projects and is used by the FastAPI project itself.

**Alternatives considered**:
- pip + requirements.txt: no lockfile, slow, no dependency isolation
- Poetry: mature, good DX, but slower than uv; migrating from Poetry to uv is common
- Conda: overkill, primarily for data science environments

**Configuration**: `pyproject.toml` per service (`services/api/`, `services/ai/`).

---

## Decision 3: Secret Detection Tool

**Decision**: Gitleaks (via `gitleaks/gitleaks-action@v2` GitHub Action)

**Rationale**: Gitleaks is the most widely adopted open-source secret scanner. It scans git history and staged content for over 150 secret patterns (API keys, tokens, connection strings). The GitHub Action integrates natively into PR workflows, fails the check on detection, and reports the file and line number — satisfying FR-011a and SC-007 exactly. Configuration via `.gitleaks.toml` allows false-positive suppression.

**Alternatives considered**:
- Trufflehog: broader detection (git history + regex + entropy), slower, more false positives
- detect-secrets: Python-based, requires pre-commit hook setup; less suited for CI-first approach
- GitHub Secret Scanning (built-in): only available on GitHub Advanced Security (paid for private repos)

---

## Decision 4: PostGIS Geometry Types for Route Points

**Decision**: `GEOMETRY(POINT, 4326)` for origin/destination fields; SRID 4326 (WGS84)

**Rationale**: WGS84 (SRID 4326) is the coordinate system used by GPS, OpenStreetMap, and OSRM — the exact tools this platform uses for routing. Using the correct SRID from the start ensures spatial queries (distance calculations, proximity checks) return correct results without coordinate system transformation overhead. `GEOMETRY` (not `GEOGRAPHY`) is preferred because OSRM outputs coordinates in WGS84 and PostGIS geometry operations are faster; geography type is reserved for long-distance great-circle calculations.

**Spatial indices**: `CREATE INDEX USING GIST` on all geometry columns is mandatory for performant spatial queries. Without GIST indices, proximity and overlap queries will perform full table scans.

**Alternatives considered**:
- `GEOGRAPHY(POINT, 4326)`: more accurate for large distances (accounts for Earth curvature), but slower for the urban/city-scale queries this platform performs
- Plain `FLOAT` lat/lng columns: violates constitution Data Standards; no spatial indexing
- `POINT` (no SRID): ambiguous coordinate system, causes bugs when mixing with OSRM output

---

## Decision 5: CI/CD Strategy for Monorepo

**Decision**: Run all jobs on every PR targeting main (no affected-detection for MVP)

**Rationale**: Affected-detection (running only changed packages) adds significant CI configuration complexity. For a small team at MVP stage with 2 frontend apps and 2 services, running all checks takes well under 10 minutes (NFR-003). Parallelization via GitHub Actions matrix covers the speed requirement. Turborepo's remote caching can be added post-competition for further speedup.

**CI job structure**:
1. `secret-scan` — Gitleaks scan (runs first, blocks everything else on failure)
2. `lint-typecheck` — pnpm turbo lint + type-check (matrix: main app, admin app)
3. `build` — pnpm turbo build (matrix: main app, admin app)
4. `api-checks` — Python lint (ruff) + type-check (mypy) for `services/api`
5. `ai-checks` — Python lint (ruff) + type-check (mypy) for `services/ai`

All jobs run in parallel after `secret-scan` passes. Branch protection requires all jobs to pass.

**Alternatives considered**:
- Turborepo affected-detection: correct long-term choice; deferred post-competition
- Single sequential job: simpler but significantly slower (violates NFR-003 risk)

---

## Decision 6: Next.js App Structure

**Decision**: App Router (`app/` directory), TypeScript strict mode, Tailwind CSS + shadcn/ui

**Rationale**: Next.js 14 defaults to App Router. It provides server components, streaming, and layout-level loading states — all beneficial for the ride-search and tracking flows coming in later phases. Strict TypeScript catches errors earlier. shadcn/ui provides accessible, Tailwind-native components that live in the codebase (not a dependency) — making them fully customizable for the platform's UI needs.

**Shared UI package**: shadcn/ui components are initialized once in `packages/ui` and re-exported. Both apps import from `@fe-el-seka/ui`. This prevents shadcn/ui from being installed twice and ensures consistent component versions.

---

## Decision 7: Database Roles and Row-Level Security

**Decision**: Enable Row-Level Security (RLS) on all tables from the first migration; keep policies permissive (allow all) until authentication is wired in Phase 3

**Rationale**: Enabling RLS from the start avoids the risk of forgetting it on production tables. Supabase's default behavior with RLS enabled is deny-all — so permissive stub policies (`USING (true)`) are added for each table in Phase 1 and replaced with real policies in Phase 3. This approach is recommended by Supabase for new projects.

**Constitution alignment**: Security & Privacy Requirements mandate that sensitive information be access-controlled. RLS is the primary mechanism for this in Supabase PostgreSQL.
