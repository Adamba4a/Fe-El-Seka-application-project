# Feature Specification: AI Application

**Feature Branch**: `012-ai-application`

**Created**: 2026-07-01

**Status**: Draft

**Input**: Competition MVP — Phase 9 — ai-route-matching (029), ai-ride-ranking (030), ai-pricing-recommendations (031)

---

## Business Objective *(mandatory)*

Deploy the trained AI models into the live passenger search and driver ride creation flows — replacing deterministic ordering with AI-powered match scoring and ranking for passengers, and replacing manual pricing with a system-assigned fare computed by the AI pricing model at ride creation — fulfilling Fe El Seka's mandatory AI-powered transportation intelligence requirement for the competition.

**Constitutional Domain**: AI-Augmented Transportation (Principle IV)

**Affected Applications**: Main App (Passenger experience + Driver experience)

---

## Clarifications

### Session 2026-07-01

- Q: Is the AI match score stored in the database or computed per request and discarded? → A: Ephemeral — computed per search request, returned in the API response, and not persisted to the database.
- Q: Does the driver see the system-assigned fare before or after submitting ride creation? → A: Single-step create — the fare is assigned and returned in the ride creation response and shown on the success/confirmation screen; no separate fare preview API call.
- Q: Is the AI match score shown only in the search results list, or also on the individual ride detail page? → A: Both — match score is displayed on each ride card in the search results list and on the individual ride detail page.
- Q: How is the AI match score displayed to passengers — decimal, percentage, or label? → A: Percentage — displayed as a whole-number percentage (e.g., "85% match") converted from the internal 0.0–1.0 value.
- Q: Should rides below a minimum match quality be filtered from results, or all candidates shown? → A: Filter with minimum count — candidates below 20% match are hidden, but if filtering leaves fewer than 3 results, the highest-scoring suppressed rides are added back until the list reaches 3.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Passenger Receives AI-Ranked Ride Results (Priority: P1)

When a passenger searches for rides, the returned list is ordered by AI-predicted match quality — not just raw route overlap. A match percentage (e.g., "85% match") is displayed on each ride card so the passenger can immediately identify the best-fit ride for their journey.

**Why this priority**: This is the externally visible AI capability required by the competition. Without it, Fe El Seka's AI is not demonstrable. It is the primary reason Phase 9 exists.

**Independent Test**: A developer submits a passenger search request and confirms the response contains candidate rides with match scores attached, ordered from highest to lowest score.

**Acceptance Scenarios**:

1. **Given** a verified passenger submits a ride search with valid origin and destination, **When** the route intelligence engine returns candidate rides, **Then** the system returns those candidates ordered by AI match score from highest to lowest.
2. **Given** search results are returned to the passenger, **When** the passenger views the results list, **Then** each ride card displays a match percentage between 0% and 100% (converted from the internal 0.0–1.0 score).
3. **Given** two candidate rides where Ride A has a score of 0.85 and Ride B has a score of 0.62, **When** results are returned, **Then** Ride A (displayed as "85% match") appears above Ride B (displayed as "62% match") in the list.
4. **Given** a passenger submits a search and zero candidate rides are found by the route intelligence engine, **When** the AI scoring step is reached, **Then** no AI call is made and an empty results list is returned without error.
5. **Given** the AI service returns a match score outside the 0.0–1.0 range for any candidate, **When** the backend processes the response, **Then** the value is clamped to the valid range before being shown to the passenger.
6. **Given** a passenger taps a ride card to view its detail page, **When** the detail page loads, **Then** the same AI match score shown on the search results card is displayed on the detail page.
7. **Given** 5 candidate rides are found and 4 of them score below 20%, **When** results are returned, **Then** the list contains 3 rides — the 1 ride above threshold plus the 2 highest-scoring suppressed rides added back.
8. **Given** all candidate rides score below 20%, **When** results are returned, **Then** the 3 highest-scoring candidates are shown rather than an empty list.

---

### User Story 2 — Fare Assigned by System at Ride Creation (Priority: P2)

When a driver creates a new ride, the platform automatically computes and assigns the fare using the AI pricing model in a single creation call. The driver sees the system-assigned fare on the success/confirmation screen after the ride is created. The fare is final and immutable — there is no preview step and no modification is possible.

**Why this priority**: Platform-controlled pricing is a core business rule that ensures fare consistency and prevents manipulation. It is a key differentiator from manual driver pricing.

**Independent Test**: A driver completes the ride creation flow and the resulting ride record carries a system-assigned fare. No UI element or API endpoint allows that fare to be subsequently changed.

**Acceptance Scenarios**:

1. **Given** a verified driver has filled in ride details (origin, destination, departure time, seat count), **When** the driver submits the ride creation form, **Then** the platform assigns a fare computed by the AI pricing model before the ride is persisted to the database.
2. **Given** a ride has been created with a system-assigned fare, **When** the driver views ride details or edits any other ride field, **Then** no interface element or API action allows the fare to be changed.
3. **Given** two rides are created on the same route — one during the 7–9am peak and one at midday, **When** both fares are compared, **Then** the system reflects pricing intelligence appropriate to the time-of-day difference.
4. **Given** the AI pricing service is unavailable at the moment of ride creation, **When** the system detects the failure, **Then** it assigns a deterministic fallback fare and ride creation proceeds without surfacing an error to the driver.
5. **Given** the AI pricing model returns a zero or negative fare value, **When** the backend receives that result, **Then** the system rejects the value, applies the deterministic fallback fare, logs the anomaly, and the ride is created successfully.

---

### User Story 3 — Graceful Degradation When AI Is Unavailable (Priority: P3)

When the AI service is unreachable or returns an unrecoverable error, passengers continue to receive ride results ordered by route overlap percentage, and drivers still have a fare assigned at ride creation — with no error surfaced to either user.

**Why this priority**: The AI service must enhance the experience, not become a single point of failure. Core platform flows must always be available.

**Independent Test**: A developer stops the AI service, submits a passenger search, and confirms valid ordered results are returned with no error — then confirms a driver can still create a ride with a fare assigned.

**Acceptance Scenarios**:

1. **Given** the AI service is unreachable, **When** a passenger submits a ride search, **Then** the system detects the failure within 1 second and returns candidate rides ordered by route overlap percentage instead.
2. **Given** fallback ordering is applied, **When** the passenger receives the response, **Then** the response contains a valid, non-empty ride list with no error message and no indication that AI scoring was unavailable.
3. **Given** the AI service is unreachable, **When** a driver creates a ride, **Then** the system assigns the deterministic fallback fare and the ride is created successfully.
4. **Given** the AI service recovers and becomes reachable again, **When** the next search request arrives, **Then** the system automatically resumes AI-powered scoring and ranking without requiring a restart or manual intervention.

---

### Edge Cases

- What happens if the AI service returns scores for only a subset of candidates (partial failure)? The system must fall back to deterministic ordering for the **entire** result set — a mixed AI/deterministic list would produce a misleading ordering.
- What happens if only one candidate ride exists? The system must still return it with a match score — scoring a single result is valid.
- What happens if the feature engineering step cannot produce a valid feature vector for a specific candidate due to missing attributes? That candidate must be excluded from results entirely; the remaining candidates are scored normally.
- What happens if all candidates score identically (e.g., all 0.0 during a model failure)? The system must fall back to deterministic overlap ordering rather than returning an arbitrarily ordered tie.
- What happens if a ride is created when the AI pricing model is partially loaded but not yet ready? The system must detect the unready state, apply the fallback fare, and not block ride creation.
- What happens if all candidate rides score below 20%? The system must add back the top 3 highest-scoring candidates (or fewer if fewer exist) rather than returning an empty result set.
- What happens if fewer than 3 total candidates exist and all score below 20%? All available candidates are returned regardless of score — the minimum count guarantee takes precedence over the quality threshold.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Match Scoring

- **FR-001**: For every passenger ride search, the system MUST score each candidate ride using the AI match prediction model and produce a match score between 0.0 and 1.0 per candidate.
- **FR-002**: The system MUST pass the following attributes for each candidate to the AI scoring model: route overlap ratio, pickup detour distance, dropoff distance, time-of-day encoding, origin zone centroid, and destination zone centroid.
- **FR-003**: Match scores returned by the AI model MUST be clamped to the 0.0–1.0 range before use; any out-of-range value MUST be clamped and logged.
- **FR-004**: The match score MUST be displayed as a whole-number percentage (e.g., "85% match") on each ride card in the passenger search results list and on the individual ride detail page. The internal 0.0–1.0 value MUST be multiplied by 100 and rounded to the nearest integer before display.

#### Ride Ranking

- **FR-005**: Search results MUST be returned to the passenger ordered by AI match score, highest score first.
- **FR-005a**: Candidate rides scoring below 20% match MUST be excluded from search results. If exclusion reduces the result count below 3, the system MUST add back the highest-scoring suppressed rides (in descending score order) until the list contains exactly 3 results or all candidates are exhausted, whichever comes first.
- **FR-006**: When the AI service is unavailable, the system MUST fall back to ordering candidates by deterministic route overlap percentage within 1 second of detecting the failure.
- **FR-007**: Fallback ordering MUST be transparent to the passenger — no error message, no empty state, and no indication that AI scoring was skipped.
- **FR-008**: If all AI scores are identical (indicating a silent model failure), the system MUST activate the deterministic fallback ordering.

#### System-Assigned Fare

- **FR-009**: When a driver creates a ride, the system MUST compute and assign a fare using the AI pricing model within the same single ride creation call, before the ride record is persisted. No separate fare preview endpoint exists.
- **FR-010**: The fare MUST be computed using at minimum: origin zone, destination zone, estimated route distance, and time of day.
- **FR-011**: Drivers MUST NOT be able to modify the system-assigned fare through any user interface or API endpoint.
- **FR-012**: The system-assigned fare MUST be expressed in Egyptian Pounds (EGP) as a positive, non-zero value.
- **FR-013**: When the AI pricing service is unavailable, the system MUST assign a deterministic fallback fare and continue ride creation without surfacing an error to the driver.
- **FR-014**: If the AI pricing model returns a zero, negative, or otherwise invalid fare, the system MUST reject the result, apply the deterministic fallback fare, and log the anomaly.

### Key Entities

| Entity | Description |
|--------|-------------|
| **AI Match Score** | A numeric value (0.0–1.0) representing the AI-predicted compatibility between a passenger's route request and a specific candidate driver ride. Displayed to passengers as a whole-number percentage (e.g., "85% match"). Ephemeral — computed per search request and returned in the API response; not stored in the database. |
| **AI-Ranked Results** | The ordered list of candidate rides returned to a passenger, sorted by descending AI match score (or by route overlap percentage when fallback is active). |
| **System Fare** | The platform-computed and platform-assigned price in EGP for a driver's ride, set at ride creation time by the AI pricing model and immutable thereafter. |
| **Prediction Feature Vector** | The structured set of numeric attributes derived from a ride candidate, passed to the AI service as input for scoring and ranking. |
| **Fallback Ordering** | The deterministic ranking of candidates by route overlap percentage, activated transparently when the AI service is unavailable or returns an unrecoverable error. |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every passenger search response includes candidate rides ordered by AI match score, with rides below 20% filtered out unless doing so would leave fewer than 3 results — measurable by inspecting descending score order and verifying the minimum-count guarantee in test scenarios.
- **SC-002**: Every ride card in passenger search results and on the ride detail page displays a match percentage between 0% and 100% — zero results are returned without a visible score field.
- **SC-003**: When the AI service is stopped, passengers receive valid ordered search results within 1 second of the AI timeout — confirmed by timing fallback activation in test conditions.
- **SC-004**: Every ride created after Phase 9 is deployed carries a system-assigned fare — zero rides exist in the database without a fare value.
- **SC-005**: No driver action through any available interface results in a changed fare on an existing ride — confirmed by attempting a fare modification via UI and API and verifying both are rejected.
- **SC-006**: The AI pricing model produces a positive, non-zero fare for all route combinations covered by the synthetic training dataset used in the competition demo.

---

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The AI scoring and ranking step MUST add no more than 500ms to the total search response time at p95 for a batch of up to 20 candidate rides.
- **NFR-002**: The AI pricing call at ride creation MUST complete within 200ms at p95 under normal operating conditions.
- **NFR-003**: The system MUST detect AI service unavailability within 1 second (via health check or a failed prediction call) and activate the appropriate fallback path.
- **NFR-004**: Match scores and system fares MUST be deterministic for identical inputs — the same candidate and passenger request MUST always produce the same score given the same loaded model version.
- **NFR-005**: All AI prediction calls MUST be logged with: request input shape, model version used, response latency, and whether the fallback path was activated.
- **NFR-006**: The AI integration MUST NOT degrade the availability of passenger ride search or driver ride creation — both flows MUST operate correctly even when the AI service is completely offline.

---

## Dependencies *(mandatory)*

- **Internal — Phase 2 (AI Foundation)**: Trained model artifacts (match score, ride ranking, price recommendation) and the prediction API endpoints must be available and loaded. Phase 9 is a consumer of those endpoints — it does not train or manage models.
- **Internal — Phase 5 (Route Intelligence)**: The deterministic route overlap engine must be producing candidate rides with precomputed overlap ratios, detour distances, and zone attributes — these are the direct inputs to the AI feature vector.
- **Internal — Phase 4 (Ride Management)**: The driver ride creation flow must be in place. Phase 9 inserts the system fare assignment step into that existing flow.
- **Internal — Phase 6 (Passenger Experience)**: The passenger ride search and results display must be in place. Phase 9 wires AI scores and ranking into the existing results pipeline.
- **Data**: At least one trained model version must be loaded in the AI service model registry before Phase 9 produces real predictions. The fallback path handles the case where no model is available.

---

## Out-of-Scope

- Training or retraining AI models — handled by Phase 2 (AI Foundation); model retraining on real data is deferred to Post-Competition Phase 13.
- Candidate ride generation and route overlap calculation — handled by Phase 5 (Route Intelligence).
- Feature importance reporting or model explainability in any user-facing or admin-facing UI — deferred to Post-Competition Phase 11.
- Demand forecasting — deferred to Post-Competition Phase 13.
- Fraud detection — deferred to Post-Competition Phase 13.
- Model performance monitoring, drift detection, or automated retraining triggers — deferred to Post-Competition Phase 12.
- Admin-facing AI model performance dashboards or training history views — deferred to Post-Competition Phase 11.
- Any modification to the AI service itself (`services/ai`) — Phase 9 integrates `services/api` as a client of the AI service HTTP API; the AI service internals are not changed in this phase.

---

## Technical Considerations

- The AI service is the standalone Python FastAPI service built in Phase 2 (`services/ai`). Phase 9 adds client-side integration in `services/api` — no changes to `services/ai` are expected.
- The feature vector passed from `services/api` to `services/ai` must use the identical schema defined in Phase 2's feature engineering module. Any format divergence between training-time and serving-time feature vectors will silently invalidate model predictions — this is the highest-risk integration point.
- All AI prediction calls from `services/api` must have an explicit HTTP timeout (≤1 second) to prevent passenger search or ride creation from hanging when the AI service is slow or unresponsive.
- The system fare must be stored as `NUMERIC(12, 2)` consistent with the financial data standard established in Phase 8. Floating-point types (`FLOAT`, `DOUBLE PRECISION`) must not be used for monetary values.
- Fare immutability must be enforced at two levels: (1) no PATCH/PUT endpoint exposes the fare field, and (2) the database column is not writable after INSERT (enforced via application logic or column-level constraints).
- Per Constitution Principle IV, the AI service must remain independently deployable. `services/api` must not import from `services/ai` directly — all communication is over the HTTP prediction API.
- Per Constitution Principle II, the deterministic route overlap score from Phase 5 remains the authoritative measure of route feasibility. The AI score is an enhancement for ranking and pricing, not a replacement for feasibility gating.

---

## Assumptions

- The AI service from Phase 2 is running and has at least one trained model version loaded in the registry before Phase 9 is demonstrated at the competition.
- Route overlap ratio, detour distance, and zone attributes computed by Phase 5 are available on each candidate ride object at search time — no additional database queries are needed to build the feature vector.
- The fallback deterministic fare reuses the Phase 5 pricing formula (base fare + per-km rate) — no new fallback formula is required for Phase 9.
- The competition demo environment runs the AI service and main backend on the same local machine; internal network latency between them is negligible and does not affect the 500ms p95 target.
- MVP scale is ≤1,000 active users; AI scoring for batches of up to 20 candidate rides per search is the expected maximum batch size.
- The synthetic training dataset produces models with sufficient quality to generate meaningful, non-uniform match scores across different candidate rides — scores are not all concentrated at a single value.
- AI match scores are ephemeral — they are not stored in the database and require no new schema changes beyond those needed for the system fare column on the rides table.
