# Contributing to Fe El Seka

## Branch Naming

Feature branches follow sequential spec numbering:

```
<spec-number>-<short-description>
```

Examples: `001-platform-foundation`, `002-user-auth`, `003-ride-matching`

## Pull Request Requirements

All PRs must:
1. Target `main`
2. Pass the full CI pipeline (`secret-scan` → `ci-typescript` + `ci-api` + `ci-ai`)
3. Include a description linking the relevant spec (e.g., `specs/001-platform-foundation/spec.md`)
4. Have at least one reviewer approved

## Branch Protection

Configure on GitHub → Settings → Branches → Add rule for `main`:

- Require a pull request before merging
- Require status checks to pass before merging:
  - `Secret Scan`
  - `TypeScript Apps`
  - `API Service`
  - `AI Service`
- Require branches to be up to date before merging
- Do not allow bypassing the above settings

## Local Development

```bash
# Install dependencies
pnpm install

# Run all services in parallel
pnpm dev

# TypeScript checks
pnpm turbo typecheck

# Linting
pnpm turbo lint

# Python linting (from services/api or services/ai)
uv run ruff check .
uv run mypy app
```

## Commit Style

Use imperative mood, present tense:

```
add user authentication endpoint
fix ride status state machine
update database migration for bookings
```
