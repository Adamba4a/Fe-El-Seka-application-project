# Implementation Plan: Real-Time Transportation

**Branch**: `main` | **Date**: 2026-06-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/010-realtime-transportation/spec.md`

## Summary

Phase 7 adds three tightly coupled real-time capabilities to the Fe El Seka platform: FCM push notifications dispatched by a new `asyncio` background loop reading from a dedicated `notification_events` table; ride lifecycle endpoints that were pre-built in `ride_service.py` but are missing `started_at`/`completed_at` column writes and notification event insertion; and live driver GPS broadcasting with a PostGIS-backed `driver_locations` table, a new location endpoint pair, and Supabase Realtime subscriptions for both booking status and driver position. Four new backend services are added — `fcm_service.py`, `notification_dispatcher.py`, `driver_reminder_service.py`, `location_service.py` — alongside a new passenger live tracking screen and Realtime subscription hooks in the existing booking screens.

## Technical Context

**Language/Version**: Python 3.11 (FastAPI backend), TypeScript / Node.js 20 (Next.js 14 frontend)

**Primary Dependencies**: FastAPI + asyncpg (raw SQL, no ORM), `firebase-admin` (FCM HTTP v1 API), `@supabase/supabase-js` (Realtime subscriptions), Leaflet (live map — already installed), Next.js 14 App Router

**Storage**: Supabase PostgreSQL + PostGIS — new tables: `notification_events`, `user_device_tokens`, `driver_locations`; `rides` table extended with `started_at` and `completed_at`

**Testing**: pytest + httpx (backend unit + integration); Playwright (frontend E2E)

**Target Platform**: Mobile-first web (Next.js 14, Tailwind CSS, shadcn/ui); Linux server (FastAPI via uvicorn)

**Project Type**: Monorepo — `apps/main` (combined passenger + driver role-based routing), `services/api` (FastAPI backend)

**Performance Goals**: Location POST endpoint p95 < 200ms; Realtime event propagation < 3 s end-to-end; FCM dispatch within 30 s of notification_event creation (dispatcher runs every 30 s)

**Constraints**:
- `notification_events.event_type` is a new PostgreSQL enum `notification_event_type`; the conceptual "extension from Phase 6" maps to a new dedicated FCM table, not to the existing `email_notifications` table (see `research.md` §2)
- `driver_locations` uses single-row upsert per ride (`INSERT ... ON CONFLICT (ride_id) DO UPDATE`)
- FCM dispatcher uses `SELECT ... FOR UPDATE SKIP LOCKED` — identical to the existing `notification_service.py` email retry loop
- `started_at` / `completed_at` added to `rides` via non-breaking migration; `ride_service.py` `start_ride()` and `complete_ride()` require corresponding SQL + `_RIDE_COLS` updates
- Supabase Realtime Authorization must be enabled in project settings before Realtime subscriptions can enforce RLS server-side
- FCM credentials (Firebase service account JSON) loaded from Supabase Vault at FastAPI startup; never written to disk or environment files

**Scale/Scope**: ≤1,000 concurrent users; up to 50 active rides with GPS tracking; up to 1,000 pending `notification_events` rows per dispatcher run

## Constitution Check

| Gate | Principle | Assessment |
|------|-----------|------------|
| ✅ | I — Driver-First Route Sharing | Ride lifecycle (start/complete) is a driver-initiated operation on an existing scheduled ride; no demand-side changes |
| ✅ | II — Route Intelligence Over Geographic Proximity | Live location uses raw GPS coordinates; no routing logic added; ETA computation is explicitly out of scope |
| ✅ | III — Trust Before Transportation | Location access enforced by confirmed booking membership at both API layer and Supabase RLS; Realtime Authorization enforces this at the channel layer |
| ✅ | IV — AI-Augmented Transportation | No AI logic in Phase 7; AI matchmaking remains Phase 9 |
| ✅ | V — Mobile-First UX | Live tracking screen follows existing mobile-first Leaflet + Tailwind patterns; driver pin orientation via nullable bearing |
| ✅ | VI — Modular Domain-Driven | Spec scoped to Real-Time Transportation only; booking cascade remains Phase 6 code; financial settlement remains Phase 8 |
| ✅ | VII — Shared Foundations | Monorepo structure unchanged; `apps/main` hosts both the passenger tracking screen and the driver lifecycle controls; no new apps introduced |

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/010-realtime-transportation/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   ├── api.md               # Phase 1 output — REST endpoint contracts
│   └── frontend-pages.md    # Phase 1 output — Next.js page contracts
└── tasks.md                 # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
# ── Backend ──────────────────────────────────────────────────────────────────
services/api/app/
├── api/
│   ├── rides/
│   │   └── router.py          # EXTEND — add POST /{id}/location, GET /{id}/location
│   └── users/
│       ├── __init__.py        # NEW
│       └── router.py          # NEW — POST /users/me/device-tokens
├── models/
│   ├── device_token.py        # NEW — Pydantic schemas for FCM token registration
│   └── location.py            # NEW — Pydantic schemas for location update + GET response
├── services/
│   ├── ride_service.py        # EXTEND — start_ride(): add started_at + notification_events inserts;
│   │                          #           complete_ride(): add completed_at + notification_events inserts;
│   │                          #           _RIDE_COLS must include started_at, completed_at
│   ├── booking_service.py     # EXTEND — create_booking(): add booking_received notification_event;
│   │                          #           confirm_booking(): add booking_confirmed notification_event;
│   │                          #           reject_booking(): add booking_rejected notification_event;
│   │                          #           cancel_booking(): add booking_cancelled notification_event;
│   │                          #           booking_expiry_loop(): add booking_expired notification_events
│   ├── location_service.py    # NEW — upsert driver_locations, read current position, ownership checks
│   ├── fcm_service.py         # NEW — firebase-admin wrapper: load credentials from Vault, send_multicast()
│   ├── notification_dispatcher.py  # NEW — asyncio loop (30 s): poll notification_events FOR UPDATE
│   │                               #        SKIP LOCKED, dispatch FCM, handle retry (max 3), mark status
│   └── driver_reminder_service.py  # NEW — asyncio loop (300 s): find pending bookings > 2 h old,
│                                   #        insert booking_received reminder notification_event atomically
└── main.py                    # EXTEND — register notification_dispatcher_loop and driver_reminder_loop
                               #           tasks in lifespan context manager

# ── Database ──────────────────────────────────────────────────────────────────
supabase/migrations/
├── 20260628000001_phase7_device_tokens.sql          # NEW — user_device_tokens table + RLS
├── 20260628000002_phase7_notification_events.sql    # NEW — notification_event_type enum,
│                                                    #        notification_events table + RLS
├── 20260628000003_phase7_driver_locations.sql       # NEW — driver_locations (PostGIS Point) + RLS
└── 20260628000004_phase7_rides_lifecycle.sql        # NEW — started_at, completed_at on rides;
                                                     #        Realtime publication additions for
                                                     #        bookings and driver_locations

# ── Frontend ──────────────────────────────────────────────────────────────────
apps/main/src/
├── app/
│   └── (passenger)/
│       └── rides/
│           └── [id]/
│               └── tracking/
│                   └── page.tsx       # NEW — live tracking screen (Leaflet + Realtime)
├── components/
│   └── tracking/
│       ├── LiveTrackingMap.tsx        # NEW — Leaflet map with movable driver pin + stale indicator
│       └── TrackingStatusBanner.tsx   # NEW — "Ride Completed" countdown + auto-redirect; stale warning
└── lib/
    ├── api/
    │   ├── location.ts                # NEW — POST/GET /rides/{id}/location API functions
    │   └── device-tokens.ts           # NEW — POST /users/me/device-tokens API function
    └── hooks/
        ├── useDriverLocation.ts       # NEW — Supabase Realtime subscription to driver_locations
        └── useBookingStatus.ts        # NEW — Supabase Realtime subscription to bookings table

# Existing files extended for Realtime subscriptions (no new files):
# apps/main/src/app/(passenger)/bookings/page.tsx      — add useBookingStatus hook
# apps/main/src/app/(passenger)/bookings/[id]/page.tsx — add useBookingStatus hook
# apps/main/src/app/(driver)/rides/[id]/bookings/page.tsx — add useBookingStatus hook (new bookings)
```

**Structure Decision**: Option 4 (Monorepo). No new applications or packages. The `(passenger)/rides/[id]/tracking/` route follows the existing nested App Router pattern under `(passenger)/`. A new `users/` API module is added alongside the existing `rides/`, `bookings/`, and `search/` modules.
