# Feature Specification: Continuous Learning Pipeline

**Feature Branch**: `016-continuous-learning-pipeline`

**Created**: 2026-08-02

**Status**: Draft

**Input**: User description: "Phase 13: Advanced AI & Continuous Learning — production retraining, shadow deployment rollout, and model monitoring on real outcome data (roadmap items 046-049, building on the match-event instrumentation and exploration strategy already shipped in 013-match-learning-foundation)"

## Business Objective *(mandatory)*

Replace the synthetic-data-bootstrapped AI models (match score, ride ranking) with models that learn from real passenger and driver behavior, on an ongoing basis, without regressing match quality or silently reinforcing the launch model's own biases. This closes the loop opened by `013-match-learning-foundation`: that feature captures real outcomes; this feature turns captured outcomes into better-performing, safely-deployed models.

> **Scope correction (2026-08-02, during planning)**: pricing is excluded from this feature. Since the 2026-07-14 pricing simplification, fare calculation is deterministic-only (`pricing_service.py` + `pricing_config`) — there is no AI pricing model in the registry to retrain, evaluate, or roll out. The original roadmap phrasing ("match score, ride ranking, pricing") predates that change. If AI-driven pricing is reintroduced later, it can reuse this feature's retraining/shadow/rollout mechanics as a separate follow-up.

**Constitutional Domain**: AI Integration / Route Intelligence

**Affected Applications**: Shared (`services/api`, `services/ai`) — backend and AI-service only; no passenger, driver, or admin-facing UI changes.

---

## Clarifications

### Session 2026-08-02

- Q: What metric determines whether a candidate model "wins" the champion-vs-challenger offline evaluation (FR-007/FR-008)? → A: A ranking-quality metric — how often the model's top-ranked candidate matches the ride the passenger actually chose/accepted, on held-out real outcome data.
- Q: What live signal triggers automatic rollback during a staged rollout (FR-012), given real outcomes lag behind predictions? → A: Short-horizon acceptance rate — the percentage of the rolled-out model's shown candidates that get booked/accepted, tracked in near-real-time, since it's available within minutes unlike completion or rating.
- Q: What minimum accumulated real-traffic volume gates automated retraining and promotion (Assumptions)? → A: 500 completed rides with recorded outcomes — reachable in about a week at expected launch volume (~100 rides/day), balancing statistical usability against time-to-first-retrain.
- Q: What is the maximum acceptable lag between a real model degradation starting and monitoring raising an alert (NFR-004, SC-004)? → A: Hourly batch checks — enough resolution to catch meaningful degradation without chasing noise at Fe El Seka's expected launch volume (~100 rides/day), without needing a streaming metrics pipeline.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real ride outcomes become a labeled training dataset (Priority: P1)

As the platform, logged match events and their downstream outcomes (booked, accepted, rejected, completed, cancelled, rated) are periodically joined and transformed into a labeled dataset that reflects real revealed preference, so that any future model — whether trained by this pipeline or analyzed manually — has trustworthy ground truth to learn from instead of only synthetic rides.

**Why this priority**: This is the foundation everything else in this feature depends on. Without a correctly labeled real-outcome dataset, there is nothing to retrain on, nothing to hold out for evaluation, and nothing to monitor for drift. It is also independently valuable on its own — even before automated retraining exists, the dataset can be inspected manually to sanity-check the launch model's assumptions.

**Independent Test**: With a population of match events and linked outcomes already present (from `013-match-learning-foundation`), run the dataset pipeline and confirm it produces a labeled dataset where each row has a clear signal strength (e.g., completed+highly-rated vs. shown-not-booked) and excludes rows flagged as low-quality (bot/fraud/spam) or outside the retention window.

**Acceptance Scenarios**:

1. **Given** a set of match events with linked outcomes spanning completed, cancelled, and shown-not-booked cases, **When** the dataset pipeline runs, **Then** it produces one labeled training example per match event, each tagged with a signal-strength tier from a defined hierarchy (completed + highly rated > completed unrated > booked-not-completed > shown-not-booked).
2. **Given** a match event tied to a booking that was later cancelled, **When** the pipeline assigns a label, **Then** the cancellation is treated per the documented ambiguous-signal handling rather than automatically counted as a negative outcome.
3. **Given** a match event associated with an account previously flagged for fraudulent or abusive behavior, **When** the dataset pipeline runs, **Then** that event's data is excluded from the output dataset.
4. **Given** a dataset run completes, **When** the output is inspected, **Then** every retained row falls within the documented data-retention window and has had any personally identifying fields anonymized or removed per the documented policy.

---

### User Story 2 - New model versions are trained and only promoted if they beat the live model (Priority: P2)

As the platform, new candidate model versions for match scoring, ride ranking, and pricing are automatically trained on the latest real-outcome dataset and evaluated against a fixed, real-world benchmark — and a candidate only replaces the currently live model if it demonstrably performs better, never automatically otherwise.

**Why this priority**: Automated retraining without a promotion gate is dangerous — it could silently replace a working model with a worse one trained on a noisy or biased recent sample. Champion-vs-challenger gating is what makes "learn from real users" safe to automate. This depends on User Story 1 producing a trustworthy dataset.

**Independent Test**: Trigger a retraining run against a fixed historical real-outcome dataset snapshot. Confirm a challenger model is produced, evaluated against the same held-out real data the current live (champion) model was last evaluated on, and that promotion only occurs when the challenger's evaluation score exceeds the champion's by the defined margin.

**Acceptance Scenarios**:

1. **Given** a new labeled dataset snapshot is available, **When** the retraining pipeline runs on schedule, **Then** a new candidate model version is trained and registered with a version identifier, without automatically becoming the live model.
2. **Given** a candidate model has been trained, **When** it is evaluated, **Then** its evaluation is run against held-out real outcome data, not synthetic data, and produces a comparable score to the current live model's last recorded score on the same evaluation set.
3. **Given** a candidate model's evaluation score does not exceed the live model's score by the defined promotion margin, **When** the evaluation completes, **Then** the candidate is retained in the model registry but is NOT promoted to live, and the outcome is recorded for review.
4. **Given** a candidate model's evaluation score exceeds the live model's score by the defined promotion margin, **When** promotion criteria are met, **Then** the candidate becomes eligible for rollout via the shadow deployment process (User Story 3) rather than replacing the live model directly.

---

### User Story 3 - New models prove themselves in shadow before serving real traffic (Priority: P3)

As the platform, a model version that has passed offline evaluation is first run in shadow mode — generating predictions that are logged and compared against the live model and real outcomes, without being shown to any user — and is only gradually rolled out to real traffic once its shadow-mode performance holds up.

**Why this priority**: Offline evaluation on historical data cannot fully predict how a model behaves on live traffic. Shadow deployment is the safety net between "passed the benchmark" and "trusted with real passengers and drivers." It depends on User Story 2 having already produced a promotion-eligible candidate.

**Independent Test**: Deploy a promotion-eligible candidate in shadow mode alongside the live model. Confirm its predictions are logged for every live request without being returned to any passenger or driver, and that a comparison report between shadow and live predictions is available before any traffic is shifted.

**Acceptance Scenarios**:

1. **Given** a promotion-eligible candidate model, **When** it is deployed in shadow mode, **Then** it produces a prediction for every live match/ranking/pricing request the champion also scores, logged for comparison, but the shadow prediction is never returned to the requesting passenger or driver.
2. **Given** a shadow model has accumulated a defined minimum burn-in period of live comparison data, **When** the burn-in period ends, **Then** a comparison report is produced showing the shadow model's agreement/divergence with the champion and, where outcomes are already known, which model's prediction better matched the real outcome.
3. **Given** a shadow model's burn-in comparison meets the rollout criteria, **When** rollout begins, **Then** it is shifted to serve a small percentage of real traffic first, with the percentage increased in defined steps rather than switched to 100% at once.
4. **Given** a model serving a partial percentage of real traffic has a short-horizon acceptance rate below the champion's by the defined margin, **When** the underperformance is detected, **Then** rollout is halted and traffic reverts to the champion without requiring a manual code deployment.

---

### User Story 4 - Model quality is continuously monitored so degradation is caught before users complain (Priority: P4)

As the platform, prediction distributions and downstream acceptance/completion rates for live models are continuously tracked per zone and time window, so that a degrading model is flagged by monitoring and periodic human spot-audits, rather than discovered through a spike in user complaints or a visible drop in bookings.

**Why this priority**: Retraining and shadow rollout reduce the risk of deploying a bad model, but they don't eliminate drift after a model has been live for weeks (e.g., seasonal demand shifts, new geographic zones). This is the ongoing safety net once User Stories 1-3 are operating. It is independently valuable even against the current single launch model, before any retraining cycle has occurred.

**Independent Test**: With a live model serving traffic, review the monitoring output over a period and confirm prediction-distribution and acceptance-rate metrics are broken down by zone and time window, and that a synthetic/injected degradation (e.g., replaying a known-bad prediction pattern) triggers a flagged alert.

**Acceptance Scenarios**:

1. **Given** a live model is serving predictions, **When** monitoring runs on its regular interval, **Then** prediction-score distribution and real acceptance/completion rates are recorded per geographic zone and time window.
2. **Given** a live model's acceptance rate in a specific zone drops below its established baseline by a defined margin, **When** the monitoring check runs, **Then** an alert is raised identifying the affected zone and metric, without requiring a user complaint to surface it.
3. **Given** the monitoring period defined for periodic human spot-audits elapses, **When** the audit is due, **Then** a sample of the live model's recent decisions is surfaced for manual review, weighted toward the early low-volume period after any promotion or rollout.

---

### Edge Cases

- What happens when accumulated real traffic volume is too low to produce a statistically meaningful dataset or evaluation set? The dataset pipeline still runs and produces output, but retraining and promotion are gated on the 500-completed-ride minimum volume threshold (see Assumptions) — a smaller dataset does not block User Story 1's inspection value, but does block User Story 2's automated promotion.
- What happens if a challenger model is never promoted because it never beats the champion? The champion continues serving indefinitely; this is the expected safe outcome, not a failure state.
- What happens if the AI service or model registry is unavailable during a scheduled retraining run? The run is skipped and logged as missed; the existing live model continues serving unaffected, per the fallback behavior already established in `012-ai-application`.
- What happens if a shadow or partially-rolled-out model's underlying feature inputs (e.g., a new zone with no historical data) fall outside what it was trained on? Rollout criteria must account for per-zone confidence, not just an aggregate metric, so a model can be rolled back in a specific zone without a full global rollback.
- What happens to human spot-audit findings that identify a live problem outside a scheduled monitoring alert? They feed back into the model-registry record for that version and can trigger an out-of-cycle rollback, independent of the scheduled retraining cadence.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST periodically join logged match events (`013-match-learning-foundation`) with their linked outcomes into a labeled training dataset, without requiring manual data assembly.
- **FR-002**: The dataset pipeline MUST assign each labeled example a signal-strength tier per a documented hierarchy (completed + highly rated > completed unrated > booked-not-completed > shown-not-booked), with cancellations handled per documented rules rather than treated as an automatic negative signal.
- **FR-003**: The dataset pipeline MUST exclude data associated with accounts or events flagged as bot, fraudulent, or spam activity.
- **FR-004**: The dataset pipeline MUST enforce a documented data-retention window and MUST anonymize or remove personally identifying fields from output training data, consistent with Egypt PDPL 151/2020 obligations.
- **FR-005**: System MUST support triggering model retraining (match score, ride ranking) on the latest available labeled dataset, on a recurring schedule and on-demand.
- **FR-006**: Every trained candidate model MUST be registered with a distinct version identifier in the existing model registry, independent of whether it is promoted.
- **FR-007**: System MUST evaluate every candidate model against held-out real-outcome data, not synthetic data, using a ranking-quality metric — how often the model's top-ranked candidate matches the ride the passenger actually chose/accepted — producing a score comparable to the currently live model's evaluation score on the same held-out set.
- **FR-008**: System MUST NOT promote a candidate model to live traffic based on retraining alone — promotion requires the candidate's evaluation score to exceed the live model's by a defined margin (champion-vs-challenger gating).
- **FR-009**: System MUST support deploying a promotion-eligible candidate model in shadow mode, generating predictions on live requests that are logged but never returned to passengers or drivers.
- **FR-010**: System MUST produce a comparison report between a shadow model and the live model after a defined burn-in period, including agreement/divergence and, where known, alignment with real outcomes.
- **FR-011**: System MUST support gradual, percentage-based traffic rollout for a model that has passed shadow burn-in, rather than an immediate full switch.
- **FR-012**: System MUST automatically halt an in-progress rollout and revert traffic to the champion model when a rolled-out candidate's short-horizon acceptance rate (percentage of its shown candidates that get booked/accepted, tracked near-real-time) underperforms the champion's by a defined margin, without requiring a code deployment to revert.
- **FR-013**: System MUST continuously track prediction-score distributions and real acceptance/completion rates for the live model, broken down by geographic zone and time window.
- **FR-014**: System MUST raise an alert when a live model's tracked metrics degrade beyond a defined baseline margin for a given zone or time window.
- **FR-015**: System MUST support periodic human spot-audits of a sample of the live model's recent decisions, with increased audit frequency during the early period following any promotion or rollout.
- **FR-016**: System MUST retain a complete history of model versions, their training dataset snapshot, evaluation scores, promotion decisions, and rollout outcomes, for auditability.

### Key Entities *(include if feature involves data)*

- **Training Example**: One labeled row derived from a match event and its linked outcome(s). Attributes: source match-event reference, feature vector snapshot, signal-strength tier, label, dataset-snapshot identifier, retention/expiry marker.
- **Dataset Snapshot**: A versioned, point-in-time output of the dataset pipeline. Attributes: snapshot identifier, generation timestamp, row count, date range covered, exclusion/filtering summary.
- **Model Version**: A trained candidate or champion model artifact. Attributes: version identifier, model type (match score / ranking), training dataset snapshot reference, evaluation score, promotion status (candidate / shadow / partial-rollout / champion / retired), creation timestamp.
- **Evaluation Result**: The outcome of scoring a model version against held-out real data. Attributes: model version reference, held-out dataset reference, ranking-quality score (rate at which the model's top-ranked candidate matches the passenger's actual chosen/accepted ride), comparison margin vs. champion, evaluation timestamp.
- **Shadow Comparison Report**: Aggregated comparison between a shadow model version and the live champion over a burn-in period. Attributes: shadow model version reference, champion version reference, burn-in window, agreement rate, outcome-alignment rate where known.
- **Monitoring Metric**: A tracked measurement of live model behavior. Attributes: model version reference, zone, time window, metric type (prediction distribution / acceptance rate / completion rate), value, baseline, alert status.
- **Spot Audit Record**: A human review of a sampled live model decision. Attributes: model version reference, sampled decision reference, reviewer, finding, timestamp.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Once sufficient real traffic has accumulated, a labeled real-outcome dataset can be produced end-to-end without manual data wrangling, on a recurring cadence.
- **SC-002**: At least one retrained model version is evaluated against real held-out data and either promoted or rejected using the champion-vs-challenger comparison, with the decision and reasoning fully traceable after the fact.
- **SC-003**: No model version reaches 100% live traffic without first completing a shadow burn-in period and a gradual, staged rollout.
- **SC-004**: A degrading live model's acceptance-rate or prediction-distribution shift in any zone is flagged by monitoring within one hour of the degradation appearing in that hour's metric window, prior to any manual complaint being the first signal.
- **SC-005**: 100% of promoted and rejected model versions have a retrievable audit trail covering their training dataset snapshot, evaluation score, and promotion decision.
- **SC-006**: A rollout that underperforms the champion is automatically reverted without requiring an emergency deployment, within the defined rollback detection window.

## Non-Functional Requirements *(mandatory)*

- **NFR-001**: The dataset pipeline and retraining jobs MUST run as scheduled background processes and MUST NOT add latency or load to the passenger- or driver-facing request paths (search, booking, ranking).
- **NFR-002**: All personally identifying data handled by the dataset pipeline MUST be encrypted in transit and at rest and access-controlled per the platform's existing data-protection standards.
- **NFR-003**: Shadow-mode prediction generation MUST NOT add measurable latency to the live request path it shadows — shadow scoring happens off the response-blocking path, consistent with the async logging pattern established in `013-match-learning-foundation`.
- **NFR-004**: Monitoring metric collection and alerting MUST run on an hourly batch cadence, so a real degradation is flagged within at most one hour of its metric window closing, without requiring a streaming metrics pipeline.
- **NFR-005**: Retraining, evaluation, promotion, and rollout configuration (schedule, promotion margin, rollout step sizes, rollback thresholds) MUST be adjustable without a code deployment.

---

## Dependencies *(mandatory)*

- **Internal**: `013-match-learning-foundation` — source of the match events and linked outcomes this feature's dataset pipeline consumes; this feature cannot produce meaningful output without it. `002-ai-foundation` / `012-ai-application` — existing model registry, versioning, and live-serving infrastructure this feature extends with promotion, shadow, and rollout states. `032-ratings-system` — rating data feeds the highest signal-strength tier once available for a given ride.
- **External**: None new — no third-party ML platform or service is introduced; retraining and serving continue to use the existing AI service infrastructure.
- **Data**: Requires accumulated real production traffic with logged match events and outcomes (see Assumptions on minimum volume); requires the existing Supabase Postgres database and model artifact storage already in place.

---

## Out-of-Scope

- Demand forecasting and fraud detection models (roadmap Phase 13, TBD items) — not yet specified; this feature covers only the real-outcome dataset, retraining, shadow rollout, and monitoring pipeline for the existing match score and ranking models.
- AI-driven pricing — pricing has been deterministic-only since 2026-07-14; there is no pricing model in the registry for this feature to retrain, evaluate, or roll out. Reintroducing an AI pricing model is a separate future decision, not part of this feature.
- The initial match-event and outcome logging instrumentation, and the ranking exploration strategy that generates counterfactual data — already delivered by `013-match-learning-foundation`; this feature only consumes that data.
- Any passenger-, driver-, or admin-facing UI or UX changes — this is a backend/AI-service pipeline feature.
- Arabic/RTL localization (Phase 14) and digital payment integration (Phase 15) — unrelated domains.
- Introducing a new third-party ML platform, feature store, or experiment-tracking tool — this feature builds on the existing model registry and Supabase infrastructure.

---

## Technical Considerations

- Must reuse the existing model registry and versioned-artifact storage already established in `002-ai-foundation` / `012-ai-application`, adding promotion/shadow/rollout status rather than introducing a parallel system.
- Dataset pipeline, retraining, and monitoring jobs are backend/AI-service concerns (`services/api`, `services/ai`); no `apps/main` or `apps/admin` changes are anticipated, though an admin-visible view of model versions and monitoring alerts may be a natural extension of `015-admin-operations` in a future iteration.
- Should follow the project's existing asyncpg / raw-SQL convention for any new tables, consistent with `013-match-learning-foundation`.
- Retraining and evaluation MUST reuse the calibration and monotonicity fixes already established for match scoring (2026-07-04 recalibration, per `002-ai-foundation` research notes) so that automated retraining cannot silently reintroduce previously-fixed miscalibration.
- Shadow deployment and staged rollout require the live serving path to support running two model versions concurrently for the same request without doubling user-facing latency.

---

## Assumptions

- This feature can be fully specified, planned, and implemented locally before the platform is redeployed; however, User Stories 2-4 (retraining, shadow rollout, monitoring) cannot be meaningfully exercised end-to-end against real data until public traffic resumes and accumulates. User Story 1 (dataset pipeline) can be built and validated now against locally-seeded or synthetic-shaped match-event data that mirrors the real schema.
- A minimum real-traffic volume threshold of 500 completed rides with recorded outcomes gates automated retraining and promotion — reachable in roughly a week at the platform's expected launch volume (~100 rides/day). This is a configuration value, not a hardcoded constant, and can be tuned once real volume is observed.
- Retraining runs on a recurring cadence (e.g., weekly) by default, adjustable via configuration rather than requiring a fixed cadence to be decided now.
- The promotion margin, shadow burn-in duration, rollout step sizes, and rollback thresholds are configuration values with reasonable conservative defaults, tunable post-launch as real-world variance is observed — none of these are hardcoded in a way that requires a redeployment to adjust.
- Egypt PDPL 151/2020 data-retention and anonymization requirements apply to this feature's stored training data in the same way they apply to the source match-event data it consumes; this feature does not introduce new categories of personal data beyond what `013-match-learning-foundation` already logs.
- Admin-facing visibility into model versions, evaluation results, and monitoring alerts is desirable but not required for this feature's core pipeline to function; if needed, it can be layered on as an extension of the existing admin operations domain (`015-admin-operations`) without changing this feature's data model.
