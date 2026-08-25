from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.admin import rides_router
from app.dependencies.roles import get_current_admin
from app.main import app

# ── admin rides list/detail: fair price + markup visibility (Spec 023, US4) ──


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


class _FakeConn:
    def __init__(self, ride_row: dict, booking_rows: list | None = None, total: int = 1):
        self._ride_row = ride_row
        self._booking_rows = booking_rows or []
        self._total = total

    async def fetchval(self, query, *args):
        return self._total

    async def fetch(self, query, *args):
        if "FROM bookings" in query:
            return self._booking_rows
        return [self._ride_row]

    async def fetchrow(self, query, *args):
        return self._ride_row


def _ride_row(**overrides) -> dict:
    row = {
        "id": uuid.uuid4(),
        "status": "scheduled",
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
        "origin_address": "A",
        "destination_address": "B",
        "total_seats": 2,
        "booked_seats": 0,
        "available_seats": 2,
        "price_per_seat": "65.00",
        "fair_price_per_seat": "50.00",
        "notes": None,
        "cancellation_reason": None,
        "cancellation_source": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "driver_id": uuid.uuid4(),
        "driver_display_name": "Driver",
        "driver_email": "driver@example.com",
        "driver_rating_avg": None,
        "driver_rating_count": 0,
        "plate_number": "ABC123",
        "make": "Toyota",
        "model": "Corolla",
        "color": "White",
    }
    row.update(overrides)
    return row


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_current_admin, None)


@pytest.fixture(autouse=True)
def _override_admin():
    app.dependency_overrides[get_current_admin] = lambda: {"id": str(uuid.uuid4()), "role": "admin"}


class TestListRidesMarkupFields:
    def test_markup_fields_present_and_consistent(self, client, monkeypatch):
        row = _ride_row(price_per_seat="65.00", fair_price_per_seat="50.00")
        conn = _FakeConn(row)
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.get("/api/admin/rides/")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["fair_price_per_seat"] == "50.00"
        assert item["markup_egp"] == "15.00"
        assert item["markup_percentage"] == 30


class TestRideDetailMarkupFields:
    def test_markup_fields_present_and_consistent(self, client, monkeypatch):
        row = _ride_row(price_per_seat="60.00", fair_price_per_seat="50.00")
        conn = _FakeConn(row)
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.get(f"/api/admin/rides/{row['id']}")
        assert resp.status_code == 200
        ride = resp.json()["ride"]
        assert ride["fair_price_per_seat"] == "50.00"
        assert ride["markup_egp"] == "10.00"
        assert ride["markup_percentage"] == 20

    def test_no_markup_when_price_equals_fair(self, client, monkeypatch):
        row = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00")
        conn = _FakeConn(row)
        monkeypatch.setattr(rides_router, "get_pool", lambda: _FakePool(conn))

        resp = client.get(f"/api/admin/rides/{row['id']}")
        assert resp.status_code == 200
        ride = resp.json()["ride"]
        assert ride["markup_egp"] == "0.00"
        assert ride["markup_percentage"] == 0
