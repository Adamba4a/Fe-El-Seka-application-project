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

    async def _fake_award_driver_points(conn, driver_id, wallet_id, distance_fee_amount):
        return None

    monkeypatch.setattr(wallet_service, "get_wallet_with_lock", _fake_get_wallet_with_lock)
    monkeypatch.setattr(wallet_service, "insert_ledger_entry", _fake_insert_ledger_entry)
    monkeypatch.setattr(wallet_service, "decrement_balance", _fake_decrement_balance)
    monkeypatch.setattr(loyalty_service, "award_driver_points", _fake_award_driver_points)
    return entries


class TestDeductCommissionWithMarkup:
    async def test_commission_includes_markup_term(self, captured_ledger_entries):
        # fuel_cost=17.12, distance_fee=3.00, safety_margin=5.00, total_seats=2
        # cost-basis per_seat = (17.12*0.20 + 3.00 + 5.00) / 2 = (3.424 + 8.00) / 2 = 5.712
        # markup = (65.00 - 50.00) * 0.20 = 3.00 per seat
        # per_seat_commission = 5.712 + 3.00 = 8.712 -> commission for 1 seat = 8.71 (ROUND_HALF_UP)
        ride = _ride_row()
        booking = {"id": uuid.uuid4(), "seats": 1}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        assert len(captured_ledger_entries) == 1
        entry = captured_ledger_entries[0]
        assert entry["entry_type"] == "COMMISSION_DEBIT"
        assert entry["amount"] == Decimal("8.71")

    async def test_commission_scales_with_seats(self, captured_ledger_entries):
        ride = _ride_row()
        booking = {"id": uuid.uuid4(), "seats": 2}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        entry = captured_ledger_entries[0]
        # per_seat_commission (5.712 + 3.00 = 8.712) * 2 seats = 17.424 -> 17.42 (ROUND_HALF_UP)
        assert entry["amount"] == Decimal("17.42")

    async def test_no_markup_matches_pre_existing_cost_basis_commission(self, captured_ledger_entries):
        ride = _ride_row(price_per_seat="50.00", fair_price_per_seat="50.00")
        booking = {"id": uuid.uuid4(), "seats": 1}

        await commission_service.deduct_commission(conn=None, ride=ride, confirmed_bookings=[booking])

        entry = captured_ledger_entries[0]
        assert entry["amount"] == Decimal("5.71")
