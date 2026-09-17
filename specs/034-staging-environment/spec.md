# Feature Specification: Isolated Staging Environment

Created: 2026-09-16

## Business Objective

Provide a production-like Triplyy staging environment for safe end-to-end checks and capacity testing without access to production data, credentials, users, or deployment images.

**Constitutional Domain**: Shared Foundations. **Affected Applications**: main, API, AI, deployment infrastructure, Supabase.

## User Scenarios & Acceptance Criteria

### User Story 1 — Deploy safely before production (P1)

An operator can deploy the `staging` branch to distinct Bunny services and a separate Supabase project.

1. Staging API, frontend, AI, and OSRM services do not share the production database, service-role secret, internal secret, or Bunny app.
2. Staging frontend assets are built with the staging Supabase and API URLs.
3. A staging deployment never changes a production image tag.

### User Story 2 — Test capacity without customer impact (P1)

An operator can run the read-only capacity scenario using a dedicated verified staging passenger account.

1. The test account exists only in staging.
2. The test uses the staging host and bearer token.
3. Results can be compared with protected per-instance API metrics.

## Functional Requirements

- FR-001: Pushes to `staging` must publish distinct `:staging` API, AI, and frontend images.
- FR-002: Frontend staging builds must read public build variables from the GitHub `staging` environment.
- FR-003: Staging requires its own Supabase project and all repository migrations.
- FR-004: Staging must use a separate Bunny Magic Containers app and isolated environment variables.
- FR-005: Staging API CORS and Supabase redirect URLs must include only the staging public origin in addition to localhost defaults.
- FR-006: Staging uses a newly generated internal secret and test-only credentials.

## Out of Scope

Automatic promotion to production, production load generation, production database copies, and a staging admin deployment.
