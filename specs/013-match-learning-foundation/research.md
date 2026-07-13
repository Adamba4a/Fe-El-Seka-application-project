# Phase 0 Research: Match Learning Foundation

## R1: How does a downstream booking action link back to its originating match-event?

**Decision**: Implicit correlation by lookup, not a client-supplied identifier.

When a booking-lifecycle transition occurs (`create_booking`, `confirm_booking`, `reject_booking`,
`cancel_booking`, `complete_ride_bookings` in `booking_service.py`), look up the most recent
`match_events` row for `(candidate_ride_id = ride_id, passenger_id = passenger_id)`:

```sql
SELECT id FROM match_events
WHERE candidate_ride_id = $1 AND passenger_id = $2
ORDER BY created_at DESC
LIMIT 1
```

If found, insert a linked `match_outcomes` row. If not found (e.g. a booking made without any prior
logged search — should not happen in normal flow but is not impossible), skip linking silently and
log at debug level; the booking operation itself MUST NOT fail or be delayed by this lookup.

**Rationale**: The spec (`Technical Considerations`) explicitly scopes this feature as backend-only
with no passenger/driver-facing UI changes. Passing an explicit `match_event_id` through the booking
creation request would require a frontend change (the client would need to capture and forward an ID
it currently discards), which is out of scope. A passenger requesting a specific ride shortly after
seeing it in search results is the dominant real-world case, so "most recent match-event for this
(passenger, ride) pair" is a reliable correlation key without any contract change.

**Alternatives considered**:
- Explicit `match_event_id` passed by the client at booking time — rejected: requires frontend change, violates backend-only scope.
- Correlate via `search_id` stored in a cookie/session — rejected: adds session-state complexity for no benefit over the ride/passenger lookup.

---

## R2: Exploration algorithm for ranking-exploration-strategy

**Decision**: Single-swap epsilon-greedy. After the existing 20%-threshold + minimum-3-guarantee
filter produces the final ranked candidate list, with probability `exploration_rate` (config,
default 0.125), pick one candidate uniformly at random from positions 2..N and promote it to
position 1, shifting the intervening candidates down by one. The promoted candidate's match-event
row is flagged `exploration_selected = true`; all others remain `false` (their relative order is
unchanged, so they were not "selected by exploration").

**Rationale**: Satisfies FR-007/FR-008/FR-009/FR-010 with the smallest possible mechanism — one
random draw and one list operation, easy to reason about, easy to audit (exactly one candidate per
exploring search is flagged), and trivially bounded (never touches candidates that failed feasibility
gating, since it only operates on the already-filtered `final_scored` list from `_ai_rank`).

**Alternatives considered**:
- Full Plackett-Luce softmax re-sampling of the entire order — rejected: harder to explain/audit, disproportionate to a ~10-15% exploration rate, and the spec's Constitution (Principle IV) requires AI-adjacent behavior to remain explainable.
- Random shuffle of the whole list on trigger — rejected: degrades perceived match quality far more than needed to collect counterfactual signal (SC-003 wants a barely-perceptible deviation for most users).

---

## R3: Fire-and-forget persistence mechanism (no external queue)

**Decision**: `asyncio.create_task(...)` fired from within the `search_rides` request handler,
immediately before the response is returned. The task acquires its own short-lived connection from
the existing `asyncpg` pool and performs the inserts; the request handler does not `await` it.

**Rationale**: Matches the Clarifications' best-effort/fire-and-forget delivery guarantee exactly —
no retry, no replay, a write failure is logged and accepted as lost. The codebase already uses
`asyncio.create_task` for long-running background loops (`booking_expiry_loop`,
`pricing_config_refresh_loop`, etc.) started at `lifespan` startup; using the same primitive for a
one-shot per-request task is a natural, dependency-free extension — no message queue or external
worker needs to be introduced for a v1 feature whose own success criteria tolerate loss.

**Alternatives considered**:
- A durable queue (e.g. a `pending_events` table drained by a worker loop) — rejected: this is an at-least-once delivery pattern, which contradicts the explicitly chosen best-effort guarantee (Clarifications) and adds operational surface for no required benefit at ~100 rides/day.
- `BackgroundTasks` (FastAPI's built-in) — functionally equivalent to `asyncio.create_task` here; `asyncio.create_task` was chosen only for consistency with the existing background-loop pattern already used elsewhere in `main.py`.

---

## R4: Exploration rate configuration storage

**Decision**: A new singleton `ranking_config` table (one row, admin-edited directly via the
Supabase dashboard), loaded into an in-process cache at startup and refreshed on a 30-second
background loop — the exact pattern already used for `pricing_config` / `pricing_service.py`.

**Rationale**: FR-010 and NFR-004 require the exploration rate to be adjustable without a code
deployment. The project already has a proven, working pattern for exactly this (singleton config
table + cache + refresh loop); reusing it is simpler than introducing a new configuration mechanism
(e.g. environment variables, which *do* require a deployment to change) and keeps operational
knowledge consistent across the two "tunable at runtime" config points in the system.

**Alternatives considered**:
- Environment variable — rejected: changing it requires a redeploy, violating FR-010 directly.
- Feature-flag service — rejected: no such service exists in the stack; would be new infrastructure for one number.

---

## R5: Outcome-recording durability (vs. match-event best-effort)

**Decision**: Match Outcome inserts (FR-003) are ordinary synchronous writes inside the same DB
transaction as the booking/ride status change they represent — not fire-and-forget.

**Rationale**: The Clarifications' best-effort guarantee was scoped specifically to match-event
persistence on the search path (where a 1-second AI timeout and zero added search latency are hard
constraints). Booking-lifecycle endpoints (`confirm_booking`, `reject_booking`, `cancel_booking`,
etc.) have no equivalent latency constraint and already perform their own synchronous audit-log
insert (`booking_audit_log`) inside the same transaction as the status change. Recording the match
outcome the same way is consistent with that existing pattern, and — unlike match-event volume,
which is O(candidates per search) — outcome volume is O(1) per lifecycle transition, so the
durability cost is negligible.

---

## R6: Data model shape

Confirmed against existing conventions (`bookings` + `booking_audit_log` two-table split,
`pricing_config` singleton): four new tables — `search_sessions`, `match_events`, `match_outcomes`,
`ranking_config` — all UUID-keyed, `asyncpg` raw SQL, no ORM. See `data-model.md`.
