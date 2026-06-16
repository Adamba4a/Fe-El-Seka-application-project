# Research: Ride Management

**Branch**: `004-ride-management` | **Date**: 2026-06-17

---

## 1. Map Provider — Interactive Pin Drop + Reverse Geocoding

**Decision**: Leaflet.js + OpenStreetMap tiles + Nominatim reverse geocoding

**Rationale**: Leaflet is the standard open-source map library for Next.js. OpenStreetMap tiles and Nominatim are free, require no API key for modest MVP usage, and align with the OSRM stack the platform already adopts for Phase 5 routing (both OSRM and Nominatim are OSM-ecosystem tools). Using one ecosystem for all geo tooling reduces integration surface. For production at scale, Nominatim can be self-hosted or proxied through a managed OSM service.

**Alternatives considered**:
- Mapbox GL JS: Better visual quality and UX, but requires a paid API key at volume and introduces a proprietary dependency not aligned with the OSM-first stack.
- Google Maps: Most familiar UX, but expensive at scale and locks the platform to a commercial provider.
- react-leaflet: Wraps Leaflet for React; use as the Next.js integration layer over raw Leaflet to keep component API consistent with the React model.

**Integration pattern**: Driver picks origin and destination via two sequential pin drops on a `react-leaflet` `MapContainer`. On each pin placement, a `GET https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json` call fetches the address label. Coordinates are stored; address label is displayed to the driver for confirmation. No forward geocoding (address → coordinates) is needed in this phase.

**Rate limit note**: Nominatim's public instance enforces 1 req/s per IP. For MVP (low volume), this is fine. A self-hosted or Supabase Edge Function proxy should be added before production load.

---

## 2. Email Delivery + Retry Mechanism

**Decision**: Resend (transactional email SaaS) + Supabase `email_notifications` queue table + FastAPI BackgroundTasks for retry

**Rationale**: Resend offers a generous free tier, a simple REST API, and React Email template support. FastAPI `BackgroundTasks` is sufficient for immediate enqueuing at MVP scale without introducing Celery/Redis complexity. A lightweight `email_notifications` table in Supabase persists pending/failed emails so that a background sweep (daily cron or next API call) can retry without losing state. Email delivery is best-effort (per FR-021 clarification); the table records retry count and last attempt timestamp.

**Alternatives considered**:
- SendGrid: More established, similar API surface, slightly higher free-tier restrictions.
- Celery + Redis: Robust distributed task queue, but overkill for MVP email volumes (tens of emails per day at most in this phase).
- Supabase Edge Functions (Deno): Would allow triggers directly from DB events, but adds Deno/TypeScript runtime to the backend stack, fragmenting business logic across FastAPI and Edge Functions.

**Retry strategy**: Exponential backoff — attempt at T+0, T+5m, T+30m, T+2h, T+24h. After 5 failures the record is marked `failed_permanent` and no further retries occur. All retry logic runs in a FastAPI startup background loop (simple `asyncio.create_task` on app startup calling a sweep every 5 minutes).

---

## 3. PostGIS Column Type for Origin/Destination

**Decision**: `geography(Point, 4326)` (WGS84 spherical) for both `origin_coordinates` and `destination_coordinates`

**Rationale**: The `geography` type correctly handles distance calculations on a spherical Earth — essential for Egypt's ~1,100 km North-South extent where planar geometry introduces significant error. Phase 5 will add spatial queries (bounding box overlap, proximity filtering) that benefit from GIST indexes on `geography` columns. Using `geography` now avoids a destructive column type migration later. SRID 4326 is the standard for GPS coordinates (what Leaflet and Nominatim return).

**GIST index**: Create GIST indexes on both coordinate columns at migration time. Phase 5 will rely on these for `ST_DWithin` and `ST_Intersects` queries.

**Alternatives considered**:
- `geometry(Point, 4326)`: Planar, faster for very large datasets, but incorrect distance math for real-world geographic queries without manual SRID conversion.
- Storing lat/lng as two `numeric` columns: Simple but violates Constitution §Data Standards ("Geospatial data MUST use PostGIS geometry/geography types") and cannot use spatial indexes.

---

## 4. Concurrent Access — Overlap Check + Seat Counter Atomicity

**Decision**: PostgreSQL advisory locks for the 2-hour overlap check; row-level `SELECT FOR UPDATE` for `booked_seats` updates

**Rationale**:
- **Overlap check**: When a driver creates a ride, the system checks for existing rides within a 2-hour window. Two simultaneous creations by the same driver could both pass this check if read concurrently. Acquiring a per-driver advisory lock (`pg_advisory_xact_lock(driver_id)`) serializes creation for the same driver, making the check reliable without a complex unique constraint.
- **Booked seats**: When Phase 6's booking system increments/decrements `booked_seats`, `SELECT FOR UPDATE` on the Ride row ensures the counter is never double-modified under concurrent bookings. Phase 4 initializes this pattern; Phase 6 uses it.

**Alternatives considered**:
- Application-level locks (Redis): More complex, introduces a new dependency; PostgreSQL advisory locks are sufficient at MVP scale.
- `booked_seats` as a derived aggregate (COUNT of bookings): Correct but requires a JOIN on every read, and makes the `available_seats` generated column impossible. Stored counter is the right tradeoff (per clarification session Q1).

---

## 5. Verification Revocation → Auto-Cancellation Propagation

**Decision**: Supabase Database Webhook on `users.verification_status` + `vehicles.active` changes → POST to FastAPI internal endpoint

**Rationale**: Supabase supports row-level Database Webhooks that fire on `UPDATE` events. A webhook on the `users` table (filter: `verification_status` changed to `suspended`) and on the `vehicles` table (filter: `active` changed to `false`) POSTs to a protected FastAPI endpoint (`/api/v1/internal/driver-revocation`). The endpoint runs a single transaction: fetch all `scheduled` rides for the affected driver → set each to `cancelled` (reason: system-generated) → insert `RideHistoryLog` entries → enqueue `email_notifications` rows. This satisfies SC-007 (auto-cancel within 1 minute of revocation) without polling.

**Security**: The webhook includes a shared secret header (`X-Webhook-Secret`) validated by FastAPI using a Supabase Vault-stored value.

**Alternatives considered**:
- Poll on every driver action (lazy revocation): Does not satisfy SC-007's 1-minute SLA; a revoked driver's existing scheduled rides would remain visible to passengers indefinitely.
- Supabase Database Trigger (PL/pgSQL): Could directly update ride rows in the DB, but violates Constitution §Architecture Standards ("Backend services MUST own business logic") — business logic must live in FastAPI, not the database.
- Supabase Realtime subscription in FastAPI: Maintains a long-lived WebSocket connection from FastAPI to Supabase Realtime; fragile for server-side use and requires connection management overhead.
