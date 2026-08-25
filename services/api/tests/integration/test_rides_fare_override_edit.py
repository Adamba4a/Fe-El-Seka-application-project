from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.ride import EditRideRequest
from app.services import ride_service

# ── edit_ride: driver-chosen final price + edit-time re-banding (Spec 023, US3) ──


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
    """Routes fetchrow by matching a distinctive substring of the query text, same
    convention as test_rides_fare_override.py / test_continuous_learning_flow.py."""

    def __init__(self, ride_row: dict, updated_row: dict | None = None):
        self._ride_row = ride_row
        self._updated_row = updated_row or ride_row
        self.update_args: tuple | None = None
        self.update_query: str | None = None

    async def execute(self, query, *args):
        return None

    async def fetch(self, query, *args):
        return []

    async def fetchrow(self, query, *args):
        if query.strip().startswith("SELECT") and "FROM rides WHERE id = $1" in query:
            return self._ride_row
        if query.strip().startswith("UPDATE rides"):
            self.update_query = query
            self.update_args = args
            return self._updated_row
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
        "route_geometry_geojson": '{"type": "LineString", "coordinates": []}',
    }
    row.update(overrides)
    return row


async def _edit(monkeypatch, ride_row, updated_row=None, **payload_overrides):
    conn = _FakeConn(ride_row, updated_row=updated_row)
    monkeypatch.setattr(ride_service, "get_pool", lambda: _FakePool(conn))
    payload = EditRideRequest(**payload_overrides)
    ride = await ride_service.edit_ride(
        ride_id=ride_row["id"],
        driver_id=ride_row["driver_id"],
        payload=payload,
    )
    return ride, conn


class TestDirectPriceEdit:
    async def test_in_band_price_saved(self, monkeypatch):
        row = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00")
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "price_per_seat": "60.00"},
            final_price_per_seat=60.0,
        )
        assert ride.price_per_seat == "60.00"

    async def test_out_of_band_price_rejected(self, monkeypatch):
        with pytest.raises(ride_service.RideServiceError) as exc_info:
            await _edit(
                monkeypatch,
                _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00"),
                final_price_per_seat=100.0,
            )
        assert exc_info.value.code == "price_out_of_band"


class TestSeatCountRebanding:
    # distance_km=10.0 with hardcoded pricing defaults recomputes fair_price_per_seat
    # to a fixed 10.00 (per-seat split is by FARE_SPLIT_SEATS, not total_seats), so the
    # recomputed band is always [10.00, 13.00] regardless of the new total_seats value.

    async def test_old_price_still_in_band_kept_unchanged(self, monkeypatch):
        row = _ride_row(price_per_seat="12.00", fair_price_per_seat="10.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "total_seats": 3},
            total_seats=3,
        )
        assert ride.price_per_seat == "12.00"

    async def test_old_price_out_of_band_rejected_without_new_price(self, monkeypatch):
        # A large existing price (well above the recomputed fair*1.30 band) must be
        # rejected once total_seats changes and no replacement price is supplied.
        with pytest.raises(ride_service.RideServiceError) as exc_info:
            await _edit(
                monkeypatch,
                _ride_row(price_per_seat="1000.00", fair_price_per_seat="10.00", total_seats=2),
                total_seats=3,
            )
        assert exc_info.value.code == "price_out_of_band"

    async def test_old_price_out_of_band_succeeds_with_new_price(self, monkeypatch):
        row = _ride_row(price_per_seat="1000.00", fair_price_per_seat="10.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "total_seats": 3, "price_per_seat": "12.00", "fair_price_per_seat": "10.00"},
            total_seats=3,
            final_price_per_seat=12.0,
        )
        assert ride.price_per_seat == "12.00"
