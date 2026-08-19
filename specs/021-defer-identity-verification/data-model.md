# Phase 1 Data Model: Deferred Identity Verification (Progressive KYC)

## Entity: User Profile (`profiles` table — existing, extended)

| Field | Type | Change | Notes |
|---|---|---|---|
| `id` | UUID (PK) | unchanged | — |
| `email` | text | unchanged | — |
| `phone_number` | text, nullable | unchanged (behavior only) | Column already exists. New accounts still collect it at signup (per FR-001, phone remains required at signup — only ID number and photo were dropped). Pre-existing accounts missing it are grandfathered per FR-016 (no migration/backfill). |
| `display_name` | text, `CHECK` 2–50 chars | unchanged | — |
| `role` | text, `CHECK IN (passenger, driver, admin)` | unchanged | — |
| `date_of_birth` | **DATE, nullable** | **NEW** | Collected at signup for new accounts only; required by the signup service-layer validator (minimum-age check) but nullable at the DB layer because pre-existing accounts (FR-017) are permanently exempt and will never have a value. Never exposed via `PublicProfileResponse`. Age is computed on demand from this value — never stored as a static integer. |
| `profile_photo_path` | text, nullable | unchanged | Already nullable/optional; this feature makes it optional in the *signup form* too (it was previously required at signup, now fully deferred like documents — same as spec's document flow). |
| `verification_status` | text, `CHECK IN (unverified, pending_review, verified, rejected, suspended)`, default `unverified` | unchanged | Existing enum reused as-is; this feature does not add a new status value — "browsing while unverified" is a UI/routing behavior change, not a new state. |
| `is_submission_locked` | boolean, default false | unchanged | Existing anti-abuse lock on repeated failed submissions, reused as-is. |
| `created_at`, `last_login_at` | timestamptz | unchanged | — |

**Validation rules (new/changed)**:
- `date_of_birth`, when present, MUST represent an age ≥ the platform's minimum-age threshold at the moment of signup (enforced once, server-side, in `profile_service.py`; see research.md Decision 1). Not re-validated after signup — no periodic recheck.
- `phone_number` retains its existing `^\+2\d{11}$` format validator (`ProfileUpdate` in `models/profile.py`) — unchanged, still required at signup, just no longer gates *post-signup* app access.
- `profile_photo_path` has no new validation — the existing upload endpoint/validators (`_ALLOWED_PHOTO_TYPES`, `_MAX_PHOTO_BYTES`) are unchanged; only the signup-time *requiredness* is removed.

**State transitions**: No change to the `verification_status` state machine (`unverified → pending_review → verified | rejected`, `rejected → pending_review` on resubmit, any → `suspended`). What changes is *when the user is permitted to be in each state while using the app* — previously `unverified`/`pending_review`/`rejected` all blocked nearly all app access; now they block only the three gated actions (see below).

## Entity: Verification Submission (existing — unchanged)

No schema or lifecycle changes. The only change is *reachability*: the submission form (`verify-id`/`driver/verify-documents`) is now linked from the persistent "Verify identity" affordance and from the 403 `verification_required` prompt, in addition to the existing forced-redirect-on-`rejected` path. The review pipeline, turnaround SLA (5 min–2 hr), and decision-notification mechanism (push/email) are all reused unmodified.

## Conceptual Entity: Gated Action (not persisted — a runtime check)

Represents the enforcement point applied at exactly three call sites, all pre-existing backend dependency guards with no code change required:

| Gated action | Endpoint | Guard (already present) |
|---|---|---|
| Passenger creates a booking | `POST /api/bookings` | `get_current_verified_passenger` |
| Driver creates a ride | `POST /api/rides` | `get_current_verified_driver` |
| Driver confirms/rejects a booking | `POST /api/rides/{ride_id}/bookings/{booking_id}/confirm` and `.../reject` | `get_current_verified_driver` |

Each guard raises `HTTPException(403, {"error": "verification_required", "message": "..."})` when `verification_status != "verified"`. This plan does not add or move any guard — it removes the *frontend* blanket gates that previously made these backend guards unreachable in the unverified state (a user could never get far enough in the UI to trigger them), and adds frontend handling that turns the existing 403 into a helpful prompt (see research.md Decision 4) rather than a raw error.
