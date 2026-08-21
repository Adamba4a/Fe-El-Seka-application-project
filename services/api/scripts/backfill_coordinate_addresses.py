"""
Re-resolve ride addresses that were stored as raw "lat, lng" text.

Root cause (fixed alongside this script): origin_address/destination_address
are captured once, client-side, at ride-creation time from a direct browser
call to the public Nominatim instance. That instance has no SLA and, without
an identifying User-Agent, throttles/drops requests especially from mobile
carrier IPs — when the lookup failed, the UI fell back to the raw coordinate
string and that string was what got persisted, permanently, as the address.
Geocoding now goes through services/api's own proxy (app/services/geocode_service.py),
which is reliable going forward — this script repairs rides created before
that fix, in place, using the same service.

Run (local dev, against services/api/.env's DATABASE_URL):
    uv run python scripts/backfill_coordinate_addresses.py

Run for prod (do NOT run against prod until explicitly told to):
    uv run python scripts/backfill_coordinate_addresses.py --env-file ../../.env.prod --apply

Defaults to a dry run (prints what would change). Pass --apply to write.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.services.geocode_service import GeocodeServiceUnavailableError, reverse_geocode  # noqa: E402

# Matches the "{lat.toFixed(5)}, {lng.toFixed(5)}" fallback string produced
# client-side (see apps/main/src/lib/geocode.ts / RideMap.tsx).
_COORD_ADDRESS_RE = re.compile(r"^-?\d{1,3}\.\d+,\s*-?\d{1,3}\.\d+$")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", default=None, help="Path to an alternate .env file (default: services/api/.env)"
    )
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = parser.parse_args()

    settings = Settings(_env_file=args.env_file) if args.env_file else Settings()
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        rows = await conn.fetch(
            """
            SELECT id, origin_address, destination_address,
                   ST_Y(origin_coordinates::geometry) AS origin_lat,
                   ST_X(origin_coordinates::geometry) AS origin_lng,
                   ST_Y(destination_coordinates::geometry) AS dest_lat,
                   ST_X(destination_coordinates::geometry) AS dest_lng
            FROM rides
            WHERE origin_address ~ '^-?[0-9]{1,3}\\.[0-9]+,\\s*-?[0-9]{1,3}\\.[0-9]+$'
               OR destination_address ~ '^-?[0-9]{1,3}\\.[0-9]+,\\s*-?[0-9]{1,3}\\.[0-9]+$'
            """
        )

        print(f"Found {len(rows)} ride(s) with a raw-coordinate address.")
        for row in rows:
            updates: dict[str, str] = {}

            if _COORD_ADDRESS_RE.match(row["origin_address"]):
                try:
                    result = await reverse_geocode(row["origin_lat"], row["origin_lng"])
                except GeocodeServiceUnavailableError as exc:
                    print(f"  ride={row['id']} origin: geocode failed ({exc}), skipping")
                else:
                    if result.get("address"):
                        updates["origin_address"] = result["address"]

            if _COORD_ADDRESS_RE.match(row["destination_address"]):
                try:
                    result = await reverse_geocode(row["dest_lat"], row["dest_lng"])
                except GeocodeServiceUnavailableError as exc:
                    print(f"  ride={row['id']} destination: geocode failed ({exc}), skipping")
                else:
                    if result.get("address"):
                        updates["destination_address"] = result["address"]

            if not updates:
                continue

            print(f"  ride={row['id']} -> {updates}")
            if args.apply:
                set_clause = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(updates))
                await conn.execute(
                    f"UPDATE rides SET {set_clause} WHERE id = $1", row["id"], *updates.values()
                )

        if not args.apply:
            print("\nDry run only — pass --apply to write these changes.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
