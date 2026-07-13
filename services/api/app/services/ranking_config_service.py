from __future__ import annotations

import asyncio
import logging
import random
from typing import Optional

from app.core.database import get_pool

logger = logging.getLogger(__name__)

_DEFAULTS: dict[str, float] = {
    "exploration_rate": 0.125,
}

_config_cache: dict[str, float] = dict(_DEFAULTS)
_config_lock = asyncio.Lock()
_config_loaded: bool = False


async def _refresh_ranking_config() -> None:
    global _config_loaded
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM ranking_config LIMIT 1")
    if row is None:
        logger.warning("ranking_config table is empty — keeping current cache")
        return
    async with _config_lock:
        _config_cache["exploration_rate"] = float(row["exploration_rate"])
        _config_loaded = True


async def init_ranking_config() -> None:
    """Best-effort initial load at startup. Falls back to hardcoded defaults if DB
    table does not exist yet (e.g. migration pending). Background loop retries."""
    try:
        await _refresh_ranking_config()
        logger.info(
            "ranking_config loaded from DB: exploration_rate=%.4f",
            _config_cache["exploration_rate"],
        )
    except Exception as exc:
        logger.warning(
            "ranking_config unavailable at startup (%s) — using defaults. "
            "Apply migrations and the background loop will sync within 30s.",
            exc,
        )


async def ranking_config_refresh_loop() -> None:
    """Background task: refresh ranking_config cache every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await _refresh_ranking_config()
        except Exception as exc:
            logger.error("ranking_config refresh error: %s", exc)


def get_exploration_rate() -> float:
    if not _config_loaded:
        logger.warning("ranking_config not yet loaded from DB — using hardcoded default")
    return _config_cache["exploration_rate"]


def apply_exploration(ranked_candidates: list) -> tuple[list, Optional[str]]:
    """Single-swap epsilon-greedy (research.md R2): with probability
    get_exploration_rate(), promote one uniformly-random candidate from
    positions 2..N (index 1..len-1) to position 1 (index 0), shifting
    intervening candidates down by one. Only reorders candidates that already
    passed feasibility gating upstream — never adds or removes candidates
    (FR-009). Returns (possibly-reordered list, promoted candidate's ride_id
    as str, or None if no swap occurred)."""
    if len(ranked_candidates) < 2:
        return ranked_candidates, None
    if random.random() >= get_exploration_rate():
        return ranked_candidates, None

    idx = random.randint(1, len(ranked_candidates) - 1)
    promoted = ranked_candidates[idx]
    reordered = [promoted] + ranked_candidates[:idx] + ranked_candidates[idx + 1:]
    return reordered, str(promoted.ride_id)
