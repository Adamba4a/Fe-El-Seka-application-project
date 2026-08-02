from __future__ import annotations

from decimal import Decimal
from typing import Literal

from app.utils.period import Period, get_daily_buckets, get_period_range

Metric = Literal["rides_completed", "commission_collected_egp"]

_ROLES = ("passenger", "driver", "admin")


async def get_kpis(conn, period: Period) -> dict:
    start, end = get_period_range(period)

    role_rows = await conn.fetch("SELECT role, COUNT(*) AS count FROM profiles GROUP BY role")
    users_by_role = {role: 0 for role in _ROLES}
    for row in role_rows:
        if row["role"] in users_by_role:
            users_by_role[row["role"]] = int(row["count"])

    rides_created = await conn.fetchval(
        "SELECT COUNT(*) FROM rides WHERE created_at >= $1 AND created_at < $2", start, end
    )
    rides_completed = await conn.fetchval(
        "SELECT COUNT(*) FROM rides WHERE completed_at >= $1 AND completed_at < $2", start, end
    )
    commission_collected = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_egp), 0) FROM driver_ledger_entries
        WHERE type = 'COMMISSION_DEBIT' AND created_at >= $1 AND created_at < $2
        """,
        start,
        end,
    )
    pending_verifications = await conn.fetchval(
        "SELECT COUNT(*) FROM verification_submissions WHERE status = 'pending_review'"
    )
    open_reports = await conn.fetchval(
        "SELECT COUNT(*) FROM reports WHERE status IN ('open', 'under_review')"
    )
    drivers_at_or_below_zero = await conn.fetchval(
        """
        SELECT COUNT(*) FROM profiles p
        LEFT JOIN driver_wallets w ON w.driver_id = p.id
        WHERE p.role = 'driver'
          AND COALESCE(w.balance_egp, 0) - COALESCE(w.reserved_egp, 0) <= 0
        """
    )

    return {
        "period": period,
        "users_by_role": users_by_role,
        "rides_created": int(rides_created),
        "rides_completed": int(rides_completed),
        "commission_collected_egp": str(Decimal(str(commission_collected))),
        "pending_verifications": int(pending_verifications),
        "open_reports": int(open_reports),
        "drivers_at_or_below_zero": int(drivers_at_or_below_zero),
    }


async def get_daily_trend(conn, period: Period, metric: Metric) -> dict:
    start, end = get_period_range(period)
    buckets = get_daily_buckets(start, end)
    dates = [b[0] for b in buckets]
    starts = [b[1] for b in buckets]
    ends = [b[2] for b in buckets]

    if metric == "rides_completed":
        rows = await conn.fetch(
            """
            SELECT b.bucket_date, COUNT(r.id) AS value
            FROM unnest($1::date[], $2::timestamptz[], $3::timestamptz[])
                AS b(bucket_date, bucket_start, bucket_end)
            LEFT JOIN rides r
                ON r.completed_at >= b.bucket_start AND r.completed_at < b.bucket_end
            GROUP BY b.bucket_date
            ORDER BY b.bucket_date
            """,
            dates,
            starts,
            ends,
        )
        points = [{"date": r["bucket_date"].isoformat(), "value": int(r["value"])} for r in rows]
    else:
        rows = await conn.fetch(
            """
            SELECT b.bucket_date, COALESCE(SUM(l.amount_egp), 0) AS value
            FROM unnest($1::date[], $2::timestamptz[], $3::timestamptz[])
                AS b(bucket_date, bucket_start, bucket_end)
            LEFT JOIN driver_ledger_entries l
                ON l.type = 'COMMISSION_DEBIT'
                AND l.created_at >= b.bucket_start AND l.created_at < b.bucket_end
            GROUP BY b.bucket_date
            ORDER BY b.bucket_date
            """,
            dates,
            starts,
            ends,
        )
        points = [
            {"date": r["bucket_date"].isoformat(), "value": str(Decimal(str(r["value"])))}
            for r in rows
        ]

    return {"metric": metric, "granularity": "day", "points": points}
