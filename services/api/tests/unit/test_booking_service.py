from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.services import booking_service

# ── shared fakes (same query-substring-routing convention as
# tests/unit/test_group_service.py) ──────────────────────────────────────────


class _FakeTransactionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc_info):
        return False


class _RoutedFakeConn:
    def __init__(self, fetchrow_rules=None):
        self._fetchrow_rules = fetchrow_rules or []

    def _resolve(self, rules, query):
        for substring, response in rules:
            if substring in query:
                return response() if callable(response) else response
        raise AssertionError(f"Unmatched query: {query}")

    async def fetchrow(self, query, *args):
        return self._resolve(self._fetchrow_rules, query)

    def transaction(self):
        return _FakeTransactionCtx()


def _ride_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "status": "scheduled",
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=1),
        "price_per_seat": 50,
        "booked_seats": 0,
        "total_seats": 4,
        "driver_id": uuid.uuid4(),
        "group_id": None,
    }
    row.update(overrides)
    return row


class TestCreateBookingSelfBookingGuard:
    async def test_driver_cannot_book_own_ride(self):
        driver_id = uuid.uuid4()
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM rides WHERE id", _ride_row(driver_id=driver_id))],
        )

        with pytest.raises(HTTPException) as exc_info:
            await booking_service.create_booking(
                conn,
                ride_id=uuid.uuid4(),
                passenger_id=driver_id,
                boarding_lat=30.0,
                boarding_lng=31.0,
                alighting_lat=30.1,
                alighting_lng=31.1,
                premium_pickup=False,
                premium_dropoff=False,
                premium_pickup_fee=None,
                premium_dropoff_fee=None,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "cannot_book_own_ride"

    async def test_missing_ride_still_returns_404_before_self_booking_check(self):
        conn = _RoutedFakeConn(
            fetchrow_rules=[("FROM rides WHERE id", None)],
        )

        with pytest.raises(HTTPException) as exc_info:
            await booking_service.create_booking(
                conn,
                ride_id=uuid.uuid4(),
                passenger_id=uuid.uuid4(),
                boarding_lat=30.0,
                boarding_lng=31.0,
                alighting_lat=30.1,
                alighting_lng=31.1,
                premium_pickup=False,
                premium_dropoff=False,
                premium_pickup_fee=None,
                premium_dropoff_fee=None,
            )

        assert exc_info.value.status_code == 404
