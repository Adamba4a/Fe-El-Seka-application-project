from __future__ import annotations

import uuid
from datetime import datetime

from app.models.location import LocationResponse, LocationUpdateResponse


class LocationServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def upsert_location(
    conn,
    ride_id: uuid.UUID,
    driver_id: uuid.UUID,
    lat: float,
    lng: float,
    bearing: int | None,
    speed_kmh: float | None,
    client_timestamp: datetime,
) -> LocationUpdateResponse:
    ride = await conn.fetchrow(
        "SELECT driver_id, status FROM rides WHERE id = $1",
        ride_id,
    )
    if ride is None:
        raise LocationServiceError("ride_not_found", "Ride not found.", 404)
    if ride["driver_id"] != driver_id:
        raise LocationServiceError("forbidden", "You are not the driver of this ride.", 403)
    if ride["status"] != "in_progress":
        raise LocationServiceError(
            "ride_not_in_progress",
            "Location updates are only accepted for in-progress rides.",
            409,
        )

    row = await conn.fetchrow(
        """
        INSERT INTO driver_locations
            (ride_id, driver_id, location, bearing, speed_kmh, client_timestamp)
        VALUES
            ($1, $2, ST_SetSRID(ST_MakePoint($4, $3), 4326), $5, $6, $7)
        ON CONFLICT (ride_id) DO UPDATE SET
            location         = EXCLUDED.location,
            bearing          = EXCLUDED.bearing,
            speed_kmh        = EXCLUDED.speed_kmh,
            client_timestamp = EXCLUDED.client_timestamp,
            updated_at       = now()
        RETURNING id, ride_id, updated_at
        """,
        ride_id, driver_id, lat, lng, bearing, speed_kmh, client_timestamp,
    )
    return LocationUpdateResponse(
        location_id=row["id"],
        ride_id=row["ride_id"],
        updated_at=row["updated_at"],
    )


async def read_location(
    conn,
    ride_id: uuid.UUID,
    caller_id: uuid.UUID,
) -> LocationResponse:
    booking = await conn.fetchrow(
        """
        SELECT id FROM bookings
        WHERE ride_id = $1 AND passenger_id = $2 AND status = 'confirmed'
        """,
        ride_id, caller_id,
    )
    if booking is None:
        raise LocationServiceError(
            "forbidden",
            "You do not have a confirmed booking on this ride.",
            403,
        )

    row = await conn.fetchrow(
        """
        SELECT ride_id, lat, lng, bearing, client_timestamp, updated_at
        FROM driver_locations_view
        WHERE ride_id = $1
        """,
        ride_id,
    )
    if row is None:
        raise LocationServiceError(
            "location_not_found",
            "Driver has not reported a location yet.",
            404,
        )

    return LocationResponse(
        ride_id=row["ride_id"],
        lat=row["lat"],
        lng=row["lng"],
        bearing=row["bearing"],
        client_timestamp=row["client_timestamp"],
        updated_at=row["updated_at"],
    )
