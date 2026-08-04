import numpy as np

from app.models.prediction import MatchScoreBatchRequest, MatchScoreItem, MatchScoreResponse
from app.services.feature_engineering import build_feature_vector_from_coords


def predict_scores(request: MatchScoreBatchRequest, model_state: dict) -> MatchScoreResponse:
    model = model_state["model"]
    version = model_state["version"]
    candidate_slot = model_state.get("candidate")

    feature_rows = []
    for c in request.candidates:
        vec = build_feature_vector_from_coords(
            passenger_origin_lat=c.passenger_origin.lat,
            passenger_origin_lng=c.passenger_origin.lng,
            passenger_dest_lat=c.passenger_destination.lat,
            passenger_dest_lng=c.passenger_destination.lng,
            driver_origin_lat=c.driver_origin.lat,
            driver_origin_lng=c.driver_origin.lng,
            driver_dest_lat=c.driver_destination.lat,
            driver_dest_lng=c.driver_destination.lng,
            overlap_ratio=c.overlap_ratio,
            pickup_detour_km=c.pickup_detour_km,
            dropoff_distance_km=c.dropoff_distance_km,
            departure_at_utc=c.departure_at,
        )
        feature_rows.append(vec)

    X = np.array(feature_rows)
    raw_scores = model.predict(X)
    clamped = np.clip(raw_scores, 0.0, 1.0)

    # Shadow score never influences `score`/ranking — computed from the same
    # feature matrix purely for the burn-in comparison report (T028).
    shadow_scores: list[float] | None = None
    shadow_model_version: str | None = None
    if candidate_slot is not None:
        shadow_raw = candidate_slot["model"].predict(X)
        shadow_scores = np.clip(shadow_raw, 0.0, 1.0).tolist()
        shadow_model_version = candidate_slot["version"]

    scores = [
        MatchScoreItem(
            candidate_id=str(i),
            score=float(s),
            shadow_score=float(shadow_scores[i]) if shadow_scores is not None else None,
        )
        for i, s in enumerate(clamped)
    ]
    return MatchScoreResponse(scores=scores, model_version=version, shadow_model_version=shadow_model_version)
