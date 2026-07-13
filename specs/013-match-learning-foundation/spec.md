# Feature Specification: Match Learning Foundation

**Feature Branch**: `013-match-learning-foundation`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "match-event-instrumentation and ranking-exploration-strategy: ship at/before public launch so real ride outcomes can be logged and learned from"

## Business Objective *(mandatory)*

Capture a complete, unbiased record of every ride candidate shown to a passenger and what happened to it, from the first day of public launch, so that future AI retraining on real usage data (Phase 13 items 046-049) has ground truth to learn from instead of only synthetic data. This data cannot be reconstructed retroactively — if it is not captured correctly from day one, the platform's entire "learn from real users" strategy has nothing to learn from.

**Constitutional Domain**: AI Integration / Route Intelligence

**Affected Applications**: Shared (`services/api`, `services/ai`) — backend-only; no passenger or driver-facing UI changes.

---

## Clarifications

### Session 2026-07-14

- Q: What delivery guarantee should match-event persistence provide relative to the search response? → A: Best-effort fire-and-forget — an async task writes after the response is built; a write failure is logged, not retried or replayed. Small risk of loss only on a mid-write crash.
- Q: Should Match Outcome be stored as a full transition history or a single current-status row? → A: Append-only event log — one row per transition, preserving the timestamp of every stage (requested, accepted, rejected, completed, cancelled, rated).
- Q: What starting exploration rate should ranking use? → A: ~10-15% of searches return an order that deviates from pure highest-score-first — enough to gather meaningful counterfactual signal at ~100 rides/day without degrading perceived match quality for most searches.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every shown candidate is logged with its full context (Priority: P1)

As the platform, when a passenger runs a search and is shown a list of AI-ranked ride candidates, every candidate in that response is recorded with the exact feature vector and score the AI used to rank it, so that a future retraining job can reconstruct "what the model believed at the time" for every match it ever surfaced.

**Why this priority**: This is the entire foundation of the real-data learning strategy. Without it, nothing downstream (outcome linking, exploration analysis, retraining) has anything to work with, and the gap can never be closed later.

**Independent Test**: Run a passenger search that returns candidates, then query the match-event store directly. Confirm one event row exists per candidate returned, each containing the feature vector, rank position, and predicted score that was actually shown to the passenger.

**Acceptance Scenarios**:

1. **Given** a passenger search returns 5 AI-ranked candidates, **When** the search response is sent, **Then** 5 match-event records are persisted, one per candidate, each with its feature vector, rank position, and predicted score.
2. **Given** the AI service is unavailable and the deterministic fallback (overlap_pct sort) is used, **When** the search response is sent, **Then** match-event records are still persisted for each candidate, tagged as fallback-derived rather than AI-scored.
3. **Given** a match-event has been logged for a candidate, **When** that candidate is later requested/booked, accepted, rejected, completed, cancelled, or (once ratings exist) rated, **Then** each of those state changes is linked back to the original match-event record.

---

### User Story 2 - Ranking occasionally surfaces non-top candidates to collect counterfactual data (Priority: P2)

As the platform, ranking does not always show passengers the purest highest-predicted-score ordering — it deliberately perturbs the order some of the time, so that borderline candidates the model is unsure about also get shown, booked, and their real outcome observed, rather than only ever confirming the model's existing beliefs.

**Why this priority**: Without this, every future retrain only ever sees outcomes for candidates the model already scored highly — it can never learn that a lower-scored candidate would actually have been accepted. This turns "learning from real users" into "confirming what launch already believed." It depends on User Story 1 being in place to be useful (exploration without logging produces nothing).

**Independent Test**: Run a large batch of searches with fixed inputs and observe the distribution of returned orderings. Confirm a measurable, non-zero fraction of responses deviate from the pure highest-score-first order, and that every candidate's match-event record indicates whether it was placed by exploration or by pure ranking.

**Acceptance Scenarios**:

1. **Given** a search returns multiple feasible candidates, **When** ranking is applied, **Then** some fraction of searches (per a configurable rate) return an order that is not strictly highest-score-first.
2. **Given** a candidate's position was changed by exploration, **When** its match-event is logged, **Then** the record indicates it was exploration-selected, distinct from candidates placed by pure predicted-score ordering.
3. **Given** a candidate failed deterministic feasibility gating (Phase 5, e.g. exceeds max detour), **When** exploration selects candidates to reorder, **Then** that candidate is never surfaced — exploration only reorders already-feasible candidates, it never bypasses feasibility.

---

### User Story 3 - Logging never degrades the search experience (Priority: P3)

As a passenger, my search results load with the same speed and reliability regardless of whether event logging succeeds, fails, or is slow.

**Why this priority**: Instrumentation that breaks or slows down the product it's instrumenting defeats its own purpose and risks being disabled under pressure — which would silently re-create the "never logged from day one" problem this feature exists to prevent.

**Independent Test**: Simulate the event-logging write path being slow or failing entirely. Confirm the search endpoint still returns within its existing performance target and still returns correct results.

**Acceptance Scenarios**:

1. **Given** the match-event store is temporarily unreachable, **When** a passenger runs a search, **Then** the search still returns ranked results within the existing performance target, and the logging failure is recorded for operational visibility rather than surfaced to the passenger.
2. **Given** normal operation, **When** a passenger runs a search, **Then** event persistence does not add measurable latency to the search response.

---

### Edge Cases

- What happens when the same ride is shown to the same passenger across two different searches (e.g. they re-run the search)? Each impression is logged as a separate match-event tied to its own search — candidates are not deduplicated across searches.
- What happens if a driver accepts/rejects a request that was logged under the deterministic fallback (no real AI score)? The outcome is still linked to its match-event; the fallback tag lets retraining exclude or weight these separately.
- What happens if exploration is enabled but only 1-2 feasible candidates exist for a search? Exploration has nothing meaningful to reorder and the existing minimum-3-guarantee / threshold-filter rules (012-ai-application) still apply unchanged.
- What happens to match-events for candidates never acted on (shown, never booked)? They remain logged as "shown-not-booked" — a valid, weaker training signal in the future outcome hierarchy (046), not an error state.
- What happens before 032-ratings-system ships? Rating outcomes are simply absent from linked records; the schema accommodates them without requiring a later migration.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST log one match-event record per ride candidate shown to a passenger in a search response, including the candidate's full feature vector, rank position, and predicted score.
- **FR-002**: System MUST tag every match-event from the same search response with a shared search identifier, so candidates and their outcomes can be grouped and analyzed per originating search.
- **FR-003**: System MUST record each downstream state change for a previously-shown candidate as its own outcome entry linked back to its match-event (append-only, not overwritten): requested/booked, driver accepted, driver rejected, ride completed, ride cancelled.
- **FR-004**: System MUST support linking a rating to its match-event once 032-ratings-system ships, without requiring a breaking change to this feature's stored schema.
- **FR-005**: System MUST NOT delay or block the search response while persisting match-event logs — persistence is a best-effort, fire-and-forget async write that happens after the response is built, not a retried or replayed operation.
- **FR-006**: System MUST log match-events even when the AI service is unavailable and the deterministic fallback ordering is used, tagged so fallback-derived rows are distinguishable from AI-scored rows.
- **FR-007**: Ranking MUST inject controlled randomization into candidate order shown to passengers, at a configurable rate, instead of always returning the pure highest-predicted-score order.
- **FR-008**: System MUST record, per candidate, whether its shown position resulted from exploration or from pure highest-score ranking.
- **FR-009**: Exploration MUST only reorder candidates that already passed deterministic feasibility gating (Phase 5) — it MUST NOT surface a candidate that failed feasibility.
- **FR-010**: The exploration rate MUST default to approximately 10-15% of searches receiving a non-pure-top-score order, and MUST be adjustable without a code deployment, so it can be tuned once real traffic volume is observed.
- **FR-011**: Exploration MUST preserve the existing minimum-3-results guarantee and 20%-match-score threshold filter behavior (012-ai-application) — it changes ordering/selection among eligible candidates, not the eligibility rules themselves.
- **FR-012**: Match-event and linked outcome data MUST be persisted in a queryable store suitable as direct input to the future real-outcome-dataset ETL (Phase 13 item 046), requiring no retroactive backfill.

### Key Entities *(include if feature involves data)*

- **Match Event**: One record per ride candidate shown to a passenger in a search response. Attributes: search identifier, passenger identifier, candidate ride identifier, feature vector snapshot, predicted score, rank position, exploration flag, AI-availability flag (AI-scored vs fallback), timestamp.
- **Match Outcome**: An append-only log of observed downstream results for a match event — one row per transition, not a single mutable status. Attributes: linked match-event identifier, transition type (requested, accepted, rejected, completed, cancelled, rated — rated absent until 032 ships), transition timestamp.
- **Search Session**: Groups all match events returned from one passenger search request. Attributes: search identifier, passenger identifier, timestamp, origin/destination.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under normal operation (no service crash mid-write), 100% of ride candidates returned in a passenger search response have a corresponding match-event persisted within seconds of the response being sent; occasional loss is tolerated only as a direct result of the best-effort delivery guarantee (see Clarifications).
- **SC-002**: Search response time is not measurably degraded by event logging, compared to the pre-instrumentation baseline.
- **SC-003**: Within the first week of real traffic, approximately 10-15% of searches show an exploration-perturbed order rather than pure top-score, confirmed via the exploration flag on real production data.
- **SC-004**: 100% of ride lifecycle transitions (requested, accepted, rejected, completed, cancelled) for a previously-shown candidate are linked back to their originating match-event, with zero orphaned outcome records.
- **SC-005**: A sample of logged match-events can be exported directly into the future outcome-dataset ETL format (046) without any retroactive backfill or schema change.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: Match-event logging MUST NOT add measurable synchronous latency to the search request path — persistence happens off the response-blocking path.
- **NFR-002**: A failure to persist match-event logs MUST NOT fail the search request; the failure MUST be recorded for operational visibility. Delivery is best-effort — a write failure (including one caused by a process crash mid-write) is logged and accepted as lost, not retried or replayed.
- **NFR-003**: The existing AI service 1-second call timeout and search performance goals (012-ai-application) MUST remain unchanged by this feature.
- **NFR-004**: Exploration randomization MUST be tunable per environment (e.g. disabled or reduced in automated tests) without code changes.

---

## Dependencies *(mandatory)*

- **Internal**: `012-ai-application` — the existing search/AI-ranking flow this feature instruments and extends. `008-route-intelligence` — the deterministic feasibility gate that exploration must never bypass. `032-ratings-system` (future) — rating outcomes link into this feature's schema once it ships; not a blocking dependency.
- **External**: None new.
- **Data**: New table(s) in the existing Supabase Postgres database for match events and outcomes. No changes to existing `rides` or `requests` schemas required.

---

## Out-of-Scope

- The real-outcome-dataset ETL job itself, including data-quality filtering and anonymization/retention policy — covered by Phase 13 item 046, which consumes the data this feature produces.
- Automated retraining, shadow deployment, and drift monitoring — Phase 13 items 047-049.
- Any passenger- or driver-facing UI or UX changes — this feature is backend instrumentation only.
- True client-side "viewed" telemetry (e.g. scroll-into-view tracking) — v1 treats "returned in the search API response" as the impression event; finer-grained view tracking can be layered on later without changing this feature's schema.

---

## Technical Considerations

- Must not introduce synchronous latency into the search request path or the existing 1-second AI service timeout (012-ai-application, Principle IV).
- Should follow the project's existing asyncpg / raw-SQL convention for the new tables — no ORM (per current `services/api` conventions).
- This is a `services/api` concern: the search request path already owns candidate assembly and AI client calls; `services/ai` does not need to change to support logging.

---

## Assumptions

- Passenger identity is available at search time via existing authentication and can be attached to match events.
- Exploration rate starts at approximately 10-15% (see Clarifications) and is tuned once real traffic volume is observed (~100 rides/day at launch, per current growth expectations); the exact production value remains a configuration decision made during implementation, not a hardcoded constant.
- Data retention and anonymization policy for this data (relevant given Egypt PDPL 151/2020) is addressed by Phase 13 item 046, which owns the ETL and data-quality/retention concerns; this feature only owns correct, complete capture.
- "Viewed" is treated as equivalent to "returned in the search response" for v1; distinguishing true user-eye-time from API-returned is deferred (see Out-of-Scope).
