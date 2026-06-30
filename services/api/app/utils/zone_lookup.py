from __future__ import annotations

CAIRO_ZONES: list[dict] = [
    {"name": "Downtown Cairo", "lat": 30.0444, "lng": 31.2357},
    {"name": "Maadi",          "lat": 30.0131, "lng": 31.2089},
    {"name": "Zamalek",        "lat": 30.0626, "lng": 31.2197},
    {"name": "Heliopolis",     "lat": 30.0876, "lng": 31.3219},
    {"name": "Nasr City",      "lat": 30.0561, "lng": 31.3360},
    {"name": "New Cairo",      "lat": 30.0271, "lng": 31.4697},
    {"name": "6th of October", "lat": 29.9285, "lng": 30.9188},
    {"name": "Giza",           "lat": 30.0131, "lng": 31.2089},
    {"name": "Mohandessin",    "lat": 30.0619, "lng": 31.1997},
    {"name": "Dokki",          "lat": 30.0380, "lng": 31.2114},
    {"name": "Shubra",         "lat": 30.1060, "lng": 31.2436},
    {"name": "Ain Shams",      "lat": 30.1180, "lng": 31.3197},
    {"name": "Smart Village",  "lat": 30.0723, "lng": 30.9703},
]


def nearest_zone(lat: float, lng: float) -> tuple[str, dict[str, float]]:
    zone = min(CAIRO_ZONES, key=lambda z: (z["lat"] - lat) ** 2 + (z["lng"] - lng) ** 2)
    return zone["name"], {"lat": zone["lat"], "lng": zone["lng"]}
