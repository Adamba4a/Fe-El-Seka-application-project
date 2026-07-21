from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None  # type: ignore[type-arg]


async def _init_connection(conn: asyncpg.Connection) -> None:  # type: ignore[type-arg]
    """Register JSON/JSONB codecs so Python dicts are accepted for JSONB columns."""
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(database_url: str) -> asyncpg.Pool:  # type: ignore[type-arg]
    global _pool
    if _pool is not None:
        return _pool
    # statement_cache_size=0: Supabase's transaction-mode pgbouncer pooler
    # (port 6543) hands out a different backend connection per query, so
    # asyncpg's per-connection prepared-statement cache goes stale and
    # raises "prepared statement already exists" — disable it entirely.
    _pool = await asyncpg.create_pool(
        database_url, min_size=1, max_size=10, init=_init_connection, statement_cache_size=0
    )
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
