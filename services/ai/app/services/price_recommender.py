import math

import numpy as np

from app.models.prediction import PriceRequest, PriceResponse

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
        request.passenger_origin.lat,
        request.passenger_origin.lng,
        request.passenger_destination.lat,
        request.passenger_destination.lng,
        request.dest_zone_distance_km,
        hour_sin,
        hour_cos,
    ]])

    raw_price = float(model.predict(X)[0])
    price = max(raw_price, _MIN_FARE_EGP)

    return PriceResponse(recommended_price_egp=round(price, 2), model_version=version)
