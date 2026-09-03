from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

from app.utils.period import get_trend_granularity

_LEDGER_TYPES = (
    "COMMISSION_DEBIT", "CASH_BACK_CREDIT", "POINTS_DISCOUNT_REIMBURSEMENT", "ADMIN_CREDIT", "ADMIN_DEBIT",
)


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

    credits = totals["ADMIN_CREDIT"]
    debits = totals["ADMIN_DEBIT"]

    # COMMISSION_DEBIT (cash rides) and the SPONSORED_RIDE_CREDIT gap (below) are both
    # GROSS figures: they still contain the ride's distance_fee, which is not platform
    # revenue — it is credited straight back to the driver as CASH_BACK_CREDIT in the
    # same transaction (see commission_service.deduct_commission and
    # booking_service._settle_sponsored_booking's "100% platform revenue, credited
    # straight back to the driver" comments). Subtracting that passthrough here is what
    # turns "amount debited from the driver's wallet" into the platform's true take.
    # CASH_BACK_CREDIT has exactly two writers (see the two note strings below) and both
    # ONLY carry the distance-fee share of commission, so summing it is safe here —
    # nothing else has ever written this ledger type. The two writers are told apart by
    # booking_id: the cash-ride writer never sets it, the sponsored writer always does.
    distance_fee_passthrough_cash = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_egp), 0) FROM driver_ledger_entries
        WHERE type = 'CASH_BACK_CREDIT' AND booking_id IS NULL
          AND created_at >= $1 AND created_at < $2
        """,
        start_dt,
        end_dt,
    )
    distance_fee_passthrough_sponsored = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_egp), 0) FROM driver_ledger_entries
        WHERE type = 'CASH_BACK_CREDIT' AND booking_id IS NOT NULL
          AND created_at >= $1 AND created_at < $2
        """,
        start_dt,
        end_dt,
    )
    distance_fee_passthrough_cash = Decimal(str(distance_fee_passthrough_cash))
    distance_fee_passthrough_sponsored = Decimal(str(distance_fee_passthrough_sponsored))

    # POINTS_DISCOUNT_REIMBURSEMENT (cash rides only — commission_service.py, never
    # written for sponsored bookings) pays the driver back for a passenger's
    # pay-with-points fare discount out of COMMISSION_DEBIT, same as CASH_BACK_CREDIT
    # above: gross commission debited, then a slice of it immediately paid back out.
    # It's a real cost incurred at redemption time even though the points themselves
    # were earned (and their cost budgeted for) on other, earlier rides.
    points_discount_reimbursement = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_egp), 0) FROM driver_ledger_entries
        WHERE type = 'POINTS_DISCOUNT_REIMBURSEMENT'
          AND created_at >= $1 AND created_at < $2
        """,
        start_dt,
        end_dt,
    )
    points_discount_reimbursement = Decimal(str(points_discount_reimbursement))

    commission = totals["COMMISSION_DEBIT"] - distance_fee_passthrough_cash - points_discount_reimbursement

    # Sponsored-ride commission never touches the driver's own balance (there's
    # no cash the driver held to debit) — it's the gap between what the group's
    # funded balance is debited (bookings.total_price) and what the driver is
    # credited (the SPONSORED_RIDE_CREDIT entry), so it must be computed here
    # rather than summed directly out of driver_ledger_entries like the other
    # ledger-type totals above. This gap is also gross (see distance-fee note
    # above), so the per-group query below subtracts each group's passthrough too.
    sponsored_commission_gross = await conn.fetchval(
        """
        SELECT COALESCE(SUM(b.total_price - l.amount_egp), 0)
        FROM driver_ledger_entries l
        JOIN bookings b ON b.id = l.booking_id
        WHERE l.type = 'SPONSORED_RIDE_CREDIT' AND l.created_at >= $1 AND l.created_at < $2
        """,
        start_dt,
        end_dt,
    )
    sponsored_commission = Decimal(str(sponsored_commission_gross)) - distance_fee_passthrough_sponsored

    sponsored_commission_by_group_rows = await conn.fetch(
        """
        SELECT g.id AS group_id, g.name AS group_name,
               COALESCE(SUM(b.total_price - l.amount_egp), 0) AS gross_commission_egp,
               COALESCE(cb.distance_fee_passthrough, 0) AS distance_fee_passthrough,
               COUNT(*) AS rides
        FROM driver_ledger_entries l
        JOIN bookings b ON b.id = l.booking_id
        JOIN rides r ON r.id = l.ride_id
        JOIN groups g ON g.id = r.group_id
        LEFT JOIN (
            SELECT r2.group_id, SUM(l2.amount_egp) AS distance_fee_passthrough
            FROM driver_ledger_entries l2
            JOIN rides r2 ON r2.id = l2.ride_id
            WHERE l2.type = 'CASH_BACK_CREDIT' AND l2.booking_id IS NOT NULL
              AND l2.created_at >= $1 AND l2.created_at < $2
            GROUP BY r2.group_id
        ) cb ON cb.group_id = g.id
        WHERE l.type = 'SPONSORED_RIDE_CREDIT' AND l.created_at >= $1 AND l.created_at < $2
        GROUP BY g.id, g.name, cb.distance_fee_passthrough
        ORDER BY gross_commission_egp - COALESCE(cb.distance_fee_passthrough, 0) DESC
        """,
        start_dt,
        end_dt,
    )
    sponsored_commission_by_group = [
        {
            "group_id": str(r["group_id"]),
            "group_name": r["group_name"],
            "commission_egp": str(Decimal(str(r["gross_commission_egp"])) - Decimal(str(r["distance_fee_passthrough"]))),
            "rides": r["rides"],
        }
        for r in sponsored_commission_by_group_rows
    ]

    distance_fee_passthrough_total = distance_fee_passthrough_cash + distance_fee_passthrough_sponsored
    net_revenue = commission + sponsored_commission - debits

    granularity = get_trend_granularity(start, end)
    buckets = _buckets(start, end, granularity)
    bucket_labels = [b[0] for b in buckets]
    bucket_starts = [b[1] for b in buckets]
    bucket_ends = [b[2] for b in buckets]

    # Net out the same cash-ride distance-fee passthrough and points-discount
    # reimbursement as `commission` above, per bucket, so the trend line matches the
    # top-level figure instead of the gross debit.
    trend_rows = await conn.fetch(
        """
        SELECT b.bucket_label,
               COALESCE(SUM(l.amount_egp) FILTER (WHERE l.type = 'COMMISSION_DEBIT'), 0)
                   - COALESCE(SUM(l.amount_egp) FILTER (WHERE l.type = 'CASH_BACK_CREDIT' AND l.booking_id IS NULL), 0)
                   - COALESCE(SUM(l.amount_egp) FILTER (WHERE l.type = 'POINTS_DISCOUNT_REIMBURSEMENT'), 0)
                   AS value
        FROM unnest($1::text[], $2::timestamptz[], $3::timestamptz[])
            AS b(bucket_label, bucket_start, bucket_end)
        LEFT JOIN driver_ledger_entries l
            ON l.type IN ('COMMISSION_DEBIT', 'CASH_BACK_CREDIT', 'POINTS_DISCOUNT_REIMBURSEMENT')
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
        "sponsored_commission_collected_egp": str(sponsored_commission),
        "sponsored_commission_by_group": sponsored_commission_by_group,
        "distance_fee_passthrough_egp": str(distance_fee_passthrough_total),
        "points_discount_reimbursement_egp": str(points_discount_reimbursement),
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
               COALESCE(w.reserved_egp, 0) AS reserved_egp,
               COALESCE(w.sponsored_earnings_egp, 0) AS sponsored_earnings_egp
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
        sponsored_earnings = Decimal(str(r["sponsored_earnings_egp"]))
        items.append(
            {
                "driver_id": str(r["driver_id"]),
                "display_name": r["display_name"],
                "balance_egp": str(balance),
                "reserved_egp": str(reserved),
                "available_egp": str(available),
                "sponsored_earnings_egp": str(sponsored_earnings),
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
        "start", "end", "commission_collected_egp", "sponsored_commission_collected_egp",
        "distance_fee_passthrough_egp", "points_discount_reimbursement_egp",
        "admin_credits_egp", "admin_debits_egp", "net_revenue_egp",
    )
    yield _csv_row(
        report["range"]["start"],
        report["range"]["end"],
        report["commission_collected_egp"],
        report["sponsored_commission_collected_egp"],
        report["distance_fee_passthrough_egp"],
        report["points_discount_reimbursement_egp"],
        report["admin_credits_egp"],
        report["admin_debits_egp"],
        report["net_revenue_egp"],
    )
    yield _csv_row()
    yield _csv_row("trend_date", "trend_commission_collected_egp")
    for point in report["trend"]["points"]:
        yield _csv_row(point["date"], str(point["value"]))
    yield _csv_row()
    yield _csv_row("sponsored_group_name", "sponsored_group_commission_egp", "sponsored_group_rides")
    for g in report["sponsored_commission_by_group"]:
        yield _csv_row(g["group_name"], g["commission_egp"], str(g["rides"]))
