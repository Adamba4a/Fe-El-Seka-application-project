from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services import commission_service, loyalty_service, wallet_service

# ── commission scales with driver markup (Spec 023, Phase 7 / FR-011) ───────


def _ride_row(**overrides) -> dict:
    row = {
        "id": uuid.uuid4(),
        "driver_id": uuid.uuid4(),
        "total_seats": 2,
        "fuel_cost_egp": "17.12",
        "distance_fee_egp": "3.00",
        "safety_margin_egp": "5.00",
        "price_per_seat": "65.00",
        "fair_price_per_seat": "50.00",
    }
    row.update(overrides)
    return row


@pytest.fixture
def captured_ledger_entries(monkeypatch):
    entries = []

    async def _fake_get_wallet_with_lock(conn, driver_id):
        return {"id": uuid.uuid4(), "balance_egp": "1000.00", "reserved_egp": "0.00"}

    async def _fake_insert_ledger_entry(conn, **kwargs):
        entries.append(kwargs)

    async def _fake_decrement_balance(conn, wallet_id, amount):
        return None

    async def _fake_increment_cash_back_points(conn, wallet_id, amount):
        return None

    async def _fake_award_passenger_points(conn, passenger_id, booking_id, ride_id, commission_egp):
        return None

    monkeypatch.setattr(wallet_service, "get_wallet_with_lock", _fake_get_wallet_with_lock)
    monkeypatch.setattr(wallet_service, "insert_ledger_entry", _fake_insert_ledger_entry)
    monkeypatch.setattr(wallet_service, "decrement_balance", _fake_decrement_balance)
    monkeypatch.setattr(wallet_service, "increment_cash_back_points", _fake_increment_cash_back_points)
    monkeypatch.setattr(loyalty_service, "award_passenger_points", _fake_award_passenger_points)
    return entries


class TestDeductCommissionWithMarkup:
    async def test_commission_includes_markup_term(self, captured_ledger_entries):
        # fuel_cost=17.12, distance_fee=3.00, safety_margin=5.00 (legacy ride), total_seats=2
        # cost-basis per_seat = (3.00 + 5.00 + (17.12 + 3.00) * 0.20) / 2 = (8.00 + 4.024) / 2 = 6.012
        # markup = (65.00 - 50.00) * 0.20 = 3.00 per seat
        # per_seat_commission = 6.012 + 3.00 = 9.012 -> commission for 1 seat = 9.01 (ROUND_HALF_UP)
        ride = _ride_row()
        booking = {"id": uuid.uuid4(), "passenger_id": uuid.uuid4(), "seats": 1}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        assert len(captured_ledger_entries) == 2
        entry = captured_ledger_entries[0]
        assert entry["entry_type"] == "COMMISSION_DEBIT"
        assert entry["amount"] == Decimal("9.01")
        # distance_fee_egp=3.00 / FARE_SPLIT_SEATS=2 * 1 seat = 1.50, credited back as Cash Back
        cash_back = captured_ledger_entries[1]
        assert cash_back["entry_type"] == "CASH_BACK_CREDIT"
        assert cash_back["amount"] == Decimal("1.50")

    async def test_commission_scales_with_seats(self, captured_ledger_entries):
        ride = _ride_row()
        booking = {"id": uuid.uuid4(), "passenger_id": uuid.uuid4(), "seats": 2}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        entry = captured_ledger_entries[0]
        # per_seat_commission (6.012 + 3.00 = 9.012) * 2 seats = 18.024 -> 18.02 (ROUND_HALF_UP)
        assert entry["amount"] == Decimal("18.02")
        cash_back = captured_ledger_entries[1]
        assert cash_back["entry_type"] == "CASH_BACK_CREDIT"
        # distance_fee_egp=3.00 / 2 * 2 seats = 3.00
        assert cash_back["amount"] == Decimal("3.00")

    async def test_no_markup_matches_pre_existing_cost_basis_commission(self, captured_ledger_entries):
        ride = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00")
        booking = {"id": uuid.uuid4(), "passenger_id": uuid.uuid4(), "seats": 1}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        entry = captured_ledger_entries[0]
        assert entry["amount"] == Decimal("6.01")
        cash_back = captured_ledger_entries[1]
        assert cash_back["entry_type"] == "CASH_BACK_CREDIT"
        assert cash_back["amount"] == Decimal("1.50")
