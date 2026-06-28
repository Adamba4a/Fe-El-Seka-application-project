# Frontend Page Contracts: Real-Time Transportation

**Feature**: `010-realtime-transportation` | **Date**: 2026-06-28

---

## New Pages

### `/(passenger)/rides/[id]/tracking/page.tsx`

**Route**: `/(passenger)/rides/[id]/tracking`

**Purpose**: Live driver location tracking screen, accessible to a confirmed passenger after the ride transitions to `in_progress`. Shows a Leaflet map with the driver's current position updating in real time.

**Entry conditions**:
- User must be authenticated (middleware enforces this).
- User must have a `confirmed` booking on ride `[id]`.
- Ride must be in `in_progress` status. If the ride is `completed` or `cancelled`, the page redirects to `/(passenger)/bookings/{booking_id}`.

**Data loading**:
1. On mount, call `GET /api/v1/rides/{id}/location` to load the last known position.
2. Subscribe to Supabase Realtime `postgres_changes` on `driver_locations` table, `filter: ride_id=eq.{id}`.
3. On each Realtime UPDATE event, call `GET /api/v1/rides/{id}/location` to refresh (or use the payload directly if lat/lng are available).
4. Subscribe to Supabase Realtime `postgres_changes` on `bookings` table to detect the ride completing — when the booking's `status` changes to `completed`, trigger the auto-redirect flow.

**UI components**:
- `LiveTrackingMap` — Leaflet map centered on driver's current position; directional driver pin (rotated by `bearing` when non-null); standard pin when `bearing` is null.
- `TrackingStatusBanner` — displays above the map:
  - Normal: driver info (name from booking), departure time.
  - Stale (>60 s since last update): "Driver location may be outdated" warning strip.
  - Completed: "Ride Completed" message with 3-second countdown, then auto-redirects to `/(passenger)/bookings/{booking_id}`.
- Loading skeleton while initial location is fetched.
- Error state with "Location unavailable" if the GET endpoint returns 404 (driver hasn't reported yet).

**Realtime cleanup**: Both channel subscriptions must be removed (`supabase.removeChannel()`) in the `useEffect` cleanup function.

**Deep link target**: This page is the target of `ride_started` FCM notifications via `/(passenger)/rides/{ride_id}/tracking`.

---

## Extended Pages (Realtime Subscriptions Added)

### `/(passenger)/bookings/page.tsx` — My Bookings List

**Change**: Add `useBookingStatus` hook subscription to the `bookings` table filtered by `passenger_id = auth.uid()`. On any `UPDATE` event for a booking in the visible list, update the corresponding item's `status` badge in place without a full page reload (SC-003 target: within 3 seconds).

**Hook**: `useBookingStatus(passengerId: string)` — returns a `lastEvent` object; the page updates the local bookings array state when a matching booking ID is found.

---

### `/(passenger)/bookings/[id]/page.tsx` — Booking Detail

**Change**: Add `useBookingStatus` hook subscription filtered by `booking_id = [id]`. On a `confirmed` or `cancelled` event, update the status badge and show/hide the cancel button accordingly. No page reload required.

---

### `/(driver)/rides/[id]/bookings/page.tsx` — Driver Booking Queue

**Change**: Add a Supabase Realtime INSERT subscription on the `bookings` table filtered by `ride_id = [id]`. When a new `pending` booking INSERT event arrives, append the new booking card to the list in real time (SC-003: within 3 seconds, no page reload).

---

## New Hooks

### `useDriverLocation(rideId: string)`

**File**: `apps/main/src/lib/hooks/useDriverLocation.ts`

**Signature**:
```typescript
function useDriverLocation(rideId: string): {
  location: { lat: number; lng: number; bearing: number | null; updatedAt: string } | null;
  isStale: boolean;
  error: string | null;
}
```

Subscribes to `postgres_changes` UPDATE on `driver_locations` filtered by `ride_id`. On each event, calls `GET /api/v1/rides/{rideId}/location` to get fresh data (since the raw Realtime payload does not expose lat/lng from PostGIS geometry). Sets `isStale = true` when `Date.now() - new Date(updatedAt).getTime() > 60_000`.

---

### `useBookingStatus(filter: { passengerId?: string; bookingId?: string; rideId?: string })`

**File**: `apps/main/src/lib/hooks/useBookingStatus.ts`

**Signature**:
```typescript
function useBookingStatus(filter: {
  passengerId?: string;
  bookingId?: string;
  rideId?: string;
}): {
  lastEvent: RealtimePostgresChangesPayload<BookingRow> | null;
}
```

Subscribes to `postgres_changes` (INSERT and UPDATE) on the `bookings` table with the appropriate `filter` string. Callers decide what to do with `lastEvent`. Cleans up channel on unmount.

---

## New API Client Functions

### `apps/main/src/lib/api/location.ts`

```typescript
// POST /api/v1/rides/{rideId}/location
export async function reportLocation(
  token: string,
  rideId: string,
  data: { lat: number; lng: number; bearing?: number | null; speed_kmh?: number | null; client_timestamp: string }
): Promise<{ location_id: string; ride_id: string; updated_at: string }>

// GET /api/v1/rides/{rideId}/location
export async function getDriverLocation(
  token: string,
  rideId: string
): Promise<{ ride_id: string; lat: number; lng: number; bearing: number | null; client_timestamp: string; updated_at: string } | null>
```

### `apps/main/src/lib/api/device-tokens.ts`

```typescript
// POST /api/v1/users/me/device-tokens
export async function registerDeviceToken(
  token: string,
  data: { token: string; platform: 'web' | 'android' | 'ios' }
): Promise<{ token_id: string; user_id: string; platform: string; last_seen_at: string }>
```
