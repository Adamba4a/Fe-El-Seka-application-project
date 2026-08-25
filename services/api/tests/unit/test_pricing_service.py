from __future__ import annotations

import pytest

from app.services import pricing_service as svc

# ── calculate_max_price: capped markup band (Spec 023, research.md §1) ──────


class TestCalculateMaxPrice:
    def test_applies_thirty_percent_markup_rounded(self):
        assert svc.calculate_max_price(50.0) == 65.0

    @pytest.mark.parametrize(
        "fair_price,expected_max",
        [
            (10.0, 13.0),
            (33.0, 43.0),  # 42.9 rounds to 43
            (100.0, 130.0),
            (1.0, 1.0),  # 1.3 rounds to 1 (banker's-adjacent, matches bare round())
        ],
    )
    def test_matches_fair_price_rounding_convention(self, fair_price, expected_max):
        assert svc.calculate_max_price(fair_price) == expected_max

    def test_zero_fair_price_yields_zero_max(self):
        assert svc.calculate_max_price(0.0) == 0.0

    def test_returns_float(self):
        assert isinstance(svc.calculate_max_price(50.0), float)
