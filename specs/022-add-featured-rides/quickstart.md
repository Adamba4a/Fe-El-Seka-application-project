# Quickstart: Validating Featured Rides

Prerequisites: local Supabase stack running, `services/api` running locally, `apps/main` and `apps/admin` running locally (`pnpm dev` per app, or the monorepo's existing dev workflow), a seeded driver with at least one `scheduled` future ride that has open seats, and an admin account with access to `apps/admin`.

## 1. Apply the migration

Run the new migration (`supabase/migrations/<timestamp>_add_featured_rides.sql`) against your local Supabase instance the same way prior migrations in this repo are applied. Confirm `rides.is_featured`, `rides.featured_at`, `rides.featured_by`, and `admin_audit_logs.ride_id` exist afterward.

## 2. Admin: feature a ride (User Story 2)

1. Open `apps/admin` → Rides → pick a `scheduled` ride with a future departure and open seats.
2. Toggle it Featured. Confirm the UI reflects the new state without a page reload.
3. Confirm in the database (or via `GET /api/admin/rides/{ride_id}`) that `is_featured = true`, `featured_at` is set, `featured_by` is your admin id, and a new `admin_audit_logs` row exists with `action_type = "ride_featured"` and the correct `ride_id`.
4. Attempt to feature a `cancelled` or fully booked ride — confirm the request is rejected with a `409 not_eligible` and a clear message (FR-003).

## 3. Passenger: see and open a Featured ride (User Story 1)

1. As a passenger, open the find-a-ride entry page in `apps/main` (`(passenger)/search`).
2. Confirm the page no longer opens directly into the full-screen map — it shows a landing view with a "Featured/Recommended Rides" section listing the ride from step 2 (route, departure time, price, seats).
3. Tap the Featured ride card. Confirm it opens that ride's existing detail/booking screen (unchanged from today).
4. In the admin panel, unfeature the same ride. Reload the passenger landing page and confirm the ride no longer appears (FR-002 → FR-012 fetch-on-load behavior).

## 4. Passenger: "Find a Ride" still works (User Story 3)

1. On the landing page, tap "Find a Ride."
2. Confirm the existing pin-drop origin/destination map search opens and behaves exactly as it does on `main` today (unchanged mechanics — this validates decision 6 in research.md, that the map-search code path was not touched).

## 5. Auto-drop edge case (FR-004)

1. Re-feature the ride from step 2.
2. Book all its remaining seats (or cancel it, or wait past its departure — whichever is fastest to simulate locally).
3. Reload the passenger landing page. Confirm the ride no longer appears in the Featured section, even though `is_featured` is still `true` in the database (per the Derived visibility rule in data-model.md) — no manual admin cleanup should be required.

## 6. Empty state (FR-011)

1. Unfeature all currently Featured rides.
2. Reload the passenger landing page. Confirm it still renders a usable empty state with the "Find a Ride" button clearly available (not a blank or broken page).

## Automated coverage (for `/speckit-tasks`)

- `services/api/tests/unit`: FR-003 eligibility rules, FR-004/FR-012 derived-visibility filter logic (`list_featured_rides`).
- `services/api/tests/integration`: `POST .../feature`, `POST .../unfeature` (success + `409`/`404` cases), `GET /rides/featured` (ordering, empty result, excludes ineligible rides), audit log row creation.
- Manual/browser verification for `apps/main` and `apps/admin` UI changes, per this repo's existing convention (no frontend unit-test runner configured).
