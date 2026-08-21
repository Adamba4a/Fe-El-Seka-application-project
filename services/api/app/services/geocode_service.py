from __future__ import annotations

import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_http_client = httpx.AsyncClient(
    base_url=settings.nominatim_url,
    timeout=5.0,
    headers={"User-Agent": settings.nominatim_user_agent, "Accept-Language": "en"},
)

# Reverse-geocode results are keyed by coordinates rounded to ~11m precision —
# a pin dropped near a previous lookup (or re-opened on the same screen) is
# served from cache instead of round-tripping to Nominatim again. This is the
# main lever against the mobile-network latency that made the pin-drop flow
# feel slow: repeat lookups (e.g. re-editing a ride) become instant.
_CACHE_TTL_SECONDS = 3600
_reverse_cache: dict[tuple[float, float], tuple[float, dict]] = {}


class GeocodeServiceUnavailableError(Exception):
    pass


def _cache_key(lat: float, lng: float) -> tuple[float, float]:
    return (round(lat, 4), round(lng, 4))


async def reverse_geocode(lat: float, lng: float) -> dict:
    """Reverse-geocode a point to its address. Raises GeocodeServiceUnavailableError on failure."""
    key = _cache_key(lat, lng)
    cached = _reverse_cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = await _http_client.get(
            "/reverse", params={"lat": lat, "lon": lng, "format": "json"}
        )
    except httpx.RequestError as exc:
        logger.error("Nominatim reverse-geocode request error: %s", exc)
        raise GeocodeServiceUnavailableError(str(exc)) from exc
    if response.status_code >= 400:
        logger.error("Nominatim reverse-geocode returned HTTP %d", response.status_code)
        raise GeocodeServiceUnavailableError(f"Nominatim returned HTTP {response.status_code}")

    data = response.json()
    result = {
        "address": data.get("display_name"),
        "boundingbox": data.get("boundingbox"),
        "address_parts": data.get("address"),
    }
    _reverse_cache[key] = (now, result)
    return result


async def search_address(query: str) -> dict | None:
    """Forward-geocode a free-text query, bounded to Greater Cairo. Returns None if no match."""
    params = {
        "format": "json",
        "q": query,
        "limit": "1",
        "countrycodes": "eg",
        "viewbox": "30.7,30.5,32.2,29.7",
        "bounded": "1",
    }
    try:
        response = await _http_client.get("/search", params=params)
        if response.status_code < 400:
            results = response.json()
            if results:
                return results[0]
        # Bounded search found nothing — retry without the viewbox constraint.
        fallback_params = {"format": "json", "q": query, "limit": "1", "countrycodes": "eg"}
        response = await _http_client.get("/search", params=fallback_params)
    except httpx.RequestError as exc:
        logger.error("Nominatim search request error: %s", exc)
        raise GeocodeServiceUnavailableError(str(exc)) from exc
    if response.status_code >= 400:
        logger.error("Nominatim search returned HTTP %d", response.status_code)
        raise GeocodeServiceUnavailableError(f"Nominatim returned HTTP {response.status_code}")
    results = response.json()
    return results[0] if results else None
