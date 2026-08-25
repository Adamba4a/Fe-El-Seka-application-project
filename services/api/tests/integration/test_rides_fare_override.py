from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.ride import CreateRideRequest, LocationSchema
from app.services import commission_service, ride_service, wallet_service

# ── create_ride: driver-chosen final price (Spec 023, US1) ──────────────────


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc_info):
        return False


class _FakeTransactionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc_info):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _FakeAcquireCtx(self._conn)


class _FakeConn:
    """Routes fetchrow/execute by matching a distinctive substring of the query
    text, same convention as test_continuous_learning_flow.py."""

    def __init__(self, ride_row: dict):
        self._ride_row = ride_row
        self.insert_ride_args: tuple | None = None

    async def execute(self, query, *args):
        return None

    async def fetchrow(self, query, *args):
        if "pg_advisory_xact_lock" in query:
            return None
        if "SELECT id FROM rides" in query:
            return None  # no conflicting ride
        if "INSERT INTO rides" in query:
            self.insert_ride_args = args
            return self._ride_row
        raise AssertionError(f"Unmatched fetchrow query: {query}")

    def transaction(self):
        return _FakeTransactionCtx()


def _ride_row(**overrides) -> dict:
    row = {
        "id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "vehicle_id": uuid.uuid4(),
        "origin_lat": 30.0131,
        "origin_lng": 31.2089,
        "origin_address": "A",
        "dest_lat": 30.0626,
        "dest_lng": 31.3462,
        "destination_address": "B",
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
        "total_seats": 2,
        "booked_seats": 0,
        "available_seats": 2,
        "price_per_seat": "50.00",
        "fair_price_per_seat": "50.00",
        "status": "scheduled",
        "cancellation_reason": None,
        "cancellation_source": None,
        "notes": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "route_distance_km": 10.0,
        "route_duration_minutes": 20,
        "fuel_cost_egp": 17.0,
        "platform_commission_egp": 3.4,
        "distance_fee_egp": 3.0,
        "safety_margin_egp": 5.0,
        "price_source": "system",
        "started_at": None,
        "completed_at": None,
        "route_geometry_geojson": json.dumps({"type": "LineString", "coordinates": []}),
    }
    row.update(overrides)
    return row


def _payload(**overrides) -> CreateRideRequest:
    data = {
        "origin": LocationSchema(coordinates={"lat": 30.0131, "lng": 31.2089}, address="A"),
        "destination": LocationSchema(coordinates={"lat": 30.0626, "lng": 31.3462}, address="B"),
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=3),
        "total_seats": 2,
    }
    data.update(overrides)
    return CreateRideRequest(**data)


@pytest.fixture(autouse=True)
def _stub_wallet_and_commission(monkeypatch):
    async def _fake_get_wallet_with_lock(conn, driver_id):
        return {"id": uuid.uuid4(), "balance_egp": "1000.00", "reserved_egp": "0.00"}

    async def _fake_create_reservation(conn, wallet_id, driver_id, ride_id, amount):
        return None

    monkeypatch.setattr(wallet_service, "get_wallet_with_lock", _fake_get_wallet_with_lock)
    monkeypatch.setattr(commission_service, "check_available_balance", lambda wallet, amount: True)
    monkeypatch.setattr(commission_service, "create_reservation", _fake_create_reservation)


class TestCreateRideDefaultsToFairPrice:
    async def test_no_final_price_persists_fair_price_as_price_per_seat(self, monkeypatch):
        row = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00")
        conn = _FakeConn(row)
        monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(conn))

        payload = _payload()
        ride = await ride_service.create_ride(
            driver_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            vehicle_seat_count=4,
            payload=payload,
            route_geometry_geojson={"type": "LineString", "coordinates": []},
            route_distance_km=10.0,
            route_duration_minutes=20,
            fuel_cost_egp=17.0,
            platform_commission_egp=3.4,
            distance_fee_egp=3.0,
            safety_margin_egp=5.0,
            fair_price_per_seat=50.0,
        )

        # price_per_seat ($9) and fair_price_per_seat ($10) args to the INSERT
        assert conn.insert_ride_args[8] == 50.0
        assert conn.insert_ride_args[9] == 50.0
        assert ride.price_per_seat == ride.fair_price_per_seat == "50.00"


class TestCreateRideWithDriverChosenPrice:
    async def test_mid_band_price_persisted_exactly(self, monkeypatch):
        row = _ride_row(price_per_seat="60.00", fair_price_per_seat="50.00")
        conn = _FakeConn(row)
        monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(conn))

        payload = _payload(final_price_per_seat=60.0)
        ride = await ride_service.create_ride(
            driver_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            vehicle_seat_count=4,
            payload=payload,
            route_geometry_geojson={"type": "LineString", "coordinates": []},
            route_distance_km=10.0,
            route_duration_minutes=20,
            fuel_cost_egp=17.0,
            platform_commission_egp=3.4,
            distance_fee_egp=3.0,
            safety_margin_egp=5.0,
            fair_price_per_seat=50.0,
            final_price_per_seat=payload.final_price_per_seat,
        )

        assert conn.insert_ride_args[8] == 60.0
        assert conn.insert_ride_args[9] == 50.0
        assert ride.price_per_seat == "60.00"
        assert ride.fair_price_per_seat == "50.00"
