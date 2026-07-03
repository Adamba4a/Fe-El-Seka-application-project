import math

import numpy as np

from app.models.prediction import FareRange, PriceRequest, PriceResponse

_MIN_FARE_EGP = 10.0

_PRICE_FEATURES_ORDER = [
    "passenger_origin_lat",
    "passenger_origin_lng",
    "passenger_dest_lat",
    "passenger_dest_lng",
    "dest_zone_distance_km",
    "departure_hour_sin",
    "departure_hour_cos",
]


def predict_price(request: PriceRequest, model_state: dict) -> PriceResponse:
    model = model_state["model"]
    version = model_state["version"]

    hour = request.departure_at.hour + request.departure_at.minute / 60.0
    hour_sin = math.sin(2 * math.pi * hour / 24)
    hour_cos = math.cos(2 * math.pi * hour / 24)

    X = np.array([[
        request.origin_centroid.lat,
        request.origin_centroid.lng,
        request.destination_centroid.lat,
        request.destination_centroid.lng,
        request.estimated_distance_km,
        hour_sin,
        hour_cos,
    ]])

    raw_price = float(model.predict(X)[0])
    estimate = max(raw_price, _MIN_FARE_EGP)

    fare_range = FareRange(
        min_egp=round(max(_MIN_FARE_EGP, estimate * 0.8), 2),
        max_egp=round(estimate * 1.2, 2),
    )
    return PriceResponse(model_version=version, recommended_fare=fare_range)
