# Fe El Seka — Implementation Roadmap

**Version**: 1.0.0
**Date**: 2026-06-12
**Status**: Approved

---

## Project Overview

Fe El Seka is an Egyptian AI-powered route-sharing and carpooling platform.

Drivers create rides because they are already traveling to a destination.
Passengers discover and join existing rides that match their routes.

**Core Focus:**
- Cost reduction for drivers
- Affordable transportation for passengers
- Route-overlap-first matching
- Safety and trust
- AI-enhanced transportation intelligence

**Target Market:** University Students, Employees, Daily Commuters

**Initial Scale:** ~1,000 active users

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | Python FastAPI |
| Database | Supabase PostgreSQL + PostGIS |
| Auth | Supabase Auth (Phone OTP) |
| Storage | Supabase Storage |
| Realtime | Supabase Realtime |
| Maps | OpenStreetMap + OSRM |
| AI | Python AI Service, Scikit-Learn, XGBoost |
| Push Notifications | Firebase Cloud Messaging (FCM) |

---

## Development Philosophy

```
Constitution → Specification → Plan → Tasks → Implementation
```

Every feature must be implemented through a dedicated specification.
No implementation begins without an approved specification.

---

## Key Architecture Decisions

### Frontend: Two Applications

| App | Path | Purpose |
|---|---|---|
| Main App | `apps/main` | Passenger + Driver combined (role-based routing post-login) |
| Admin App | `apps/admin` | Platform administration (separate deployment) |

### AI Responsibility Boundary

**Deterministic Engine (PostGIS + OSRM):**
- Route feasibility validation
- Route overlap calculations
- Pickup and dropoff proximity calculations
- Candidate ride generation

**AI Models (Scikit-Learn + XGBoost):**
- Match score prediction
- Ride ranking
- Pricing recommendations

### AI Training Data Strategy

**Model 1 — Transportation Network Model:**
- Source: Kaggle datasets + OpenStreetMap road networks for Cairo
- Purpose: ETA estimation, route similarity scoring, ride ranking features
- Approach: Train on real geographic data before any user data exists

**Model 2 — Ride Behavior Model:**
- Source: 100,000+ synthetically generated rides simulating Egyptian transportation patterns
- Purpose: Teach the model how real rides behave in Cairo (pickup clusters, commute corridors, demand zones)
- Approach: Synthetic generation with realistic Cairo-specific parameters (traffic patterns, districts, universities, business zones)

### Payments: Cash-Only (MVP)

Passengers pay drivers in cash at pickup. The platform:
- Tracks driver balance (commission owed)
- Deducts commission from driver wallet
- Driver wallet is topped up manually (no payment gateway for MVP)

### Identity Verification: Manual Admin Review

Users upload a photo of their National ID. Admin manually reviews and approves via admin dashboard. No third-party KYC API for MVP.

### Language: English First

UI is in English for MVP. Arabic/RTL localization is deferred post-competition.

---

## Roadmap Structure

This document defines two tracks:

1. **Competition MVP** — 9 phases, 1-month delivery, AI mandatory
2. **Post-Competition** — Deferred features, no architectural redesign required

---

# Competition MVP — 1 Month

## Phase 1 — Platform Foundation

**Goal:** Establish the technical foundation required for all future work.

**Specifications:**

| ID | Name |
|---|---|
| 001 | database-foundation |
| 002 | backend-foundation |
| 003 | frontend-foundation |

**Deliverables:**
- Monorepo structure (`apps/main`, `apps/admin`, `packages/ui`, `packages/shared`, `services/api`, `services/ai`)
- FastAPI project setup with Supabase connection
- Two Next.js applications: main app (passenger + driver) and admin app
- Shared UI component library
- Shared TypeScript types and utilities
- Supabase project configuration (PostgreSQL + PostGIS enabled)
- Environment management (`.env` structure for local/staging)
- CI/CD foundation (GitHub Actions)
- Database schema foundation (PostGIS extension, base tables)

**Dependencies:** None

---

## Phase 2 — AI Foundation

**Goal:** Build AI infrastructure and train initial models before ride data exists.

> AI is a mandatory competition requirement. This phase is prioritized before auth and rides so models are trained and serving by the time the app is functional.

**Specifications:**

| ID | Name |
|---|---|
| 025 | ai-foundation |
| 026 | ai-dataset-pipeline |
| 027 | ai-training-pipeline |
| 028 | ai-model-serving |

**Deliverables:**
- Standalone Python AI service (`services/ai`) with FastAPI endpoints
- Dataset ingestion pipeline:
  - Kaggle/OpenStreetMap Cairo road network loader
  - Synthetic ride generator (100,000+ rides with Cairo-realistic parameters)
  - Feature engineering pipeline
- Model training pipeline:
  - Match score prediction model (XGBoost)
  - Ride ranking model (XGBoost + feature importance)
  - Price recommendation model (Scikit-Learn)
- Model registry (versioned artifacts stored in Supabase Storage)
- Prediction API endpoints consumed by the main backend

**AI Scope for Competition MVP:**
1. Match score prediction
2. Ride ranking
3. Price recommendation

**Dependencies:** Phase 1

---

## Phase 3 — Authentication & Verification

**Goal:** Build trust and identity systems.

**Specifications:**

| ID | Name |
|---|---|
| 004 | authentication |
| 005 | user-management |
| 006 | passenger-verification |
| 007 | driver-verification |
| 008 | vehicle-management |
| 035-basic | admin-foundation (basic) |

**Deliverables:**
- Phone OTP authentication via Supabase Auth
- User profile creation and management
- Passenger verification: National ID upload + manual admin review workflow
- Driver verification: National ID upload + license upload + manual admin review
- Vehicle registration (make, model, year, plate, color, capacity)
- Verification status management (pending / approved / rejected)
- Basic admin dashboard for reviewing and actioning verification requests

**Notes:**
- Admin authentication is separate (admin app, separate Supabase role)
- No KYC API — admin manually reviews uploaded ID photos
- Verification is required before a driver can create rides or a passenger can book

**Dependencies:** Phase 1

---

## Phase 4 — Ride Management

**Goal:** Allow drivers to publish rides.

**Specifications:**

| ID | Name |
|---|---|
| 009 | driver-ride-creation |
| 010 | driver-ride-management |
| 011 | seat-management |

**Deliverables:**
- Create ride (origin, destination, waypoints, departure time, seats, price)
- Route polyline stored as PostGIS geometry
- Edit ride (pre-departure only)
- Cancel ride
- Seat management (available, reserved, confirmed)
- Ride visibility controls (active / paused / cancelled / completed)

**Dependencies:** Phase 3

---

## Phase 4.1 — Dockerization

**Goal:** Containerize all services for reproducible local development and production deployment. This phase is a prerequisite for all subsequent phases — every team member runs an identical environment from here forward.

**Specifications:**

| ID | Name |
|---|---|
| 004-D | dockerization |

**Deliverables:**
- `backend/Dockerfile` (Python 3.11-slim, multi-stage, uvicorn)
- `apps/main/Dockerfile` (Node 20-alpine, multi-stage, Next.js standalone output)
- `nginx/nginx.conf` (reverse proxy: `/api/*` → FastAPI, `/*` → Next.js)
- `docker-compose.yml` (development: hot-reload volumes, Supabase CLI for local DB)
- `docker-compose.prod.yml` (production: pre-built images, restart policies)
- `.dockerignore` files for backend and frontend
- Docker-specific environment variable documentation

**Dependencies:** Phase 4

---

## Phase 4.2 — Frontend Design (Stitch MCP)

**Goal:** Generate polished, mobile-first UI designs for all existing screens using Google Stitch MCP, and establish the design system that all future phases will follow.

> Doing this now (after ride management, before route intelligence) means Phases 5–9 build new features with the design patterns already in place — not as a post-hoc polish pass.

**Specifications:**

| ID | Name |
|---|---|
| 004-F | frontend-design |

**Deliverables:**
- Stitch-generated UI for all Auth & Verification screens
- Stitch-generated UI for all Ride Management screens (dashboard, create, detail, edit)
- Design system tokens (colors, typography, spacing) established in Tailwind config
- `RideCard`, `RideStatusBadge`, `RideHistoryLog`, `StartCompleteActions` components polished
- Map UI (full-screen with slide-up form panel) for ride creation/editing
- All screens pass `pnpm --filter main build` with no TypeScript errors

**Dependencies:** Phase 4, Phase 4.1 (containerized local environment for preview)

---

## Phase 5 — Route Intelligence

**Goal:** Build the deterministic transportation intelligence foundation.

**Specifications:**

| ID | Name |
|---|---|
| 012 | route-engine-foundation |
| 013 | route-overlap-engine |
| 014 | matching-engine |
| 022 | pricing-engine |

**Deliverables:**
- OSRM integration for route calculations (distance, duration, polyline)
- Route overlap analysis: percentage of passenger route covered by driver route
- Pickup proximity analysis: walk distance from passenger origin to driver pickup point
- Dropoff proximity analysis: walk distance from driver dropoff to passenger destination
- Detour calculation: added distance/time for driver to serve passenger
- Candidate ride generation: filter rides by geographic and temporal constraints
- Deterministic fare calculation (base fare + per-km + surge factor)

**AI Integration Point:** Candidate rides generated here are passed to the AI service (Phase 9) for scoring and ranking before being returned to passengers.

**Dependencies:** Phase 4

---

## Phase 6 — Passenger Experience

**Goal:** Allow passengers to discover and join rides.

**Specifications:**

| ID | Name |
|---|---|
| 015 | ride-search |
| 016 | ride-details |
| 017 | booking-system |
| 018 | booking-management |

**Deliverables:**
- Ride search: origin + destination + date input
- Search results ranked by AI match score (from Phase 9)
- Ride detail view (driver info, route map, seats, price, ETA)
- Booking creation (seat reservation + status: pending)
- Driver booking confirmation/rejection
- Booking cancellation (passenger and driver)
- Booking status management (pending / confirmed / cancelled / completed)

**Dependencies:** Phase 5

---

## Phase 7 — Real-Time Transportation

**Goal:** Enable active ride tracking and notifications.

**Specifications:**

| ID | Name |
|---|---|
| 019 | live-location-tracking |
| 020 | ride-status-system |
| 021 | real-time-updates |
| 043 | push-notifications |

**Deliverables:**
- Driver live location broadcasting (GPS → Supabase Realtime)
- Passenger live map view of driver position
- ETA updates as driver approaches pickup
- Ride progress states: scheduled / in-progress / completed / cancelled
- Realtime ride events via Supabase Realtime channels
- Push notifications via Firebase Cloud Messaging (FCM):
  - Booking confirmed / rejected
  - Driver is N minutes away
  - Ride started / completed
  - Ride cancelled

**Dependencies:** Phase 6

---

## Phase 8 — Financial System

**Goal:** Implement platform revenue tracking (cash-only flow).

**Specifications:**

| ID | Name |
|---|---|
| 023 | driver-balance-system |
| 024 | commission-management |

**Deliverables:**
- Driver balance ledger (credit / debit entries)
- Commission calculation per completed ride
- Automatic commission deduction from driver balance on ride completion
- Negative balance enforcement (driver cannot create rides if balance below threshold)
- Manual balance top-up by admin
- Financial audit trail (immutable ledger entries)

**Notes:**
- No payment gateway. Passengers pay drivers in cash at pickup.
- Platform commission is collected by deducting from the driver's pre-loaded balance.
- No digital payment integration for MVP.

**Dependencies:** Phase 6

---

## Phase 9 — AI Application

**Goal:** Deploy trained AI models to power match scoring, ranking, and pricing.

**Specifications:**

| ID | Name |
|---|---|
| 029 | ai-route-matching |
| 030 | ai-ride-ranking |
| 031 | ai-pricing-recommendations |

**Deliverables:**
- Match score prediction: per (passenger-request, candidate-ride) pair
- Confidence scoring for each match
- AI-ranked ride results returned to passenger search
- AI-recommended price for driver ride creation
- Feature importance reporting (for transparency and debugging)
- Fallback to deterministic scoring if AI service is unavailable

**Integration:** The deterministic engine (Phase 5) generates candidates. This phase scores and ranks them. Passengers see results already sorted by AI match score.

**Dependencies:** Phase 2, Phase 5

---

## Competition MVP — Spec Index

| Spec ID | Name | Phase | Status |
|---|---|---|---|
| 001 | database-foundation | 1 | MVP |
| 002 | backend-foundation | 1 | MVP |
| 003 | frontend-foundation | 1 | MVP |
| 025 | ai-foundation | 2 | MVP |
| 026 | ai-dataset-pipeline | 2 | MVP |
| 027 | ai-training-pipeline | 2 | MVP |
| 028 | ai-model-serving | 2 | MVP |
| 004 | authentication | 3 | MVP |
| 005 | user-management | 3 | MVP |
| 006 | passenger-verification | 3 | MVP |
| 007 | driver-verification | 3 | MVP |
| 008 | vehicle-management | 3 | MVP |
| 035-basic | admin-foundation | 3 | MVP (basic) |
| 009 | driver-ride-creation | 4 | MVP |
| 010 | driver-ride-management | 4 | MVP |
| 011 | seat-management | 4 | MVP |
| 004-D | dockerization | 4.1 | MVP |
| 004-F | frontend-design | 4.2 | MVP |
| 012 | route-engine-foundation | 5 | MVP |
| 013 | route-overlap-engine | 5 | MVP |
| 014 | matching-engine | 5 | MVP |
| 022 | pricing-engine | 5 | MVP |
| 015 | ride-search | 6 | MVP |
| 016 | ride-details | 6 | MVP |
| 017 | booking-system | 6 | MVP |
| 018 | booking-management | 6 | MVP |
| 019 | live-location-tracking | 7 | MVP |
| 020 | ride-status-system | 7 | MVP |
| 021 | real-time-updates | 7 | MVP |
| 043 | push-notifications | 7 | MVP |
| 023 | driver-balance-system | 8 | MVP |
| 024 | commission-management | 8 | MVP |
| 029 | ai-route-matching | 9 | MVP |
| 030 | ai-ride-ranking | 9 | MVP |
| 031 | ai-pricing-recommendations | 9 | MVP |

**Total Competition MVP Specs: 35**

---

# Post-Competition Roadmap

Features deferred until after the competition. The MVP architecture is designed so all of these add cleanly without structural changes.

## Phase 10 — Trust & Community

| ID | Name |
|---|---|
| 032 | ratings-system |
| 033 | reporting-system |
| 034 | safety-moderation |

**Deliverables:** Driver + passenger ratings, user reporting, moderation workflows

---

## Phase 11 — Admin Operations (Full)

| ID | Name |
|---|---|
| 035 | admin-dashboard (full) |
| 036 | user-management-admin |
| 037 | verification-admin |
| 038 | financial-admin |

**Deliverables:** Full admin dashboard, user oversight, verification queue management, financial monitoring, platform analytics

---

## Phase 12 — Production Readiness

| ID | Name |
|---|---|
| 039 | performance-optimization |
| 040 | security-hardening |
| 041 | production-deployment |
| 042 | monitoring-observability |

**Deliverables:** Load testing, security review, production infrastructure, monitoring, alerting, backup procedures

---

## Phase 13 — Advanced AI

**Goal:** Extend AI capabilities once real ride data is available.

| ID | Name |
|---|---|
| TBD | demand-forecasting |
| TBD | fraud-detection |
| TBD | ai-dataset-pipeline-v2 (real data) |
| TBD | ai-training-pipeline-v2 (production retraining) |

**Deliverables:** Demand prediction per zone/time, fraud and anomaly detection, model retraining on live ride data

---

## Phase 14 — Localization

| ID | Name |
|---|---|
| TBD | arabic-rtl-localization |

**Deliverables:** Full Arabic UI, RTL layout, bilingual language toggle, next-intl integration

---

## Phase 15 — Digital Payments

| ID | Name |
|---|---|
| TBD | payment-gateway-integration |

**Deliverables:** Paymob or Fawry integration, card payments, Fawry cash, InstaPay, automated commission collection

---

## MVP Success Criteria

The competition MVP is considered successful when:

- [ ] Drivers can create rides with route geometry
- [ ] Passengers can search and discover rides by route overlap
- [ ] AI match scoring, ranking, and pricing recommendations are operational
- [ ] Identity verification workflow is operational (upload → admin review → approval)
- [ ] Live ride tracking is operational
- [ ] Driver balance and commission deduction are operational
- [ ] Push notifications are delivered for key ride events
- [ ] The platform supports at least 1,000 active users
- [ ] AI models are trained and serving predictions (not rule-based fallbacks)

---

## Full Roadmap Success Criteria

The platform is considered production-ready when:

- [ ] All competition MVP criteria are met
- [ ] Ratings and safety systems are operational
- [ ] Full admin operations are available
- [ ] Production infrastructure is hardened and monitored
- [ ] Arabic/RTL localization is complete
- [ ] Digital payment integration is live
- [ ] AI models are retrained on real ride data

---

*This roadmap is governed by the Fe El Seka Project Constitution v1.0.0.*
*Every spec must go through: Specification → Plan → Tasks → Implementation.*
*No implementation begins without an approved specification.*
