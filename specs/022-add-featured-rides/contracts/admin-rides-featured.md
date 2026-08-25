# Contract: Admin Featured-Ride Mutations

Extends the existing admin Rides API (`services/api/app/api/admin/rides_router.py`), which currently exposes only `GET /` and `GET /{ride_id}`. All endpoints below require `Depends(get_current_admin)`, matching existing handlers in this router.

## `POST /api/admin/rides/{ride_id}/feature`

Marks an eligible ride as Featured (FR-001).

**Path params**: `ride_id: uuid`

**Success — 200**:
```json
{
  "ride_id": "uuid",
  "is_featured": true,
  "featured_at": "2026-08-25T12:00:00Z",
  "featured_by": "uuid"
}
```

**Errors** (matching this router's existing `{"error": ..., "message": ...}` shape):
- `404 not_found` — ride does not exist.
- `409 not_eligible` — ride fails the FR-003 eligibility check. `message` names the specific reason, e.g. `"Ride is not eligible: status must be scheduled"`, `"Ride is not eligible: departure has already passed"`, `"Ride is not eligible: no seats available"`.

**Side effects**: sets `rides.is_featured = true`, `rides.featured_at = now()`, `rides.featured_by = <admin id>`; appends one `admin_audit_logs` row with `action_type = "ride_featured"`, `ride_id`, `target_user_id = rides.driver_id` (per data-model.md).

## `POST /api/admin/rides/{ride_id}/unfeature`

Removes the Featured designation (FR-002). No eligibility check — allowed regardless of the ride's current status.

**Path params**: `ride_id: uuid`

**Success — 200**:
```json
{
  "ride_id": "uuid",
  "is_featured": false,
  "featured_at": "2026-08-25T12:00:00Z",
  "featured_by": "uuid"
}
```
(`featured_at`/`featured_by` remain as the last-set values — last-action metadata, not cleared — per data-model.md.)

**Errors**:
- `404 not_found` — ride does not exist.

**Side effects**: sets `rides.is_featured = false` (leaves `featured_at`/`featured_by` as the last action, then overwrites both to this unfeature action per decision in data-model.md); appends one `admin_audit_logs` row with `action_type = "ride_unfeatured"`.

## Existing endpoints, extended response fields

`GET /api/admin/rides/` (list) and `GET /api/admin/rides/{ride_id}` (detail) each add three fields to their existing ride object, sourced directly from the new columns:

```json
{
  "is_featured": false,
  "featured_at": null,
  "featured_by_display_name": null
}
```

`featured_by_display_name` is resolved via a join to `profiles` (same pattern already used for `driver_display_name` in this router), so the admin UI can show "Featured by <admin>" without a second request.
