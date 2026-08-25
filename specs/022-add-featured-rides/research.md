# Phase 0 Research: Featured Rides

The spec's Technical Context left no `NEEDS CLARIFICATION` markers — the tech stack is fixed by the Constitution and the existing monorepo. This research resolves *design/pattern* decisions by grounding them in how equivalent things are already done in this codebase, rather than introducing new patterns.

## 1. Where does the "Featured" designation live?

**Decision**: Extend the existing `rides` table directly with `is_featured boolean not null default false`, `featured_at timestamptz`, `featured_by uuid references profiles(id)`.

**Rationale**: This is a 1:1 designation on a ride (a ride either is or isn't currently Featured — confirmed in Clarifications: no separate expiry/duration, no history of past featured periods required). `supabase/migrations/` already extends the `rides` table incrementally this way for similar single-ride attributes (e.g. `route_geometry`, `fuel_cost_egp`, `platform_commission_egp`). A join to a separate `featured_rides` table would add query cost to the hot-path listing endpoint for no modeling benefit here.

**Alternatives considered**: A separate `featured_rides` table keyed by `ride_id` — rejected as unnecessary indirection; nothing in the spec requires tracking multiple past featuring "periods" per ride, only the current state plus last-action metadata.

## 2. How is the feature/unfeature action audited?

**Decision**: Reuse the existing `admin_audit_logs` mechanism (`services/api/app/services/audit_service.py::append_log`), extended with a nullable `ride_id` column, logging `action_type = "ride_featured"` / `"ride_unfeatured"` with `target_user_id` set to the ride's driver. The ride's own `featured_at`/`featured_by` columns (decision 1) remain the fast-path source for "is this currently featured, since when."

**Rationale**: The Constitution's Auditability requirement names "ride operations" and "administrative actions" as needing the same traceable mechanism already used for verification and moderation decisions (`verification_router.py`, `moderation_service.py` both call `append_log`). Extending that one audit log keeps a single centralized admin action trail instead of a second, parallel one — directly satisfying FR-006 without inventing new audit infrastructure.

**Alternatives considered**:
- Ride-columns-only, no audit log entry — rejected: bypasses the centralized admin action trail that every other admin action in this codebase already writes to, and Auditability is a Constitutional MUST, not a nice-to-have.
- Audit-log-only, no ride columns — rejected: would require a log lookup per ride to answer "is this ride featured" on every admin/passenger listing render, which cannot meet the 500ms p95 target (NFR-001) at any real scale.

## 3. Where do the admin mutation endpoints live?

**Decision**: Add `POST /api/admin/rides/{ride_id}/feature` and `POST /api/admin/rides/{ride_id}/unfeature` directly to the existing `services/api/app/api/admin/rides_router.py`, using the same raw-`asyncpg`-via-`get_pool()` query style already used by that router's `list_rides` and detail handlers — no new service module.

**Rationale**: `rides_router.py` today has no accompanying `admin_ride_service.py`; its handlers query the pool directly. Introducing a service layer for two small, single-table mutations would be an abstraction the codebase's own admin-rides code doesn't otherwise use here. Two explicit action endpoints (rather than one generic `PATCH` toggling a body field) mirror the existing explicit-action style used elsewhere for admin/driver mutations (e.g. booking confirm/reject), and let each endpoint carry its own eligibility check (FR-003) and its own `action_type` for the audit log without a branch.

**Alternatives considered**: Single `PATCH /rides/{ride_id}` accepting `{"is_featured": true|false}` — rejected in favor of the two-endpoint action style for consistency with the rest of the admin API surface and clearer audit semantics.

## 4. Where does the passenger-facing read endpoint live?

**Decision**: Add `GET /api/v1/rides/featured` to the existing public `services/api/app/api/rides/router.py`, backed by a new `list_featured_rides()` function alongside `list_rides()`/`get_ride()` in `services/api/app/services/ride_service.py`. The query filters `is_featured = true AND status = 'scheduled' AND departure_datetime > now() AND available_seats > 0`, ordered by `departure_datetime ASC` (per the Assumptions: soonest-departure ordering, no manual admin ordering).

**Rationale**: Keeps Featured reads inside the same ride-domain module as other ride reads instead of a new parallel service. Critically, it stays structurally outside `services/api/app/api/search/router.py` (the AI-ranked matching path) — this makes FR-013's "Featured must not influence route-matching/ranking" a structural fact (different endpoint, different code path, different query), not just a documented convention that could later be violated by a well-meaning refactor.

**Alternatives considered**: Folding Featured rides into `/api/v1/search/nearby` (which already exists) — rejected because that endpoint is proximity/AI-ranking-driven; mixing a manually curated list into it would blur exactly the separation FR-013 requires and risk the curated list being reshuffled by ranking logic.

## 5. How fresh does the frontend keep the Featured list?

**Decision**: `apps/main`'s landing page fetches `GET /rides/featured` once per page mount/navigation. No polling interval, no Supabase realtime subscription.

**Rationale**: Directly implements the Clarifications answer (2026-08-25): fetch-on-load only, because the existing booking screen already re-validates seat availability before confirming a booking, so a stale card cannot lead to an invalid booking — it can at worst show a ride that's since filled, which the user discovers on tap-through.

**Alternatives considered**: Periodic polling (rejected, adds complexity for a low-churn curated list) and realtime push (rejected, same reason — explicitly ruled out in Clarifications).

## 6. What UI pattern does the redesigned landing page follow?

**Decision**: Structure the new `(passenger)/search/page.tsx` landing view as a simple list section (`FeaturedRidesSection`, reusing the existing `RideCard` component) plus a prominent "Find a Ride" call-to-action button, modeled directly on the visual/interaction pattern of `(driver)/rides/new/page.tsx`. Tapping "Find a Ride" mounts the existing `RideSearchForm` + `RideMap` + `BottomSheet` combination completely unchanged — only its entry point moves from "always visible on page load" to "opened on demand."

**Rationale**: This was an explicit product requirement ("nearly like the driver's post-a-ride page"), and leaving the working map-search code path untouched minimizes regression risk to a flow that already functions correctly today.

**Alternatives considered**: None — this is a stated requirement, not an open design choice; the only real alternative (redesigning the map-search mechanics too) is explicitly out of scope per the spec's Out-of-Scope section.

---

**Output**: All design unknowns resolved; no `NEEDS CLARIFICATION` markers remain. Proceeding to Phase 1 (data-model.md, contracts/, quickstart.md).
