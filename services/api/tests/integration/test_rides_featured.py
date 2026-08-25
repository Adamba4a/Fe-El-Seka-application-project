from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.services import ride_service


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

    async def fetch(self, query, *args):
        return self._fetch_rows


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_user, None)


class TestGetFeaturedRides:
    def test_authenticated_returns_featured_rides(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4())}
        row = {
            "id": uuid4(),
            "origin_address": "Maadi, Cairo",
            "destination_address": "Nasr City, Cairo",
            "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
            "price_per_seat": Decimal("120.00"),
            "available_seats": 2,
        }
        monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(_FakeConn([row])))

        resp = client.get("/api/v1/rides/featured")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rides"]) == 1
        assert body["rides"][0]["ride_id"] == str(row["id"])
        assert body["rides"][0]["price_per_seat"] == "120.00"

    def test_authenticated_empty_result_is_valid(self, client, monkeypatch):
        app.dependency_overrides[get_current_user] = lambda: {"id": str(uuid4())}
        monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(_FakeConn([])))

        resp = client.get("/api/v1/rides/featured")

        assert resp.status_code == 200
        assert resp.json() == {"rides": []}

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/rides/featured",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )

        assert resp.status_code == 401
