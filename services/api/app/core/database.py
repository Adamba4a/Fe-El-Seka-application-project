from __future__ import annotations

import asyncio
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None  # type: ignore[type-arg]


async def create_pool(database_url: str) -> asyncpg.Pool:  # type: ignore[type-arg]
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)
    return _pool


def get_pool() -> asyncpg.Pool:  # type: ignore[type-arg]
    if _pool is None:
        raise RuntimeError("Database pool not initialized — call create_pool() first")
    return _pool


async def ping(pool: asyncpg.Pool) -> bool:  # type: ignore[type-arg]
    """Probe the database with a 500 ms timeout. Returns True if reachable."""
    try:
        async with asyncio.timeout(0.5):
            await pool.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning("Database probe failed: %s", e)
        return False


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
