from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

from app.core.database import get_pool

# NUMERIC columns come back from asyncpg as decimal.Decimal; cast to float so
# they interoperate with plain-float ML scores downstream (matches
# pricing_service.py / ranking_config_service.py convention).
_DECIMAL_FIELDS = ("promotion_margin", "rollback_margin", "alert_baseline_margin")

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, Any] = {
    "min_dataset_size": 500,
    "retraining_cadence_hours": 168,
    "promotion_margin": 0.0200,
    "shadow_burnin_hours": 168,
    "rollout_step_pcts": [5, 25, 50, 100],
    "rollout_step_hold_hours": 24,
    "rollback_margin": 0.0500,
    "monitoring_interval_hours": 1,
    "alert_baseline_margin": 0.1000,
    "spot_audit_sample_size": 10,
    "spot_audit_frequency_hours": 24,
    "spot_audit_early_window_hours": 72,
}

_config_cache: dict[str, Any] = dict(_DEFAULTS)
_config_lock = asyncio.Lock()
_config_loaded: bool = False


async def _refresh_continuous_learning_config() -> None:
    global _config_loaded
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM continuous_learning_config LIMIT 1")
    if row is None:
        logger.warning("continuous_learning_config table is empty — keeping current cache")
        return
    row_dict = dict(row)
    row_dict.pop("id", None)
    row_dict.pop("updated_at", None)
    for field in _DECIMAL_FIELDS:
        if field in row_dict and row_dict[field] is not None:
            row_dict[field] = float(row_dict[field])
    async with _config_lock:
        _config_cache.clear()
        _config_cache.update(row_dict)
        _config_loaded = True


async def init_continuous_learning_config() -> None:
    """Best-effort initial load at startup. Falls back to hardcoded defaults if DB
    table does not exist yet (e.g. migration pending). Background loop retries."""
    try:
        await _refresh_continuous_learning_config()
        logger.info(
            "continuous_learning_config loaded from DB: min_dataset_size=%s "
            "retraining_cadence_hours=%s promotion_margin=%.4f",
            _config_cache.get("min_dataset_size"),
            _config_cache.get("retraining_cadence_hours"),
            _config_cache.get("promotion_margin", 0),
        )
    except Exception as exc:
        logger.warning(
            "continuous_learning_config unavailable at startup (%s) — using defaults. "
            "Apply migrations and the background loop will sync within 30s.",
            exc,
        )


async def continuous_learning_config_refresh_loop() -> None:
    """Background task: refresh continuous_learning_config cache every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await _refresh_continuous_learning_config()
        except Exception as exc:
            logger.error("continuous_learning_config refresh error: %s", exc)


def get_continuous_learning_config() -> dict[str, Any]:
    """Returns a deep copy so callers can freely index/mutate the result
    (e.g. rollout_step_pcts is a list) without corrupting the shared cache."""
    if not _config_loaded:
        logger.warning(
            "continuous_learning_config not yet loaded from DB — using hardcoded defaults"
        )
    return copy.deepcopy(_config_cache)
