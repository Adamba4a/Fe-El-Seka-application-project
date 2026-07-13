from dataclasses import dataclass


@dataclass(frozen=True)
class CairoZone:
    name: str
    zone_type: str  # district | university | business_zone
    centroid_lat: float
    centroid_lng: float
    weight: float


ZONES: list[CairoZone] = [
    CairoZone("Downtown Cairo",       "district",      30.0444, 31.2357, 0.06),
    CairoZone("Maadi",                "district",      30.0131, 31.2089, 0.09),
    CairoZone("Zamalek",              "district",      30.0598, 31.2214, 0.05),
    CairoZone("Heliopolis",           "district",      30.0912, 31.3217, 0.08),
    CairoZone("Nasr City",            "district",      30.0626, 31.3462, 0.09),
    CairoZone("New Cairo",            "district",      30.0274, 31.4745, 0.08),
    CairoZone("6th of October",       "district",      29.9602, 30.9304, 0.06),
    CairoZone("Giza",                 "district",      29.9870, 31.2118, 0.07),
    CairoZone("Mohandessin",          "district",      30.0594, 31.2024, 0.05),
    CairoZone("Dokki",                "district",      30.0381, 31.2124, 0.04),
    CairoZone("Shubra",               "district",      30.1100, 31.2480, 0.05),
    CairoZone("Ain Shams",            "district",      30.1191, 31.3272, 0.04),
    CairoZone("Cairo University",     "university",    30.0260, 31.2097, 0.06),
    CairoZone("AUC New Cairo",        "university",    30.0209, 31.4997, 0.04),
    CairoZone("Ain Shams University", "university",    30.1199, 31.3220, 0.02),
    CairoZone("Helwan University",    "university",    29.8421, 31.3340, 0.01),
    CairoZone("Smart Village",        "business_zone", 30.0730, 30.9710, 0.05),
    CairoZone("New Admin Capital",    "business_zone", 30.0130, 31.6990, 0.02),
    CairoZone("El Shorouk",           "district",      30.1296, 31.6318, 0.02),
    CairoZone("Madinaty",             "district",      30.0917, 31.6381, 0.02),
]

assert abs(sum(z.weight for z in ZONES) - 1.0) < 1e-9, "Zone weights must sum to 1.0"

zone_by_name: dict[str, CairoZone] = {z.name: z for z in ZONES}
