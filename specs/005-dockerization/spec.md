# Feature Specification: Dockerization

**Feature Branch**: `005-dockerization`

**Created**: 2026-06-17

**Status**: Draft

**Input**: Phase 4.1 — Containerize the FastAPI backend and Next.js frontend with nginx reverse proxy, following GitHub's best practices for Docker.

---

## Business Objective *(mandatory)*

Establish a reproducible, containerized runtime for every Fe El Seka service so that any developer can run the full platform locally with a single command, and the same images can be promoted to production without modification. This phase eliminates environment drift, enables predictable CI/CD pipelines, and prepares the platform for scalable deployment on any server that supports Docker.

**Constitutional Domain**: Platform Infrastructure

**Affected Applications**: Main App (`apps/main`) · Backend API (`backend/`) · AI Service (`services/ai`) · Shared infrastructure (nginx, Supabase CLI local)

---

## Clarifications

### Session 2026-06-17

- Q: Should Phase 4.1 also containerize the AI service (`services/ai`) or just the FastAPI backend and Next.js frontend? → A: Include AI service — add `services/ai/Dockerfile` and `ai` service to both compose files and CI pipeline.
- Q: Should GHCR images be public or private? → A: Public — no pull credentials needed; CI uses automatic `GITHUB_TOKEN`; GHCR packages set to public after first push.
- Q: Should production containers have CPU/memory resource limits? → A: Soft memory reservations only (`mem_reservation`): backend 256 MB, AI 512 MB, frontend 128 MB, nginx 64 MB. No hard limits for MVP.
- Q: What logging strategy should containerized services use? → A: Structured JSON to stdout/stderr (12-factor standard); Docker captures natively via json-file driver; log aggregation sidecar deferred post-MVP.
- Q: Should Docker images be built/scanned on pull requests, or only on main? → A: Build + scan on every PR (for early CVE feedback); publish to GHCR only on merge to main.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Developer Onboarding (Priority: P1)

A new developer joins the team, clones the repository, and needs to run the entire platform locally — backend, frontend, reverse proxy, and a local database — without installing Python, Node, or Postgres directly on their machine.

**Why this priority**: Without a working local environment, no development can happen. This story unblocks every other story in every phase.

**Independent Test**: On a fresh machine with only Docker and Supabase CLI installed, run `supabase start` followed by `docker compose up`. Navigate to `http://localhost/` and confirm the Next.js app renders. Hit `http://localhost/api/v1/health` and confirm the FastAPI backend responds. No manual config steps beyond `.env` setup should be required.

**Acceptance Scenarios**:

1. **Given** a machine with Docker Engine and Supabase CLI installed, **When** the developer runs `supabase start` then `docker compose up`, **Then** all services start without errors and are reachable on localhost within 60 seconds.
2. **Given** the development compose stack is running, **When** the developer edits a backend source file, **Then** the change is reflected in the running container within 5 seconds without a full rebuild.
3. **Given** the development compose stack is running, **When** the developer edits a frontend source file, **Then** the browser hot-reloads the change without a full rebuild.
4. **Given** the compose stack fails to start, **When** the developer reads the terminal output, **Then** the failure reason is clearly identified in plain English (missing `.env` file, port conflict, etc.).
5. **Given** the developer has multiple projects using Docker, **When** they start the Fe El Seka stack, **Then** all services use clearly named containers and a dedicated Docker network to avoid conflicts.

---

### User Story 2 — Production Deployment (Priority: P2)

A DevOps engineer needs to deploy the latest platform build to a Linux server. They pull pre-built images from the container registry, inject production secrets via environment files, and start the stack.

**Why this priority**: The platform must be deployable to a real server without rebuilding from source on the production machine.

**Independent Test**: Pull the latest images from GitHub Container Registry, configure a `.env.prod` file with real credentials, and run `docker compose -f docker-compose.prod.yml up -d`. Confirm all services start, nginx is reachable on ports 80 and 443, and the backend health check returns 200.

**Acceptance Scenarios**:

1. **Given** pre-built images published to the container registry, **When** the engineer runs the production compose file with a valid `.env.prod`, **Then** all services start and are reachable via the configured domain.
2. **Given** the production compose file, **When** the engineer inspects the running containers, **Then** no source code, development tools, or test files exist inside any production image.
3. **Given** a production container, **When** the engineer checks the running process, **Then** all processes run as a non-root user.
4. **Given** a service that fails to start, **When** the compose health check runs, **Then** Docker automatically restarts the container up to 3 times before marking it as unhealthy.
5. **Given** the production stack is running, **When** the engineer checks image sizes, **Then** the backend image is under 300 MB and the frontend image is under 200 MB.

---

### User Story 3 — CI/CD Pipeline (Priority: P3)

Every push to the main branch and every pull request triggers an automated pipeline that builds Docker images, runs lint/type checks, scans for vulnerabilities, and publishes verified images to GitHub Container Registry.

**Why this priority**: Manual image builds are error-prone and do not guarantee the published image matches what passed tests. Automated CI enforces build hygiene and gives the team confidence in every promoted image.

**Independent Test**: Open a pull request, observe the GitHub Actions workflow run. Confirm it builds all images, runs checks, scans for critical vulnerabilities, and reports a pass/fail status on the PR. On merge to main, confirm images are published to `ghcr.io/[org]/[service]:latest` and tagged with the commit SHA.

**Acceptance Scenarios**:

1. **Given** a push to any branch, **When** the CI pipeline runs, **Then** Docker images are built for both the backend and frontend services using Docker layer caching to minimize build time.
2. **Given** the CI pipeline builds images successfully, **When** the vulnerability scan runs, **Then** any CRITICAL or HIGH severity CVEs cause the pipeline to fail and block the PR.
3. **Given** a merge to the `main` branch, **When** all CI checks pass, **Then** images are tagged with both `latest` and the full commit SHA and pushed to GitHub Container Registry (ghcr.io).
4. **Given** a CI run that passes all checks, **When** a developer inspects the published image digest, **Then** the digest matches the image built in that exact CI run (no re-builds on push).
5. **Given** the GitHub Actions workflow file, **When** a reviewer reads it, **Then** no secrets are hardcoded — all credentials are sourced from GitHub Secrets.

---

### Edge Cases

- What if a developer's local port 80 is already in use? The compose file MUST document alternative port configuration; the startup error message MUST identify the conflict clearly.
- What if the `.env` file is missing when `docker compose up` is run? Docker Compose MUST fail fast with a human-readable error; it MUST NOT start with default/empty values that silently break the application.
- What if a CI build introduces a new critical vulnerability in a base image? The pipeline MUST fail and notify the team; a remediation workflow (base image update) MUST be documented.
- What if the Supabase CLI is not installed locally? The `docker-compose.yml` MUST include a setup section in its header comment directing the developer to the Supabase CLI prerequisite before running `docker compose up`.
- What if a developer runs `docker compose up` without running `supabase start` first? The backend service MUST fail its health check (connection refused to DB) and the compose log MUST display a clear database connection error — not a cryptic crash.

---

## Requirements *(mandatory)*

### Functional Requirements

**Container Definition**

- **FR-001**: The backend API service MUST be defined as a multi-stage Dockerfile: a `builder` stage installs all dependencies into an isolated virtual environment, and a `runner` stage copies only the virtual environment and application source — no build tools in the final image.
- **FR-001b**: The AI service (`services/ai`) MUST be defined as a separate multi-stage Dockerfile following the same pattern as FR-001: a `builder` stage installs Python dependencies, a `runner` stage copies only the virtual environment and service source.
- **FR-002**: The frontend app MUST be defined as a multi-stage Dockerfile: a `deps` stage installs node modules, a `builder` stage produces a Next.js standalone build, and a `runner` stage contains only the standalone output and static assets.
- **FR-003**: All three production images (backend, AI service, frontend) MUST run all processes as a dedicated non-root system user.
- **FR-004**: All three Dockerfiles MUST include a `HEALTHCHECK` instruction pointing to a lightweight liveness endpoint on the respective service.
- **FR-005**: All three services MUST define a `.dockerignore` file that excludes test files, development tooling, secrets files (`.env*`), and version control metadata.

**Reverse Proxy**

- **FR-006**: An nginx service MUST act as the single entry point for all HTTP traffic, routing requests with the path prefix `/api/` to the backend service, requests with the path prefix `/ai/` to the AI service, and all other requests to the frontend service.
- **FR-007**: The nginx configuration MUST forward the original client IP (`X-Real-IP`, `X-Forwarded-For`) and host headers to upstream services.
- **FR-008**: The nginx configuration MUST enable HTTP response compression (gzip) for text-based content types.

**Compose Orchestration**

- **FR-009**: A development compose file MUST mount backend, AI service, and frontend source directories as volumes, enabling live reload without container rebuilds.
- **FR-010**: A production compose file MUST use pre-built images from the container registry for all four services (backend, AI, frontend, nginx), apply `restart: always` to all services, source configuration from a production environment file, and define `mem_reservation` (soft memory limits) for each service to document expected usage and prevent uncontrolled runaway without hard-killing on burst.
- **FR-011**: No compose file MUST define hardcoded secret values; all secrets MUST be provided via `.env` files referenced through `env_file` directives or environment variable injection.
- **FR-012**: All services in both compose files MUST be connected via a named Docker network, isolating them from other Docker workloads on the same host.

**GitHub CI/CD Pipeline**

- **FR-013**: A GitHub Actions workflow MUST trigger on push to `main` and on all pull requests targeting `main`.
- **FR-014**: The CI workflow MUST build Docker images for all three services (backend, AI, frontend) on every trigger (both PR and `main` push) using GitHub Actions layer cache to avoid redundant rebuilds across runs.
- **FR-015**: The CI workflow MUST run a container vulnerability scan on all three images after every build; CRITICAL or HIGH severity findings MUST cause the workflow to fail and block the PR.
- **FR-016**: On successful merge to `main` only, the CI workflow MUST push all three images to GitHub Container Registry tagged with `latest` and the full commit SHA. Pull request builds MUST build and scan but MUST NOT publish images to the registry.
- **FR-017**: All registry credentials and deployment secrets referenced in the CI workflow MUST be sourced from GitHub repository secrets — never hardcoded in workflow files.

**GitHub Container Registry**

- **FR-018**: Images MUST be published to `ghcr.io` under the repository's GitHub organisation/owner namespace with **public** visibility, so production servers and developers can pull images without credentials.
- **FR-019**: Image names MUST follow the convention `ghcr.io/<owner>/fe-el-seka-<service>:<tag>` (e.g., `ghcr.io/adamba4a777/fe-el-seka-backend:latest`, `ghcr.io/adamba4a777/fe-el-seka-ai:latest`, `ghcr.io/adamba4a777/fe-el-seka-main:latest`).

### Key Entities

- **Docker Image**: A versioned, immutable artefact for one service. Attributes: service name, tag (latest / commit SHA), build date, image digest, base image version.
- **Docker Container**: A running instance of an image. Attributes: service name, health status, network membership, environment source, resource limits.
- **Compose Stack**: A named group of coordinated containers (backend + AI service + frontend + nginx). Two variants: `development` (hot-reload) and `production` (pre-built, restart policies).
- **GitHub Actions Workflow**: An automated pipeline triggered by git events. Attributes: trigger (push/PR), steps (build → scan → push), secrets used, cache keys.
- **Container Registry Entry**: A published image in GHCR. Attributes: image name, tags (`latest`, `<sha>`), digest, visibility (public/private).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with Docker and Supabase CLI installed can have the full platform running locally within 5 minutes of cloning the repository.
- **SC-002**: The production backend image size is under 300 MB; the production frontend image size is under 200 MB.
- **SC-003**: No secret values (API keys, database passwords, tokens) are present in any published Docker image layer.
- **SC-004**: The CI pipeline completes — build, scan, and push — in under 10 minutes on a standard GitHub Actions runner.
- **SC-005**: A source file edit in development is reflected in the running service within 5 seconds, without a container restart.
- **SC-006**: 100% of CI runs triggered by a merge to `main` that pass all checks result in a published image to GHCR tagged with the commit SHA.
- **SC-007**: All containers pass their health checks within 30 seconds of startup in both development and production.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Production Docker images MUST NOT contain development dependencies, test files, source maps (for frontend), or build tools.
- **NFR-008**: The production compose file MUST define `mem_reservation` for each service: backend 256 MB, AI service 512 MB, frontend 128 MB, nginx 64 MB. Hard memory limits (`mem_limit`) are not enforced for MVP to avoid OOM-killing on legitimate burst.
- **NFR-009**: All three application services (backend, AI service, frontend) MUST emit structured JSON logs to stdout/stderr. Log lines MUST include at minimum: timestamp, log level, service name, and message. Docker captures these natively via its default `json-file` log driver. Log aggregation sidecars (Loki, Fluentd) are deferred post-MVP.
- **NFR-002**: All processes inside containers MUST run as non-root users (UID ≥ 1000).
- **NFR-003**: Container images MUST be rebuilt from cache in CI when only application source changes (not base image or dependencies) — full cold rebuilds MUST NOT be required for routine deploys.
- **NFR-004**: The nginx reverse proxy MUST respond to `http://localhost/` within 200ms under local development load.
- **NFR-005**: The vulnerability scanner in CI MUST check against an up-to-date CVE database (refreshed at least daily by the scanner vendor).
- **NFR-006**: All compose environment variable references MUST fail fast — if a required variable is absent, the service MUST refuse to start rather than silently using an empty/default value.
- **NFR-007**: Docker images MUST use pinned base image digests (not floating tags like `python:3.11` alone) to prevent silent base image changes between builds.

---

## Dependencies *(mandatory)*

- **Internal**:
  - `001-platform-foundation` — the monorepo structure, `backend/` and `apps/main/` source directories, and existing environment variable files (`.env.example`) must exist before Dockerfiles can be written.
  - `004-ride-management` — a working FastAPI backend and Next.js frontend (with passing build) must exist before Docker images can be validated end-to-end.
  - `002-ai-foundation` — the AI service (`services/ai`) source directory and `requirements.txt` must exist; the service does not need to be fully trained, but it must start and serve a health check response.

- **External**:
  - Docker Engine 24+ and Docker Compose v2 must be installed on every developer machine.
  - Supabase CLI must be installed locally to run `supabase start` for the local development database.
  - A GitHub repository with Actions enabled and GitHub Container Registry access is required for the CI/CD pipeline.
  - The automatic `GITHUB_TOKEN` with `packages: write` permission is sufficient for CI image publishing (no additional PAT required); GHCR packages must be set to public visibility after the first push.

- **Data**: No new database schema. Existing `.env.example` files define the environment variable interface; Docker merely injects them at runtime.

---

## Out-of-Scope

- Kubernetes, Helm charts, or Docker Swarm — single-server Docker Compose is the target deployment model for MVP.
- TLS certificate provisioning and HTTPS termination — nginx handles HTTP only for MVP; TLS is terminated by an upstream load balancer or added in a later infrastructure phase.
- Containerizing Supabase — the managed Supabase cloud project is the production database; Supabase CLI local is used only for development.
- Load balancing across multiple backend replicas — single nginx upstream per service; horizontal scaling is a post-competition concern.
- Automated production deploys triggered by CI (push-to-deploy) — CI publishes images; the deploy step to a server remains a manual `docker compose pull && docker compose up -d` for MVP.
- Docker image signing and attestation — out of scope for MVP.

---

## Technical Considerations

- **Multi-stage builds are mandatory** — single-stage builds that include build tools in the final image violate NFR-001 and produce images that fail SC-002.
- **Next.js standalone output** — `output: 'standalone'` must be enabled in `next.config.js` before the frontend Dockerfile can produce a minimal runner stage; without this, the standalone directory does not exist.
- **Non-root user** — both Dockerfiles must create a dedicated system user (e.g., `appuser`) and switch to it via `USER` before the final `CMD`; running as root violates NFR-002 and is blocked by many production container runtimes.
- **Supabase CLI is outside compose** — `supabase start` manages its own Docker containers internally; the development `docker-compose.yml` MUST NOT attempt to start Supabase as a compose service. The two stacks coexist on the same Docker daemon but are independent.
- **GitHub Actions layer caching** — use `docker/build-push-action` with `cache-from: type=gha` and `cache-to: type=gha,mode=max` to persist layer cache between CI runs; without this, every CI run is a cold rebuild and SC-004 cannot be met.
- **GHCR authentication** — the `GITHUB_TOKEN` provided automatically by Actions has package:write permission by default when the repository is public; private repositories require an explicit `GHCR_PAT` secret with `write:packages` scope.
- **Pinned base image digests** — use `FROM python:3.11-slim@sha256:<digest>` syntax for reproducibility; update digests via automated Dependabot PRs rather than manually (Constitution §Quality Standards — maintainability).
- **nginx upstream service names** — in Docker Compose, the service name is the DNS hostname; nginx config MUST reference `backend` and `main` (the compose service names), not `localhost`.

---

## Assumptions

- Developers run macOS, Linux, or Windows with WSL2; Docker Desktop or Docker Engine is pre-installed.
- The GitHub repository is hosted under the `Adamba4a777` account; GHCR image paths follow `ghcr.io/adamba4a777/fe-el-seka-*`.
- A single `docker-compose.prod.yml` targeting one server is sufficient for the MVP competition demo; multi-region or multi-host deployments are not required.
- The `GITHUB_TOKEN` automatic secret has sufficient permissions for GHCR publish in this repository; no additional PAT provisioning is assumed necessary unless the repo is private.
- The Supabase CLI version used locally matches or is compatible with the Supabase project version in use; version pinning for the CLI is documented in the quickstart but not enforced by Docker.
- The `apps/main/next.config.js` does not currently have `output: 'standalone'` — enabling it is a required prerequisite task, not a blocking assumption.
