from datetime import datetime, time, timezone

from app.services.recurring_ride_service import _active_week_dates, _active_week_start


def _definition(*weekdays: int) -> dict:
    return {"weekdays": list(weekdays), "departure_time": time(7, 15)}


def test_active_week_includes_only_this_sunday_through_saturday():
    now = datetime(2026, 9, 20, 5, 0, tzinfo=timezone.utc)  # Sunday before departure

    assert _active_week_start(_definition(7, 1, 2, 3, 4), now).isoformat() == "2026-09-20"
    assert [day.isoformat() for day in _active_week_dates(_definition(7, 1, 2, 3, 4), now)] == [
        "2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24",
    ]


def test_next_week_opens_only_after_the_final_departure():
    now = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)  # Thursday after 07:15, Friday/Saturday are off

    assert _active_week_start(_definition(7, 1, 2, 3, 4), now).isoformat() == "2026-09-27"
