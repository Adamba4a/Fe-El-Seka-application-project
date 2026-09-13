"""
Retroactively cancel leftover unbooked instances of ended recurring rides.

Root cause (fixed alongside this script, commit e9454d1): before that fix,
recurring_ride_service.end_definition() flipped the definition's status to
'ended' but never cancelled its already-generated future instances, leaving
them 'scheduled' forever with their wallet commission reservation still held.
Any definition ended before that fix landed is stuck with orphaned instances
the current code has no path to clean up (it only auto-cancels at the moment
a definition is ended, not retroactively). This script finds those leftovers
and cancels them the same way end_definition() now would.

Run (local dev, against services/api/.env's DATABASE_URL):
    uv run python scripts/cleanup_orphaned_ended_recurring_instances.py

Run for prod (do NOT run against prod until explicitly told to):
    uv run python scripts/cleanup_orphaned_ended_recurring_instances.py --env-file ../../.env.prod --apply

Defaults to a dry run (prints what would be cancelled). Pass --apply to write.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import Settings  # noqa: E402
from app.core.database import close_pool, create_pool, get_pool  # noqa: E402
from app.services import ride_service  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", default=None, help="Path to an alternate .env file (default: services/api/.env)"
    )
    parser.add_argument("--apply", action="store_true", help="Cancel the rides (default: dry run)")
    args = parser.parse_args()

    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    await create_pool(settings.database_url)
    pool = get_pool()
    try:
        async with pool.acquire() as conn:
            orphans = await conn.fetch(
                """
                SELECT r.id, r.driver_id, r.departure_datetime,
                       rd.id AS definition_id
                FROM rides r
                JOIN recurring_ride_definitions rd ON rd.id = r.recurring_ride_definition_id
                WHERE rd.status = 'ended'
                  AND r.status = 'scheduled'
                  AND NOT EXISTS (
                      SELECT 1 FROM bookings b WHERE b.ride_id = r.id AND b.status = 'confirmed'
                  )
                ORDER BY r.departure_datetime
                """
            )

        print(f"Found {len(orphans)} orphaned instance(s) of ended recurring definitions.")
        for row in orphans:
            print(
                f"  ride={row['id']} definition={row['definition_id']} "
                f"driver={row['driver_id']} departs={row['departure_datetime']}"
            )
            if args.apply:
                try:
                    await ride_service.cancel_ride(
                        row["id"], row["driver_id"],
                        reason="Recurring series ended by driver (retroactive cleanup)",
                        cancellation_source="system",
                    )
                except ride_service.RideServiceError as exc:
                    print(f"    skipped: {exc}")

        if not args.apply:
            print("\nDry run only — pass --apply to cancel these rides.")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
