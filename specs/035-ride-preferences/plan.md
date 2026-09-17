# Implementation Plan: Ride Preferences and Round Trips

**Branch**: `035-ride-preferences` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

## Summary

Add private profile gender collection, women-only ride eligibility, independently bookable linked round-trip legs, and recurring round-trip scheduling with safe single-date paired-time overrides. The API remains authoritative: it creates paired normal ride rows atomically, enforces women-only eligibility before booking mutations, and locks both recurring legs before any date-specific override.

## Technical Context

**Language/Version**: Python 3.11; TypeScript 5 / Next.js 14.  
**Primary Dependencies**: FastAPI, asyncpg, Pydantic, Next.js, React, next-intl, Supabase PostgreSQL/PostGIS.  
**Storage**: Supabase PostgreSQL with existing `profiles`, `rides`, `bookings`, and `recurring_ride_definitions` tables.  
**Testing**: pytest service/API tests; existing TypeScript typecheck and frontend tests.  
**Target Platform**: Linux API service and mobile-first web application.  
**Project Type**: Monorepo: `services/api`, `apps/main`, `packages/shared`, and `supabase/migrations`.  
**Performance Goals**: Keep existing ride create/edit and booking response targets; paired creation/override stays transactional.  
**Constraints**: Backend owns all eligibility and chronology validation; gender is private; no seat/wallet/booking mutation for an ineligible booking; return routes use existing OSRM pricing.  
**Scale/Scope**: One new migration; one-off and recurring ride flows, profile onboarding, ride discovery/detail/dashboard, and booking enforcement.

## Constitution Check

| Principle / Standard | Status | Evidence |
|---|---|---|
| Trust before transportation | Pass | Gender-restricted ride posting and booking are API-enforced. |
| Route intelligence | Pass | Return legs are normal reverse-route rides calculated by existing routing/pricing services. |
| Backend owns business logic | Pass | UI is advisory; profile/ride/booking/override services enforce all rules. |
| Operational history and integrity | Pass | Existing ride/booking histories remain per normal ride row; paired operations are atomic. |
| Sensitive data protected | Pass | Gender is private and excluded from public-profile and ride responses. |
| Shared foundations | Pass | Shared TypeScript types change alongside API contracts. |

No violations or complexity exceptions.

## Project Structure

```text
supabase/migrations/
  <timestamp>_ride_preferences_and_round_trips.sql
services/api/app/
  models/{profile,ride,recurring_ride}.py
  services/{profile_service,ride_service,booking_service,recurring_ride_service}.py
  api/{profiles/router.py,rides/router.py,rides/recurring_router.py}
  tests/{unit,integration}/
apps/main/src/
  app/(onboarding)/profile/page.tsx
  app/(driver)/rides/{new,page.tsx,recurring/[id]/page.tsx}
  app/(passenger)/rides/[id]/{page.tsx,book/page.tsx}
  components/rides/{RideForm,RideCard}.tsx
  lib/api/{profiles,rides,recurring-rides}.ts
  messages/{en,ar}.json
packages/shared/src/types/{user,rides}.ts
specs/035-ride-preferences/
  spec.md, research.md, data-model.md, quickstart.md, contracts/rides-api.md, tasks.md
```

**Structure Decision**: Extend the established single main-app/API monorepo paths. Round-trip legs deliberately reuse the existing `Ride` and `Booking` entities rather than adding parallel booking logic.

## Implementation Approach

1. Migrate private profile gender and the one-way/paired-leg ride schema with backward-compatible defaults. Extend recurring definitions and replace their per-date uniqueness guard so each recurring round trip can generate two legs.
2. Extend private profile schemas/service/onboarding and shared types; preserve exclusion of gender from all public responses.
3. Extend one-off ride create/edit service and contracts. For a round trip, validate both legs and create reverse-route paired rides in one transaction; validate pair chronology on later individual edits.
4. Add women-only creation/edit validation and booking-service enforcement before seat mutation; surface the badge in driver and passenger UI.
5. Extend recurring creation/edit/generation to copy leg-specific data and create pairs; add the atomic occurrence-date override endpoint and UI action.
6. Add bilingual UI labels/messages and verification coverage for migrations, pairing, gender privacy, transactional booking rejection, recurrence generation, and override atomicity.

## Verification Strategy

- Migration tests prove legacy rows become unrestricted one-way records and recurring uniqueness permits exactly two legs per date.
- Service tests prove only woman drivers can enable women-only, ineligible booking attempts leave no side effects, and paired edits preserve chronology.
- Recurring tests prove generation/updates/overrides create and modify both legs atomically while honoring bookings and cutoffs.
- Run Python tests covering ride, booking, recurring, and profile behavior; run main-app typecheck and relevant frontend tests; execute the scenarios in [quickstart.md](quickstart.md).
