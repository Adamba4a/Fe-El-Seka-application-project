import numpy as np

from app.models.prediction import RankedRide, RideRankingBatchRequest, RideRankingResponse
from app.services.feature_engineering import build_feature_vector_from_coords


def rank_candidates(request: RideRankingBatchRequest, model_state: dict) -> RideRankingResponse:
    model = model_state["model"]
    version = model_state["version"]

    feature_rows = []
    candidate_ids = []

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
        candidate_ids.append(c.candidate_id)

    X = np.array(feature_rows)
    scores = np.clip(model.predict_proba(X)[:, 1], 0.0, 1.0)

    order = np.argsort(scores)[::-1]
    ranked = [
        RankedRide(candidate_id=candidate_ids[idx], rank=rank + 1, score=float(scores[idx]))
        for rank, idx in enumerate(order)
    ]
    return RideRankingResponse(ranked=ranked, model_version=version)
