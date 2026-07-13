from __future__ import annotations

# Kept in sync with services/ai/pipelines/dataset/zones.py — both must list the
# same zones/coordinates so serving-time zone snapping matches what the models
# were trained on.
CAIRO_ZONES: list[dict] = [
    {"name": "Downtown Cairo",       "lat": 30.0444, "lng": 31.2357},
    {"name": "Maadi",                "lat": 30.0131, "lng": 31.2089},
    {"name": "Zamalek",              "lat": 30.0598, "lng": 31.2214},
    {"name": "Heliopolis",           "lat": 30.0912, "lng": 31.3217},
    {"name": "Nasr City",            "lat": 30.0626, "lng": 31.3462},
    {"name": "New Cairo",            "lat": 30.0274, "lng": 31.4745},
    {"name": "6th of October",       "lat": 29.9602, "lng": 30.9304},
    {"name": "Giza",                 "lat": 29.9870, "lng": 31.2118},
    {"name": "Mohandessin",          "lat": 30.0594, "lng": 31.2024},
    {"name": "Dokki",                "lat": 30.0381, "lng": 31.2124},
    {"name": "Shubra",               "lat": 30.1100, "lng": 31.2480},
    {"name": "Ain Shams",            "lat": 30.1191, "lng": 31.3272},
    {"name": "Cairo University",     "lat": 30.0260, "lng": 31.2097},
    {"name": "AUC New Cairo",        "lat": 30.0209, "lng": 31.4997},
    {"name": "Ain Shams University", "lat": 30.1199, "lng": 31.3220},
    {"name": "Helwan University",    "lat": 29.8421, "lng": 31.3340},
    {"name": "Smart Village",        "lat": 30.0730, "lng": 30.9710},
    {"name": "New Admin Capital",    "lat": 30.0130, "lng": 31.6990},
    {"name": "El Shorouk",           "lat": 30.1296, "lng": 31.6318},
    {"name": "Madinaty",             "lat": 30.0917, "lng": 31.6381},
]


def nearest_zone(lat: float, lng: float) -> tuple[str, dict[str, float]]:
    zone = min(CAIRO_ZONES, key=lambda z: (z["lat"] - lat) ** 2 + (z["lng"] - lng) ** 2)
    return zone["name"], {"lat": zone["lat"], "lng": zone["lng"]}
