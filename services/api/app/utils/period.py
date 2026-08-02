from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

Period = Literal["today", "7d", "30d", "90d"]

_PERIOD_DAYS: dict[Period, int] = {"today": 1, "7d": 7, "30d": 30, "90d": 90}


def get_period_range(period: Period) -> tuple[datetime, datetime]:
    """Return (start, end) as UTC-aware datetimes for the given period.

    Boundaries are computed from Africa/Cairo midnight (FR-024) so every admin sees
    identical totals regardless of their own timezone. `end` is always "now".
    """
    now_cairo = datetime.now(CAIRO)
    today_start_cairo = now_cairo.replace(hour=0, minute=0, second=0, microsecond=0)
    start_cairo = today_start_cairo - timedelta(days=_PERIOD_DAYS[period] - 1)
    return start_cairo.astimezone(timezone.utc), now_cairo.astimezone(timezone.utc)


def get_daily_buckets(start: datetime, end: datetime) -> list[tuple[date, datetime, datetime]]:
    """Return one (cairo_date, bucket_start_utc, bucket_end_utc) tuple per Africa/Cairo
    calendar day spanned by [start, end], zero-filled with no gaps.

    Africa/Cairo has no DST (fixed UTC+2), so a flat 24h step from `start` always lands on
    the correct local midnight — no per-day DST adjustment is needed.
    """
    buckets: list[tuple[date, datetime, datetime]] = []
    cursor = start
    while cursor <= end:
        cairo_date = cursor.astimezone(CAIRO).date()
        bucket_end = cursor + timedelta(days=1)
        buckets.append((cairo_date, cursor, bucket_end))
        cursor = bucket_end
    return buckets


def get_trend_granularity(start: date, end: date) -> Literal["day", "week"]:
    """"week" for ranges spanning more than 60 days, else "day" (FR-018)."""
    return "week" if (end - start).days > 60 else "day"
