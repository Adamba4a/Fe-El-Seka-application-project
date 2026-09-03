from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

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

    def __init__(
        self,
        ride_row: dict,
        updated_row: dict | None = None,
        wallet_row: dict | None = None,
        reservation_row: dict | None = None,
    ):
        self._ride_row = ride_row
        self._updated_row = updated_row or ride_row
        # Default wallet/reservation reflect the no-markup cost-basis reservation create_ride
        # would have made for this fixture's default fuel/distance/safety values
        # (17.0*0.20 + 3.0 + 5.0 = 11.40) — override per-test to exercise other cases.
        self._wallet_row = wallet_row or {
            "id": uuid.uuid4(),
            "driver_id": ride_row["driver_id"],
            "balance_egp": "1000.00",
            "reserved_egp": "11.40",
        }
        self._reservation_row = (
            reservation_row if reservation_row is not None else {"reserved_amount_egp": "11.40"}
        )
        self.update_args: tuple | None = None
        self.update_query: str | None = None
        self.execute_calls: list[tuple[str, tuple]] = []

    async def execute(self, query, *args):
        self.execute_calls.append((query.strip(), args))
        return None

    async def fetch(self, query, *args):
        return []

    async def fetchrow(self, query, *args):
        q = query.strip()
        if q.startswith("SELECT") and "FROM rides WHERE id = $1" in q:
            return self._ride_row
        if q.startswith("UPDATE rides"):
            self.update_query = q
            self.update_args = args
            return self._updated_row
        if "FROM driver_wallets" in q:
            return self._wallet_row
        if "FROM commission_reservations" in q:
            return self._reservation_row
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
        "departure_datetime": datetime.now(timezone.utc) + timedelta(hours=12),
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
        "group_id": None,
    }
    row.update(overrides)
    return row


async def _edit(
    monkeypatch,
    ride_row,
    updated_row=None,
    wallet_row=None,
    reservation_row=None,
    **payload_overrides,
):
    conn = _FakeConn(
        ride_row, updated_row=updated_row, wallet_row=wallet_row, reservation_row=reservation_row
    )
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
    # to a fixed 14.00 (per-seat split is by FARE_SPLIT_SEATS, not total_seats), so the
    # recomputed band is always [14.00, 18.00] regardless of the new total_seats value.

    async def test_old_price_still_in_band_kept_unchanged(self, monkeypatch):
        row = _ride_row(price_per_seat="16.00", fair_price_per_seat="14.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "total_seats": 3},
            total_seats=3,
        )
        assert ride.price_per_seat == "16.00"

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
            updated_row={**row, "total_seats": 3, "price_per_seat": "15.00", "fair_price_per_seat": "14.00"},
            total_seats=3,
            final_price_per_seat=15.0,
        )
        assert ride.price_per_seat == "15.00"


# ── edit_ride: commission reservation must move with price/seat edits (bug fix) ──
# Without this, a driver could create a ride at the fair price (small reservation,
# passes the balance check), then edit up to the max price — deduct_commission would
# later charge the higher markup-inclusive commission without it ever having been
# validated against, or held out of, the driver's wallet balance.


class TestReservationSync:
    async def test_price_increase_grows_reservation_and_wallet_hold(self, monkeypatch):
        row = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "price_per_seat": "60.00"},
            reservation_row={"reserved_amount_egp": "12.00"},
            wallet_row={"id": uuid.uuid4(), "balance_egp": "1000.00", "reserved_egp": "12.00"},
            final_price_per_seat=60.0,
        )
        assert ride.price_per_seat == "60.00"

        # cost-basis 12.00 + markup (60.00-50.00)*0.20*2 seats = 4.00 -> new reservation 16.00
        reservation_updates = [
            (q, a) for q, a in conn.execute_calls if "UPDATE commission_reservations" in q
        ]
        assert len(reservation_updates) == 1
        assert reservation_updates[0][1][1] == Decimal("16.00")

        reserved_increments = [
            (q, a) for q, a in conn.execute_calls if "reserved_egp = reserved_egp +" in q
        ]
        assert len(reserved_increments) == 1
        assert reserved_increments[0][1][1] == Decimal("4.00")

    async def test_price_decrease_shrinks_reservation_and_wallet_hold(self, monkeypatch):
        row = _ride_row(price_per_seat="65.00", fair_price_per_seat="50.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "price_per_seat": "50.00"},
            reservation_row={"reserved_amount_egp": "18.00"},
            wallet_row={"id": uuid.uuid4(), "balance_egp": "1000.00", "reserved_egp": "18.00"},
            final_price_per_seat=50.0,
        )
        assert ride.price_per_seat == "50.00"

        # markup drops to 0 -> new reservation 12.00 (cost-basis only)
        reservation_updates = [
            (q, a) for q, a in conn.execute_calls if "UPDATE commission_reservations" in q
        ]
        assert len(reservation_updates) == 1
        assert reservation_updates[0][1][1] == Decimal("12.00")

        reserved_decrements = [
            (q, a) for q, a in conn.execute_calls if "reserved_egp = GREATEST" in q
        ]
        assert len(reserved_decrements) == 1
        assert reserved_decrements[0][1][1] == Decimal("6.00")

    async def test_price_increase_blocked_by_insufficient_balance(self, monkeypatch):
        from fastapi import HTTPException

        row = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00", total_seats=2)
        with pytest.raises(HTTPException) as exc_info:
            await _edit(
                monkeypatch,
                row,
                updated_row={**row, "price_per_seat": "60.00"},
                reservation_row={"reserved_amount_egp": "11.40"},
                # available = 15.00 - 11.40 = 3.60, but the price bump needs +4.00
                wallet_row={"id": uuid.uuid4(), "balance_egp": "15.00", "reserved_egp": "11.40"},
                final_price_per_seat=60.0,
            )
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["error"] == "INSUFFICIENT_WALLET_BALANCE"

    async def test_seat_increase_alone_grows_reservation(self, monkeypatch):
        # No price override supplied — total_seats alone changes the markup term's
        # multiplier (price stays at the recomputed fair price, so markup is still 0,
        # but the cost-basis fuel/distance/safety total is recomputed too).
        row = _ride_row(price_per_seat="14.00", fair_price_per_seat="14.00", total_seats=2)
        ride, conn = await _edit(
            monkeypatch,
            row,
            updated_row={**row, "total_seats": 3},
            reservation_row={"reserved_amount_egp": "11.40"},
            wallet_row={"id": uuid.uuid4(), "balance_egp": "1000.00", "reserved_egp": "11.40"},
            total_seats=3,
        )
        assert ride.total_seats == 3

        reservation_updates = [
            (q, a) for q, a in conn.execute_calls if "UPDATE commission_reservations" in q
        ]
        assert len(reservation_updates) == 1
