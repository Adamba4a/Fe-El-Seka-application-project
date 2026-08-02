from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

from app.utils.period import get_trend_granularity

_LEDGER_TYPES = ("COMMISSION_DEBIT", "ADMIN_CREDIT", "ADMIN_DEBIT")


def _range_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """[start, end] is inclusive of both calendar days, in UTC."""
    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    return start_dt, end_dt


def _buckets(start: date, end: date, granularity: str) -> list[tuple[str, datetime, datetime]]:
    start_dt, end_dt = _range_bounds(start, end)
    step = timedelta(days=7) if granularity == "week" else timedelta(days=1)
    buckets: list[tuple[str, datetime, datetime]] = []
    cursor = start_dt
    while cursor < end_dt:
        bucket_end = min(cursor + step, end_dt)
        buckets.append((cursor.date().isoformat(), cursor, bucket_end))
        cursor = bucket_end
    return buckets


async def get_report(conn, start: date, end: date) -> dict:
    start_dt, end_dt = _range_bounds(start, end)

    sums = await conn.fetch(
        """
        SELECT type, COALESCE(SUM(amount_egp), 0) AS total
        FROM driver_ledger_entries
        WHERE created_at >= $1 AND created_at < $2 AND type::text = ANY($3::text[])
        GROUP BY type
        """,
        start_dt,
        end_dt,
        list(_LEDGER_TYPES),
    )
    totals = {t: Decimal("0") for t in _LEDGER_TYPES}
    for row in sums:
        totals[row["type"]] = Decimal(str(row["total"]))

    commission = totals["COMMISSION_DEBIT"]
    credits = totals["ADMIN_CREDIT"]
    debits = totals["ADMIN_DEBIT"]
    net_revenue = commission - debits

    granularity = get_trend_granularity(start, end)
    buckets = _buckets(start, end, granularity)
    bucket_labels = [b[0] for b in buckets]
    bucket_starts = [b[1] for b in buckets]
    bucket_ends = [b[2] for b in buckets]

    trend_rows = await conn.fetch(
        """
        SELECT b.bucket_label, COALESCE(SUM(l.amount_egp), 0) AS value
        FROM unnest($1::text[], $2::timestamptz[], $3::timestamptz[])
            AS b(bucket_label, bucket_start, bucket_end)
        LEFT JOIN driver_ledger_entries l
            ON l.type = 'COMMISSION_DEBIT'
            AND l.created_at >= b.bucket_start AND l.created_at < b.bucket_end
        GROUP BY b.bucket_label
        """,
        bucket_labels,
        bucket_starts,
        bucket_ends,
    )
    values_by_label = {r["bucket_label"]: Decimal(str(r["value"])) for r in trend_rows}
    points = [
        {"date": label, "value": str(values_by_label.get(label, Decimal("0")))}
        for label in bucket_labels
    ]

    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "commission_collected_egp": str(commission),
        "admin_credits_egp": str(credits),
        "admin_debits_egp": str(debits),
        "net_revenue_egp": str(net_revenue),
        "trend": {
            "metric": "commission_collected_egp",
            "granularity": granularity,
            "points": points,
        },
    }


async def get_driver_balances(conn) -> dict:
    rows = await conn.fetch(
        """
        SELECT p.id AS driver_id, p.display_name,
               COALESCE(w.balance_egp, 0) AS balance_egp,
               COALESCE(w.reserved_egp, 0) AS reserved_egp
        FROM profiles p
        LEFT JOIN driver_wallets w ON w.driver_id = p.id
        WHERE p.role = 'driver'
        """
    )
    items = []
    for r in rows:
        balance = Decimal(str(r["balance_egp"]))
        reserved = Decimal(str(r["reserved_egp"]))
        available = balance - reserved
        items.append(
            {
                "driver_id": str(r["driver_id"]),
                "display_name": r["display_name"],
                "balance_egp": str(balance),
                "reserved_egp": str(reserved),
                "available_egp": str(available),
                "is_at_risk": available <= 0,
            }
        )
    items.sort(key=lambda item: Decimal(item["available_egp"]))
    return {"items": items}


def _csv_row(*fields: str) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(fields)
    return buf.getvalue()


async def stream_report_csv(conn, start: date, end: date) -> AsyncIterator[str]:
    """Same totals as `get_report()` — no separate aggregation path to drift out of sync."""
    report = await get_report(conn, start, end)

    yield _csv_row(
        "start", "end", "commission_collected_egp", "admin_credits_egp",
        "admin_debits_egp", "net_revenue_egp",
    )
    yield _csv_row(
        report["range"]["start"],
        report["range"]["end"],
        report["commission_collected_egp"],
        report["admin_credits_egp"],
        report["admin_debits_egp"],
        report["net_revenue_egp"],
    )
    yield _csv_row()
    yield _csv_row("trend_date", "trend_commission_collected_egp")
    for point in report["trend"]["points"]:
        yield _csv_row(point["date"], str(point["value"]))
