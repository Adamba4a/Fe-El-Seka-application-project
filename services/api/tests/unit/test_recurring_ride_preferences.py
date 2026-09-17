from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.services.recurring_ride_service import (
    RecurringRideServiceError,
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
