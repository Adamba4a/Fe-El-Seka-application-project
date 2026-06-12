# Feature Specification: Platform Foundation

**Feature Branch**: `001-platform-foundation`

**Created**: 2026-06-12

**Status**: Draft

**Input**: Competition MVP — Phase 1 — database-foundation (001), backend-foundation (002), frontend-foundation (003)

## Business Objective *(mandatory)*

Establish the monorepo foundation for Fe El Seka — a shared technical baseline encompassing the database schema with geospatial capability, backend API service scaffold, and two independently deployable front-end applications (main app for passengers and drivers; admin app for platform operations) — so that all subsequent product feature development can begin from a consistent, integrated, and deployable starting point.

**Constitutional Domain**: Platform Infrastructure

**Affected Applications**: Passenger App, Driver App, Admin Panel, Shared

---

## Clarifications

### Session 2026-06-12

- Q: How complete should the base schema be at the end of Phase 1? → A: Core identifying fields per entity — `users`: id, phone, role, created_at; `rides`: id, driver_id, origin (geometry), destination (geometry), departure_at, status; `bookings`: id, ride_id, passenger_id, status, created_at.
- Q: How should the base schema be applied and versioned? → A: Supabase built-in migrations — SQL files under `supabase/migrations/`, applied via the Supabase CLI.
- Q: Should the CI/CD pipeline include automated security scanning? → A: Secret detection only — CI fails if credentials or secrets are detected in committed files.
- Q: What should the health check response include? → A: Status + database + version — `{"status": "ok|degraded", "database": "connected|disconnected", "version": "<service version>"}`.
- Q: What is the minimum developer machine spec assumed for SC-001 and NFR-001? → A: 8 GB RAM, modern CPU (2018+), SSD.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Onboarding (Priority: P1)

A developer joins the project, clones the repository, follows the setup guide, and within minutes has a fully functional local environment with the main app, admin app, and backend API all running and communicating correctly.

**Why this priority**: Without a working local development environment, no feature development can begin. This is the prerequisite for every subsequent phase.

**Independent Test**: A developer with no prior exposure to the project can follow the setup guide, run the start command, and reach the main app's home page in a browser within 15 minutes.

**Acceptance Scenarios**:

1. **Given** a developer has cloned the repository, **When** they follow the onboarding instructions, **Then** both web applications and the backend API start successfully on their local machine.
2. **Given** the local environment is running, **When** the developer opens the main application in a browser, **Then** the application loads without errors and shows the default landing page.
3. **Given** the local environment is running, **When** the developer opens the admin application in a browser, **Then** the application loads without errors and shows the default admin landing page.
4. **Given** the environment variables are missing, **When** any application attempts to start, **Then** startup fails with a clear error message identifying each missing variable by name.

---

### User Story 2 - Database & Geospatial Readiness (Priority: P2)

A backend developer verifies that the database is correctly provisioned, spatial extensions are active, and the base schema is in place before writing any business logic.

**Why this priority**: Every subsequent feature depends on a correctly configured database. Geospatial queries for route matching require the spatial extension to be enabled from the start.

**Independent Test**: A developer can connect to the database, run a spatial query against a base table, and receive a valid result — confirming the spatial extension is active and the schema foundation is correct.

**Acceptance Scenarios**:

1. **Given** the database is provisioned, **When** a developer queries the base tables, **Then** all foundation tables exist with the correct structure and no errors are returned.
2. **Given** the spatial extension is enabled, **When** a geospatial query is executed (e.g., distance calculation between two coordinates), **Then** the query executes and returns a valid spatial result.
3. **Given** the backend API is running, **When** a health check request is sent to the API, **Then** the response confirms the database connection is active and healthy.
4. **Given** the database connection is unavailable, **When** the health check endpoint is called, **Then** the response reports the database as unhealthy without crashing the service.

---

### User Story 3 - Shared Package Reuse (Priority: P3)

A developer building any feature imports a shared type from the shared packages library and uses it in both the main application and admin application without duplication or compilation errors.

**Why this priority**: Shared types and components ensure consistency across applications and prevent duplication — required by Principle VII of the constitution.

**Independent Test**: A type defined in the shared package can be imported and used in both applications simultaneously without compilation errors.

**Acceptance Scenarios**:

1. **Given** the shared packages are configured, **When** a developer imports a shared type into the main application, **Then** the project compiles without errors.
2. **Given** the shared UI component library is configured, **When** a developer imports a shared UI component into the admin application, **Then** the component renders correctly without errors.
3. **Given** a shared type is updated, **When** both applications are rebuilt, **Then** type errors surface in both applications if the update introduces a breaking change.

---

### User Story 4 - CI/CD Pipeline Validation (Priority: P4)

A developer pushes code to a feature branch and the CI/CD pipeline automatically runs lint, type-check, and build verification across all applications before the pull request can be merged.

**Why this priority**: Automated quality gates protect the shared foundation from regressions and enforce consistent code quality from the first commit.

**Independent Test**: A pull request containing a deliberate type error triggers a CI failure, blocking the merge until the error is resolved.

**Acceptance Scenarios**:

1. **Given** a developer pushes code with a lint violation, **When** the CI pipeline runs, **Then** the pipeline fails and reports the specific lint issue.
2. **Given** a developer pushes valid code, **When** the CI pipeline runs, **Then** all checks pass and the pull request is eligible for merge.
3. **Given** the CI pipeline is triggered, **When** the run completes, **Then** all three applications (main app, admin app, backend API) produce valid build artifacts with zero errors.
4. **Given** a CI run starts, **When** all checks complete, **Then** the total pipeline duration does not exceed 10 minutes.

---

### Edge Cases

- What happens when the database cannot be reached during local startup? The backend API must start but mark the database connection as unhealthy in the health check response.
- What happens when a shared package change breaks downstream applications? The CI pipeline must detect the break across all affected applications in a single pipeline run.
- What happens when two applications depend on conflicting versions of a shared dependency? The monorepo workspace must surface the conflict as a build error rather than silently resolving it.
- What happens when a developer attempts to commit secrets or credentials to version control? The CI pipeline's secret detection scan MUST fail the pull request and report the file and line where the secret was detected.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST be organized as a monorepo containing the following root-level directories: `apps/main`, `apps/admin`, `packages/ui`, `packages/shared`, `services/api`, `services/ai`.
- **FR-002**: The main application (`apps/main`) MUST serve both passenger and driver experiences under a single deployment, with role-based routing applied after login.
- **FR-003**: The admin application (`apps/admin`) MUST be independently deployable and completely separate from the main application.
- **FR-004**: The backend API service (`services/api`) MUST expose a health check endpoint that returns a structured response containing: overall status (`ok` or `degraded`), database connectivity state (`connected` or `disconnected`), and the service version string.
- **FR-005**: The database MUST have the geospatial extension enabled and verified operational prior to any schema migration.
- **FR-006**: The database MUST include a base schema with core identifying fields for the three foundation entities: `users` (id, phone, role, created_at), `rides` (id, driver_id, origin as a spatial point, destination as a spatial point, departure_at, status), and `bookings` (id, ride_id, passenger_id, status, created_at). All tables MUST use UUID primary keys.
- **FR-006a**: The base schema MUST be defined as versioned Supabase migration files under `supabase/migrations/` and applied via the Supabase CLI, so that any developer can reproduce the exact schema state from a clean database by running a single migration command.
- **FR-007**: The shared types package (`packages/shared`) MUST export reusable TypeScript types and utility functions consumable by both front-end applications without code duplication.
- **FR-008**: The shared UI package (`packages/ui`) MUST export a base component library scaffold — including at minimum a button and input component — consumable by both front-end applications.
- **FR-009**: Environment configuration MUST support local and staging environments, with all credentials and secrets managed outside version control via environment variables.
- **FR-010**: A CI/CD pipeline MUST execute on every pull request targeting the main branch, running lint, type-check, and build verification for all applications in the monorepo.
- **FR-011**: The CI/CD pipeline MUST block pull request merges when any application fails lint, type-check, build verification, or secret detection.
- **FR-011a**: The CI/CD pipeline MUST include an automated secret detection scan on every pull request; the pipeline MUST fail and block the merge if any credentials, API keys, or secrets are detected in committed files.
- **FR-012**: The AI service scaffold (`services/ai`) MUST be initialized as a runnable service skeleton with a health check endpoint; no machine learning models are required in this phase.

### Key Entities

- **Monorepo Workspace**: The root repository coordinating all applications, packages, and services with unified dependency management and shared scripts.
- **Main Application**: The primary passenger- and driver-facing web application serving both roles under one deployment.
- **Admin Application**: The platform operations and administration web application, independently deployable.
- **Backend API Service**: The server-side business logic and data access service exposing REST endpoints.
- **AI Service Scaffold**: The machine learning service skeleton; operational in structure only in this phase.
- **Shared UI Package**: Reusable user interface components shared across applications without duplication.
- **Shared Types Package**: Reusable TypeScript types and utility functions shared across applications.
- **Database Foundation**: The provisioned relational database with geospatial extension enabled and base schema deployed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with no prior project exposure can set up a fully working local development environment in under 15 minutes by following the setup guide, on a machine with at least 8 GB RAM, a modern CPU (2018 or newer), and an SSD.
- **SC-002**: All applications in the monorepo build successfully with zero errors on a clean checkout in CI.
- **SC-003**: A geospatial spatial query executes successfully against the provisioned database, confirming spatial capability is operational before any feature development begins.
- **SC-004**: A shared type or component defined in a shared package compiles without errors in both front-end applications simultaneously.
- **SC-005**: Every pull request to the main branch triggers automated lint, type-check, and build checks across all monorepo applications and completes within 10 minutes.
- **SC-006**: The backend API health check endpoint responds within 1 second under normal conditions with all three required fields present: overall status, database connectivity state, and service version.
- **SC-007**: Zero credentials or secrets appear in any version-controlled file across the entire monorepo.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Local development startup for all services combined MUST complete in under 5 minutes after dependencies are installed, measured on a machine with at least 8 GB RAM, a modern CPU (2018 or newer), and an SSD.
- **NFR-002**: All credentials and secrets MUST NOT appear in any version-controlled file; environment variable injection is required for every environment.
- **NFR-003**: The CI/CD pipeline MUST complete a full monorepo check (lint, type-check, and build for all applications) in under 10 minutes.
- **NFR-004**: The monorepo structure MUST support independent deployment of the main application, admin application, and backend API service without requiring a full monorepo build.
- **NFR-005**: All geospatial data fields in the database foundation MUST use the spatial extension's native geometry types — not plain numeric coordinate columns.
- **NFR-006**: The platform foundation MUST support at least 1,000 concurrent active users as a baseline scalability target for all subsequent features built upon it.

---

## Dependencies *(mandatory)*

- **Internal**: None — this is the foundational phase with no upstream feature dependencies within the Fe El Seka specification set.
- **External**: A Supabase project must be provisioned with PostgreSQL and the PostGIS geospatial extension enabled before the database schema can be deployed.
- **External**: A GitHub repository must be created with branch protection rules configured on the main branch before CI/CD pipelines can be activated.
- **Data**: No prior data exists; the base schema is created from scratch in this phase.

---

## Out-of-Scope

- Authentication and user management — covered by Phase 3 specifications (004, 005).
- Identity and driver/passenger verification workflows — covered by Phase 3 specifications (006, 007, 008).
- AI model training, dataset pipelines, and model serving — covered by Phase 2 specifications (025–028); only the service scaffold is created here.
- Any product-level features (ride creation, booking, route matching, live tracking, payments) — covered by Phases 4–9.
- Admin dashboard product features — covered by Phase 3 basic admin foundation and Phase 11 full admin specs.
- Arabic/RTL localization — deferred post-competition.
- Production infrastructure hardening, monitoring, and alerting — deferred to post-competition Phase 12.
- Digital payment integration — deferred post-competition.
- Ratings, reporting, and safety systems — deferred post-competition Phase 10.

---

## Technical Considerations

- The monorepo structure uses the approved technology stack: Next.js 14 with TypeScript and Tailwind CSS for both front-end applications, Python FastAPI for both the backend API and AI services, Supabase PostgreSQL as the database (per the Constitution Technical Standards).
- Database schema changes MUST be managed as versioned Supabase migration files (`supabase/migrations/`) applied via the Supabase CLI; no ad-hoc schema edits are permitted.
- Geospatial fields in the database MUST use PostGIS geometry/geography types — never plain latitude/longitude numeric columns — per the Constitution Data Standards.
- All UUID primary keys are required for every entity per the Constitution Data Standards.
- The two Next.js applications (main and admin) must be structured as independently deployable units within the monorepo per Principle VII.
- The AI service scaffold (`services/ai`) is a Python FastAPI service initialized with runnable skeleton code; no machine learning models are trained or loaded in this phase.
- Environment secrets for local development use `.env` files excluded from version control; production secrets use Supabase Vault per the Constitution Security & Privacy Requirements.
- CI/CD pipelines are implemented using GitHub Actions per the approved development workflow.
- Backend services own all business logic; front-end applications are presentation and interaction layers only, per the Constitution Architecture Standards.

---

## Assumptions

- The Supabase project is provisioned manually by the project team before the database schema migration step runs; provisioning itself is outside the scope of this specification.
- The initial database schema covers the minimum required base tables for subsequent phases; it is not the complete domain schema (additional tables are added per-specification in later phases).
- GitHub Actions is the designated CI/CD platform; no alternative CI provider is evaluated for the MVP.
- All developers are assumed to have the required runtimes (Node.js, Python, package managers) installed as prerequisites before running the setup guide.
- The `services/ai` skeleton is initialized with runnable placeholder endpoints only; actual model files, training scripts, and datasets are the responsibility of Phase 2.
- Soft deletion will be the default strategy for transactional entities in the base schema, per the Constitution Data Standards.
