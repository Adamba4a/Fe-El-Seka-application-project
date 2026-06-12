# Quickstart & Validation Guide: Platform Foundation

**Branch**: `001-platform-foundation` | **Date**: 2026-06-12
**Spec**: [spec.md](spec.md) | **Data Model**: [data-model.md](data-model.md) | **Contracts**: [contracts/health-check.md](contracts/health-check.md)

---

## Prerequisites

Before running validation, confirm the following are installed:

| Tool | Minimum Version | Check |
|------|----------------|-------|
| Node.js | 20 LTS | `node --version` |
| pnpm | 8+ | `pnpm --version` |
| Python | 3.11+ | `python --version` |
| uv | 0.4+ | `uv --version` |
| Supabase CLI | 1.200+ | `supabase --version` |
| Git | 2.40+ | `git --version` |

**External requirements**:
- Supabase project provisioned with PostgreSQL + PostGIS extension enabled
- `.env` files in place for each service (copy from `.env.example` files and fill in Supabase credentials)
- GitHub repository created with branch protection on `main`

---

## Step 1 — Install Dependencies

From the repository root:

```bash
pnpm install
```

Expected: All workspace packages resolve without errors. No dependency conflicts reported.

---

## Step 2 — Start All Services

```bash
pnpm dev
```

Expected outcomes (SC-001 target: all services running within 15 minutes of fresh clone):

| Service | URL | Expected |
|---------|-----|----------|
| Main App | `http://localhost:3000` | Default landing page loads |
| Admin App | `http://localhost:3001` | Default admin landing page loads |
| Backend API | `http://localhost:8000` | FastAPI welcome or redirect |
| AI Service | `http://localhost:8001` | FastAPI welcome or redirect |

If services don't start within 5 minutes after dependencies are installed, check for missing environment variables (the service should print the missing variable name and exit).

---

## Step 3 — Validate Health Check Endpoints (FR-004, SC-006)

```bash
curl http://localhost:8000/health
```

Expected response within 1 second:
```json
{"status": "ok", "database": "connected", "version": "0.1.0"}
```

```bash
curl http://localhost:8001/health
```

Expected response:
```json
{"status": "ok", "database": "connected", "version": "0.1.0"}
```

See [contracts/health-check.md](contracts/health-check.md) for full field definitions.

---

## Step 4 — Validate Database Schema (FR-006, SC-003)

Apply migrations to a fresh local database:

```bash
supabase db reset
```

Expected: Migrations in `supabase/migrations/` apply in order with no errors.

Then run a spatial query to confirm PostGIS is active (FR-005, SC-003):

```bash
supabase db execute --sql "SELECT ST_Distance(
  ST_SetSRID(ST_MakePoint(31.2357, 30.0444), 4326)::geography,
  ST_SetSRID(ST_MakePoint(31.2197, 30.0561), 4326)::geography
) AS distance_meters;"
```

Expected: A numeric distance result in meters (approximately 2200 m for these Cairo coordinates). No errors.

Confirm foundation tables exist:

```bash
supabase db execute --sql "\dt"
```

Expected: `users`, `rides`, `bookings` listed as tables.

---

## Step 5 — Validate Shared Packages (FR-007, FR-008, SC-004)

From the repository root:

```bash
pnpm turbo typecheck
```

Expected: All packages type-check with zero errors. Both `apps/main` and `apps/admin` resolve shared types from `packages/shared` and shared components from `packages/ui` without errors.

---

## Step 6 — Validate Full Build (SC-002)

```bash
pnpm turbo build
```

Expected: All applications produce build artifacts with zero errors:
- `apps/main/.next/` — Next.js build output
- `apps/admin/.next/` — Next.js build output
- `services/api` — Python uv confirms no import errors
- `services/ai` — Python uv confirms no import errors

---

## Step 7 — Validate CI Pipeline Locally (FR-010, FR-011)

Simulate the CI lint + type-check step:

```bash
pnpm turbo lint
pnpm turbo typecheck
```

Expected: Both commands exit with code 0. Any lint violation exits with a non-zero code and prints the file and line.

Simulate secret detection (requires Gitleaks installed locally):

```bash
gitleaks detect --source . --verbose
```

Expected: No secrets detected. If a `.env` file with a real credential is accidentally staged, Gitleaks reports the file, line, and matched rule — confirming FR-011a works.

---

## Step 8 — Validate Environment Variable Enforcement (FR-009)

Remove one required environment variable and restart a service:

```bash
# Temporarily unset a required var (example)
SUPABASE_URL="" pnpm --filter @fe-el-seka/api dev
```

Expected: The service exits immediately with a message naming the missing variable. It does NOT start in a partially-configured state.

---

## Validation Checklist

| Check | Command | Pass Condition |
|-------|---------|----------------|
| SC-001 Developer onboarding | `pnpm install && pnpm dev` | All 4 services up within 15 min |
| SC-002 Clean build | `pnpm turbo build` | Zero errors across all apps |
| SC-003 PostGIS active | Spatial SQL query | Returns distance in meters |
| SC-004 Shared packages | `pnpm turbo typecheck` | Zero type errors across workspace |
| SC-005 CI pipeline | GitHub Actions PR trigger | All checks pass, under 10 min |
| SC-006 Health check speed | `curl /health` | Response under 1 second |
| SC-007 No secrets in VCS | `gitleaks detect` | Zero secrets detected |
| NFR-001 Startup time | Timer from `pnpm dev` | Under 5 min post-install |

---

## Troubleshooting

**Services fail to start with "missing environment variable"**
Copy `.env.example` to `.env.local` in each app/service directory and fill in your Supabase project credentials.

**PostGIS spatial query returns an error**
Confirm the PostGIS extension is enabled on your Supabase project: `SELECT * FROM pg_extension WHERE extname = 'postgis';`

**Type errors in `packages/ui` or `packages/shared`**
Run `pnpm install` from the root to ensure workspace symlinks are created. Delete `node_modules` and re-install if symlinks are stale.

**Gitleaks reports a false positive**
Add a `[allowlists]` entry in `.gitleaks.toml` with the specific file path or regex pattern.
