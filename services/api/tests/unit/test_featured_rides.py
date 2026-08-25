from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services import ride_service as svc

# ── Fakes matching the pattern in test_dataset_pipeline_service.py ──────────


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeConn:
    def __init__(self, fetch_rows=None):
        self._fetch_rows = fetch_rows or []
        self.executed_queries: list[str] = []

    async def fetch(self, query, *args):
        self.executed_queries.append(query)
        return self._fetch_rows


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


def _row(**overrides):
    base = {
        "id": uuid4(),
        "origin_address": "Maadi, Cairo",
        "destination_address": "Nasr City, Cairo",
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=2),
        "price_per_seat": Decimal("120.00"),
        "available_seats": 3,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
class TestListFeaturedRides:
    async def test_returns_empty_list_when_no_rows(self, monkeypatch):
        conn = _FakeConn(fetch_rows=[])
        monkeypatch.setattr(svc, "get_pool", lambda: _FakePool(conn))

        result = await svc.list_featured_rides()

        assert result.rides == []

    async def test_maps_rows_to_featured_ride_items(self, monkeypatch):
        row = _row()
        conn = _FakeConn(fetch_rows=[row])
        monkeypatch.setattr(svc, "get_pool", lambda: _FakePool(conn))

        result = await svc.list_featured_rides()

        assert len(result.rides) == 1
        item = result.rides[0]
        assert item.ride_id == row["id"]
        assert item.origin_address == "Maadi, Cairo"
        assert item.destination_address == "Nasr City, Cairo"
        assert item.price_per_seat == "120.00"
        assert item.available_seats == 3

    async def test_query_filters_on_featured_scheduled_future_and_seats(self, monkeypatch):
        # FR-003/FR-004/FR-012: the eligibility filter is enforced in SQL, not
        # in Python post-processing — assert the query text encodes it so a
        # future refactor can't accidentally drop a clause.
        conn = _FakeConn(fetch_rows=[])
        monkeypatch.setattr(svc, "get_pool", lambda: _FakePool(conn))

        await svc.list_featured_rides()

        query = conn.executed_queries[0]
        assert "is_featured = true" in query
        assert "status = 'scheduled'" in query
        assert "departure_datetime > now()" in query
        assert "available_seats > 0" in query
        assert "ORDER BY departure_datetime ASC" in query
