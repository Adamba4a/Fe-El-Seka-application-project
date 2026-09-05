# Triplyy — Product Specification (Current State, 2026-09-04)

## Purpose

Triplyy is an AI-powered route-sharing and carpooling platform for Egypt.
Drivers create rides because they are already traveling to a destination;
passengers discover and join rides that overlap with their own route.

**Target market:** university students, employees, daily commuters.
**Core value props:** cost reduction for drivers, affordable transport for
passengers, route-overlap-first matching, safety/trust, AI-enhanced ranking.

## Applications & Services

| Component | Tech | Port | Purpose |
|---|---|---|---|
| Main app | Next.js 14 (App Router) | 3000 | Combined passenger + driver app, role-based routing after login |
| Admin app | Next.js 14 | 3001 | Internal ops dashboard (rides, users, verification, finance) |
| Core API | FastAPI (asyncpg) | 8000 | REST API for all product features |
| AI service | FastAPI (scikit-learn, XGBoost) | 8001 | Match scoring, ride ranking, pricing signals |
| Database | Supabase Postgres 15 + PostGIS | — | Geo queries, RLS-secured tables |
| Routing engine | OSRM | — | Route feasibility, distance/duration, road-network geometry |

## Authentication & Trust

- Sign-in: **password** or **Google OAuth**, plus a **one-time OTP**
  verification step (not phone-OTP-only — that was superseded).
- **National ID / photo identity verification has been removed entirely**
  (legal reasons). It is not a gate anywhere in the product.
- The sole trust floor is **org-email verification**: a user proves control
  of a company/university email domain via OTP. `org_verified_at` being set
  gates ride posting, booking, and sponsored-group access
  (`require_org_verified` dependency).
- Regular (non-sponsored) groups have unconditional/open membership.
  Sponsored groups (employer/university-backed) require domain-email OTP to join.

## Core Ride Flow

1. **Driver posts a ride** — requires an active vehicle + org-verified profile.
   OSRM computes route geometry/distance/duration; a fare is calculated
   (fuel cost, platform commission, distance fee, safety margin,
   fair per-seat price). Driver may override the suggested fare upward,
   capped at +30%.
2. **Passenger search/match** — AI service scores candidate rides by
   route overlap, pickup/dropoff detour, and departure-time compatibility;
   results are ranked, not just filtered.
3. **Booking** — passenger books N seats (or adds seats to an existing
   booking); driver confirms or rejects; cancellation flows exist for
   both sides with reason capture.
4. **In-ride** — driver shares live GPS location (`POST/GET
   /rides/{id}/location`); the current position is also appended to a
   30-day location-history trail (`driver_location_history`) for
   route-overlap-pooling analysis and real-vs-planned comparisons.
5. **Completion** — ride marked complete; passenger rating/loyalty
   accrual triggered.

## Groups & Recurring Rides

- **Groups**: open-membership carpooling groups (join freely) plus
  **sponsored groups** gated by org-domain OTP.
- **Recurring rides**: drivers define a weekly recurrence pattern;
  passengers can pick several upcoming week-instances from one ride's
  detail page (each still booked individually).

## Loyalty & Financials

- **Payments are cash-only** (MVP decision) — no in-app payment processing.
- **Loyalty points**: passengers earn points equal to ~25% of the
  platform commission on a ride ("cash back"), redeemable as a discount
  on future bookings. Thin-margin redemption rides are an intentional
  tradeoff, not a bug.
- **Car maintenance savings**: a 0.3 EGP/km distance fee (100% platform
  revenue) accumulates per driver toward 3,000 EGP of free car
  maintenance.
- **Featured rides**: a promoted-listing surface on the passenger search/home view.

## Trust, Moderation & Fraud Signals

- Ratings, reports, and an admin moderation workflow (warn / suspend /
  reinstate) exist with a rating-floor threshold and report-count
  threshold.
- **Fraud signal capture (newest, just merged)**: every signup, login,
  ride-post, and booking now fires a non-blocking background event
  recording `event_type`, `user_id`, `device_id` (client header), and
  `ip_address`. This is **instrumentation only** — it feeds a future
  fraud-detection model; there is no live fraud-decisioning or blocking
  behavior yet. Contrary to older docs, device/IP capture now exists.

## Admin Operations

- Admin app covers: rides list/detail visibility, user/driver
  management, org-email verification review, financial reporting
  (net commission after distance-fee passthrough and points-discount
  reimbursement), and moderation actions.

## AI / ML

- Match-score and ride-ranking models (XGBoost, scikit-learn) with an
  exploration-rate ranking config.
- A continuous learning pipeline: real-outcome dataset generation,
  production retraining, shadow deployment, model monitoring/drift
  detection.

## Localization

- Full English + Arabic (RTL) support across the main app.

## Known Local-Dev-Only Gaps (not product behavior)

- **OSRM is not configured in local dev.** `POST /api/v1/rides` will
  reliably 503 locally regardless of code correctness — this is an
  environment gap, not a regression, when testing ride creation.
- FCM push notifications are skipped locally (no service-account
  secret configured) — push-dependent flows won't send real
  notifications in this environment.

## What NOT to trust from other repo docs

`docs/implementation-roadmap.md` predates several of the above and is
known-stale in places: it still lists auth as "Phone OTP" only, marks
"fraud-detection" as not started, and claims no device/IP signal is
captured anywhere — all superseded by what's described in this document.
