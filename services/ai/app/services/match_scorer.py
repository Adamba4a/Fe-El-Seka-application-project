import numpy as np

from app.models.prediction import MatchScoreBatchRequest, MatchScoreItem, MatchScoreResponse
from app.services.feature_engineering import build_feature_vector_from_coords


def predict_scores(request: MatchScoreBatchRequest, model_state: dict) -> MatchScoreResponse:
    model = model_state["model"]
    version = model_state["version"]

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
    raw_scores = model.predict_proba(X)[:, 1]
    clamped = np.clip(raw_scores, 0.0, 1.0)

    scores = [
        MatchScoreItem(candidate_id=str(i), score=float(s))
        for i, s in enumerate(clamped)
    ]
    return MatchScoreResponse(scores=scores, model_version=version)
