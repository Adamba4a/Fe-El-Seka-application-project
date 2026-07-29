# Quickstart: Trust & Community

Validation guide for the ratings / reporting / moderation feature, once implemented per
`tasks.md`. Assumes the local dev stack from prior phases (`services/api`, Supabase local, `apps/main`,
`apps/admin`) is already running per repo-root setup docs.

## Prerequisites

- Supabase migration `<timestamp>_phase10_trust_community.sql` applied locally.
- Two test accounts with a `completed` booking between them (one passenger, one driver) — reuse the
  existing booking-lifecycle test fixtures from `009-passenger-experience`/`010-realtime-transportation`.
- One admin account (`profiles.role = 'admin'`).

## Scenario 1 — Mutual rating, double-blind reveal (US1, FR-001–FR-011)

1. As the passenger, `POST /ratings` with `{ booking_id, stars: 5, comment: "Great ride" }` → expect
   `201` with `revealed: false`.
2. As the passenger, `GET /profiles/{driver_id}/rating` → the just-submitted rating's comment MUST
   NOT appear yet (driver hasn't rated back, <14 days elapsed).
3. As the driver, `POST /ratings` for the same `booking_id` → expect `201`.
4. As either party, `GET /profiles/{other_id}/rating` → both comments now appear (both parties rated
   — reveal condition (a) met).
5. Repeat step 1 for a fresh booking, then attempt a second `POST /ratings` for the same
   `booking_id` as the same rater → expect `409 conflict` (FR-005), original rating unchanged.
6. Attempt `POST /ratings` for a `pending`/`confirmed`/`cancelled` booking → expect `409 conflict`
   (FR-003).
7. Attempt `POST /ratings` as a user who was not a party to the booking → expect `403
   authorization_error` (FR-004).

## Scenario 2 — Report a safety concern (US2, FR-012–FR-017)

1. As the passenger, `POST /reports` with a valid `category` and `description` against the ride's
   driver → expect `201`, `status: "open"`.
2. `GET /reports/mine` as the reporter → the new report appears with `status: "open"` only (no
   resolution fields).
3. Attempt `POST /reports` naming yourself as `reported_user_id` → expect `403 authorization_error`
   (FR-013).
4. Attempt `POST /reports` with an empty `description` → expect `400 validation_error` (FR-014).
5. Attempt `POST /reports` against a ride still `in_progress` → expect `201` (reporting is not gated
   on completion, FR-015).
6. Confirm the reported user's own booking/ride-creation ability is unaffected immediately after
   step 1 (FR-017 soft-flag-only behavior).

## Scenario 3 — Admin moderation queue and actions (US3, FR-018–FR-026)

1. As the admin, `GET /admin/moderation/queue` → the report from Scenario 2 appears, newest-first.
2. As the admin, `GET /admin/moderation/flagged` → confirm a user crossing the seeded
   `moderation_config` thresholds (rating < 3.0 over last 10 with ≥5 ratings, or ≥3 reports/30 days)
   appears, without any change to their `verification_status` (FR-019 is advisory-only).
3. As the admin, `POST /admin/moderation/reports/{id}/resolve` with `{ action: "suspend", reason:
   "..." }` → expect `200`; confirm the target's `profiles.verification_status` is now `suspended`,
   an `admin_audit_logs` row exists with `action_type = 'suspended'` and `report_id` set (FR-023),
   and the target cannot create a new ride/booking (FR-024).
4. As the admin, `POST /admin/moderation/users/{id}/reinstate` with a reason → expect `200`; confirm
   `verification_status` returns to `verified` and the user can create rides/bookings again.
5. As a non-admin, attempt any `/admin/moderation/*` endpoint → expect `403 authorization_error`
   (FR-026).
6. Confirm the affected user received a `notification_events` row for both the suspend and reinstate
   actions, and that the notification payload does not include the reporter's identity (FR-025).

## Expected outcome

All steps above pass without manual database intervention between steps — each state transition
(booking → rating, report → resolved, profile → suspended → verified) is driven entirely through the
endpoints in `contracts/api.md`, matching the acceptance scenarios in `spec.md`.
