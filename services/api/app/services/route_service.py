from __future__ import annotations

import httpx

from app.core.config import settings
from app.models.route import GeoPoint, RouteGeometry


class RouteServiceUnavailableError(Exception):
    pass


_http_client = httpx.AsyncClient(
    base_url=settings.osrm_url,
    timeout=10.0,
)


async def calculate_route(origin: GeoPoint, destination: GeoPoint) -> RouteGeometry:
    url = (
        f"/route/v1/driving/"
        f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
    )
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}
    try:
        response = await _http_client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise RouteServiceUnavailableError(str(exc)) from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        return RouteGeometry(
            is_routable=False,
            distance_km=0.0,
            duration_minutes=0,
            geojson_linestring={},
        )

    route = data["routes"][0]
    return RouteGeometry(
        is_routable=True,
        distance_km=round(route["distance"] / 1000, 3),
        duration_minutes=round(route["duration"] / 60),
        geojson_linestring=route["geometry"],
    )
