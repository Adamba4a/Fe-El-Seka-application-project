from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.database import get_pool
from app.models.route import FareEstimateResponse

logger = logging.getLogger(__name__)

FUEL_EFFICIENCY_KM_PER_L: float = 13.0
PLATFORM_COMMISSION_RATE: float = 0.20

_DEFAULTS: dict[str, Any] = {
    "fuel_price_per_litre": 15.00,
    "safety_margin": 5.00,
    "corridor_buffer_radius_m": 500,
    "min_overlap_pct": 30.00,
    "max_pickup_walk_m": 1500,
    "max_dropoff_walk_m": 1500,
    "max_detour_km": 3.00,
    "max_detour_minutes": 10,
    "max_premium_detour_km": 5.00,
    "time_window_minutes": 30,
}

_config_cache: dict[str, Any] = dict(_DEFAULTS)
_config_lock = asyncio.Lock()
_config_loaded: bool = False


async def _refresh_pricing_config() -> None:
    global _config_loaded
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM pricing_config LIMIT 1")
    if row is None:
        logger.warning("pricing_config table is empty — keeping current cache")
        return
    async with _config_lock:
        _config_cache.clear()
        _config_cache.update(dict(row))
        _config_loaded = True


async def init_pricing_config() -> None:
    """Best-effort initial load at startup. Falls back to hardcoded defaults if DB
    table does not exist yet (e.g. migration pending). Background loop retries."""
    try:
        await _refresh_pricing_config()
        logger.info(
            "pricing_config loaded from DB: fuel=%.2f EGP/L safety=%.2f EGP",
            _config_cache.get("fuel_price_per_litre", 0),
            _config_cache.get("safety_margin", 0),
        )
    except Exception as exc:
        logger.warning(
            "pricing_config unavailable at startup (%s) — using defaults. "
            "Apply migrations and the background loop will sync within 30s.",
            exc,
        )


async def pricing_config_refresh_loop() -> None:
    """Background task: refresh pricing_config cache every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await _refresh_pricing_config()
        except Exception as exc:
            logger.error("pricing_config refresh error: %s", exc)


def get_pricing_config() -> dict[str, Any]:
    if not _config_loaded:
        logger.warning("pricing_config not yet loaded from DB — using hardcoded defaults")
    return dict(_config_cache)


def _calc_fee_from_distance(distance_km: float, seat_count: int) -> dict[str, float]:
    config = get_pricing_config()
    fuel_price = float(config["fuel_price_per_litre"])
    safety = float(config["safety_margin"])

    fuel_cost = (distance_km / FUEL_EFFICIENCY_KM_PER_L) * fuel_price
    commission = fuel_cost * PLATFORM_COMMISSION_RATE
    per_seat = round((fuel_cost + commission + safety) / seat_count)
    total = per_seat * seat_count

    return {
        "fuel_cost_egp": round(fuel_cost, 2),
        "platform_commission_egp": round(commission, 2),
        "safety_margin_egp": round(safety, 2),
        "per_seat_price_egp": float(per_seat),
        "total_collected_egp": float(total),
    }


def calculate_fare(distance_km: float, seat_count: int) -> FareEstimateResponse:
    config = get_pricing_config()
    fees = _calc_fee_from_distance(distance_km, seat_count)
    logger.info(
        "calculate_fare distance_km=%.3f fuel_price=%.2f seat_count=%d per_seat=%.2f",
        distance_km,
        float(config["fuel_price_per_litre"]),
        seat_count,
        fees["per_seat_price_egp"],
    )
    return FareEstimateResponse(
        distance_km=round(distance_km, 2),
        fuel_price_per_litre_egp=float(config["fuel_price_per_litre"]),
        seat_count=seat_count,
        **fees,
    )


def calculate_premium_detour_fee(detour_km: float) -> float:
    """Fee for a single premium pickup or dropoff detour — per passenger, not split."""
    fees = _calc_fee_from_distance(detour_km, seat_count=1)
    return fees["per_seat_price_egp"]


def calculate_premium_fare_addition(
    pickup_detour_km: float,
    dropoff_detour_km: float,
) -> dict:
    """Per-passenger premium fee breakdown for optional pickup and/or dropoff detours."""
    return {
        "premium_pickup_fee_egp": calculate_premium_detour_fee(pickup_detour_km),
        "premium_dropoff_fee_egp": calculate_premium_detour_fee(dropoff_detour_km),
    }
