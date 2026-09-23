from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.services.recurring_ride_service import (
    RecurringRideServiceError,
    _active_week_start,
    override_round_trip_occurrence,
)


class TestRecurringRoundTripOccurrenceValidation:
    async def test_rejects_return_at_or_before_outbound_before_database_work(self):
        departure = datetime(2026, 9, 22, 18, 0, tzinfo=timezone.utc)

        with pytest.raises(RecurringRideServiceError) as exc_info:
            await override_round_trip_occurrence(
                uuid.uuid4(), uuid.uuid4(), "2026-09-22", departure, departure
            )

        assert exc_info.value.code == "return_departure_invalid"
        assert exc_info.value.status_code == 422

    async def test_rejects_times_outside_the_selected_occurrence_date(self):
        with pytest.raises(RecurringRideServiceError) as exc_info:
            await override_round_trip_occurrence(
                uuid.uuid4(), uuid.uuid4(), "2026-09-22",
                datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 9, 23, 18, 0, tzinfo=timezone.utc),
            )

        assert exc_info.value.code == "occurrence_date_invalid"


class TestRecurringWeekRollover:
    def test_round_trip_stays_in_current_week_until_return_leg_departs(self):
        definition = {
            "weekdays": [6],  # Saturday, the last day in the Sunday–Saturday week
            "departure_time": datetime.strptime("08:00", "%H:%M").time(),
            "journey_type": "round_trip",
            "return_departure_time": datetime.strptime("18:00", "%H:%M").time(),
        }

        # The outbound has departed, but the return ("coming") ride has not.
        now = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)

        assert _active_week_start(definition, now).isoformat() == "2026-09-20"
