# Research: Dockerization

**Phase**: 0 | **Branch**: `005-dockerization` | **Date**: 2026-06-17

---

## Resolved Unknowns

| Unknown | Decision |
|---|---|
| Python Dockerfile approach (pip vs uv) | uv copy-install pattern — copy uv binary from `ghcr.io/astral-sh/uv`, use `uv sync --frozen --no-dev` |
| Next.js production output mode | Enable `output: 'standalone'` in `next.config.mjs`; runner copies `.next/standalone/` + `.next/static/` |
| Vulnerability scanner | Trivy (`aquasecurity/trivy-action`) — free, no account, daily CVE DB updates, GitHub native |
| Docker build caching in CI | `docker/build-push-action@v5` + `cache-from/to: type=gha,mode=max` |
| Internal port allocation | api → 8000, ai → 8000 (separate containers, no conflict), main → 3000, nginx → 80 |
| Separate vs extended CI workflow | New `.github/workflows/docker.yml` — keeps Docker concerns out of existing `ci.yml` |
| Base image pinning strategy | Pin SHA digests in Dockerfiles; Dependabot automates digest updates via `docker` ecosystem |
| Structured logging library (Python) | FastAPI/uvicorn JSON logging via `uvicorn --log-config`; configure `PYTHONUNBUFFERED=1` |

---

## Decision 1: uv in Docker (Python Services)

**Decision**: Copy the uv binary from `ghcr.io/astral-sh/uv:latest` in the builder stage. Use `uv sync --frozen --no-dev` to install production dependencies into the project virtualenv. Copy only `.venv` and `app/` to the runner stage.

**Rationale**: Both `services/api` and `services/ai` already use `uv` (with `uv.lock`). Using uv in Docker aligns with the existing toolchain, avoids re-solving dependencies, and is significantly faster than pip (10–100× on warm cache). The `--frozen` flag ensures the lock file is respected exactly.

**Pattern**:
```dockerfile
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.11-slim AS runner
COPY --from=builder /app/.venv /app/.venv
COPY app/ /app/app/
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
```

**Alternatives considered**:
- `pip install -r requirements.txt` — does not exist in these services (they use pyproject.toml + uv.lock); would require export step
- Multi-stage with full uv image as base — larger image (includes uv tooling in runner); not needed since only the binary is required

---

## Decision 2: Next.js Standalone Output

**Decision**: Add `output: 'standalone'` to `apps/main/next.config.mjs`. The Dockerfile builder stage runs `pnpm build` which produces `.next/standalone/server.js`. The runner copies only the standalone directory and static assets.

**Rationale**: Without `standalone` mode, the runner stage would need the full `node_modules` (~500 MB), violating SC-002. Standalone output traces and bundles only the required modules, producing a self-contained `server.js` with minimal dependencies.

**Pattern**:
```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable pnpm && pnpm install --frozen-lockfile

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

**Monorepo note**: `apps/main` is part of a pnpm workspace (root `pnpm-workspace.yaml`). The Dockerfile build context must be set to the monorepo root so `COPY packages/ ./packages/` (shared deps) can be included. Alternatively, use `--build-context` with Docker Buildx.

**Alternatives considered**:
- `output: 'export'` (static HTML) — rejected; app uses SSR/API routes
- Full `node_modules` in runner — rejected; violates SC-002 (image too large)

---

## Decision 3: Vulnerability Scanner — Trivy

**Decision**: Use `aquasecurity/trivy-action@0.24.0` (pinned version) for image scanning in GitHub Actions. Fail on CRITICAL or HIGH severity findings. Scan after build, before push.

**Rationale**: Trivy is the de-facto standard for GitHub Actions Docker vulnerability scanning. It's free, requires no external account or token, integrates directly with GHCR images, and updates its CVE database daily. The `aquasecurity/trivy-action` is officially maintained by Aqua Security and has 1M+ GitHub Stars usage.

**Alternatives considered**:
- Snyk (`snyk/actions/docker`) — requires Snyk account; free tier has scan limits
- Docker Scout (`docker/scout-action`) — requires Docker subscription for unlimited scans
- Grype — good alternative but less GitHub Actions native integration than Trivy

---

## Decision 4: GitHub Actions Layer Caching

**Decision**: Use `docker/build-push-action@v5` with GitHub Actions cache backend.

```yaml
- uses: docker/setup-buildx-action@v3
- uses: docker/build-push-action@v5
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
    push: ${{ github.ref == 'refs/heads/main' }}
```

**Rationale**: `type=gha` uses GitHub's built-in Actions cache (5 GB free per repo). `mode=max` caches all layers including intermediate stages, maximising cache hits for dependency-only stages. The `push` conditional ensures images are only pushed to GHCR on `main`, satisfying FR-016.

**Key actions required**:
```yaml
- uses: docker/setup-buildx-action@v3        # required for advanced caching
- uses: docker/login-action@v3               # GHCR auth
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}    # automatic; no PAT needed (public repo)
```

**Alternatives considered**:
- Registry cache (`type=registry`) — requires a separate cache registry; more complex setup
- No cache — every CI run is a cold build; SC-004 (10 min) cannot be met without caching

---

## Decision 5: Separate Docker Workflow File

**Decision**: Create `.github/workflows/docker.yml` as a new workflow alongside the existing `ci.yml`. The existing `ci.yml` handles linting, type checking, and unit tests. `docker.yml` handles Docker build, scan, and publish.

**Rationale**: Separating Docker concerns from the code quality CI avoids making the existing workflow longer and allows the Docker workflow to be paused or skipped independently (e.g., during rapid iteration). The two workflows can run in parallel on pull requests.

**`docker.yml` job sequence**:
```
build-api    ─┐
build-ai     ─┼─► scan-api, scan-ai, scan-main ─► push (main only)
build-main   ─┘
```
All three build jobs run in parallel. Each scan job depends only on its own build job. Push depends on all three scans passing.

---

## Decision 6: Port Allocation

| Service | Internal Port | Nginx Upstream Path |
|---|---|---|
| `services/api` | 8000 | `/api/` |
| `services/ai` | 8000 | `/ai/` |
| `apps/main` | 3000 | `/` (catch-all) |
| nginx | 80 (dev), 80+443 (prod) | — |

Both Python services use port 8000 internally — this is safe because each runs in its own container network namespace. nginx differentiates them by service name (`api:8000` vs `ai:8000`).

---

## Decision 7: Structured Logging (Python)

**Decision**: Configure uvicorn with `--log-config` pointing to a JSON log config file, and set `PYTHONUNBUFFERED=1` in the Dockerfile ENV. Application logs use Python's standard `logging` module with a `pythonjsonlogger.jsonlogger.JsonFormatter` or FastAPI's built-in access log format.

**Minimum required log fields** (per NFR-009): `timestamp`, `level`, `service`, `message`.

**uvicorn JSON logging**:
```python
# log_config.json
{
  "version": 1,
  "formatters": {
    "json": {
      "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
      "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
    }
  }
}
```

**Alternatives considered**:
- `structlog` — excellent but adds a dependency; standard `logging` + `python-json-logger` is lighter
- Plain text logging — rejected; violates NFR-009

---

## Decision 8: Monorepo Context for Frontend Dockerfile

**Decision**: Set the Docker build context to the monorepo root for `apps/main/Dockerfile` and use a path argument or `--build-context` to scope the image. In `docker-compose.yml`, set `build.context: .` (repo root) and `build.dockerfile: apps/main/Dockerfile`.

**Rationale**: `apps/main` imports from `packages/shared` and `packages/ui` (per `next.config.mjs` `transpilePackages`). These packages live outside `apps/main/` and cannot be copied if the build context is scoped to `apps/main/` only.

**Pattern in compose**:
```yaml
services:
  main:
    build:
      context: .
      dockerfile: apps/main/Dockerfile
```
