import asyncio
import logging
import uuid
from datetime import date

from fastapi import HTTPException, UploadFile
from supabase import create_client

from app.core.config import settings
from app.services import storage_service

_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}
_MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
MIN_SIGNUP_AGE_YEARS = 18
logger = logging.getLogger(__name__)


def _calculate_age(dob: date) -> int:
    today = date.today()
    age = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1
    return age


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def setup_profile(
    user_id: str, email: str, role: str, display_name: str
) -> dict:
    sb = _supabase()
    existing = sb.table("profiles").select("id").eq("id", user_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail={"error": "already_exists", "message": "Profile already set up."},
        )
    resp = sb.table("profiles").insert({
        "id": user_id,
        "email": email,
        "role": role,
        "display_name": display_name,
    }).execute()
    if not resp.data:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "insert_failed",
                "message": "Failed to create profile. Please try again.",
            },
        )
    return _format_profile(resp.data[0])


def get_profile_me(user_id: str) -> dict:
    sb = _supabase()
    resp = sb.table("profiles").select("*").eq("id", user_id).single().execute()
    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )
    return _format_profile(resp.data)


def update_profile(
    user_id: str,
    display_name: str | None,
    language_preference: str | None = None,
    phone_number: str | None = None,
    date_of_birth: date | None = None,
    gender: str | None = None,
) -> dict:
    sb = _supabase()
    updates: dict = {}
    if display_name is not None:
        updates["display_name"] = display_name
    if language_preference is not None:
        updates["language_preference"] = language_preference
    if phone_number is not None:
        updates["phone_number"] = phone_number
    if date_of_birth is not None:
        if _calculate_age(date_of_birth) < MIN_SIGNUP_AGE_YEARS:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "underage",
                    "message": f"You must be at least {MIN_SIGNUP_AGE_YEARS} years old to use Triplyy.",
                },
            )
        updates["date_of_birth"] = date_of_birth.isoformat()
    if gender is not None:
        updates["gender"] = gender
    if not updates:
        return get_profile_me(user_id)
    resp = sb.table("profiles").update(updates).eq("id", user_id).execute()
    return _format_profile(resp.data[0])


async def upload_profile_photo(user_id: str, file: UploadFile) -> dict:
    if file.content_type not in _ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_media",
                "message": "Only JPEG and PNG are accepted",
            },
        )

    data = await file.read()
    if len(data) > _MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "file_too_large", "message": "Photo must be under 5 MB"},
        )

    ext = "jpg" if file.content_type == "image/jpeg" else "png"
    path = f"{user_id}/profile.{ext}"
    # boto3 and supabase-py are synchronous clients. This endpoint is async,
    # so running either client directly here blocks the worker's event loop
    # while the browser is waiting for the upload response. Under a slow R2
    # connection that can make the write succeed but the client lose the
    # response, surfacing as a misleading browser-level "Failed to fetch".
    # Keep the network work off the event loop, as verification uploads do.
    try:
        await asyncio.to_thread(
            storage_service.upload_file, "profile-photos", path, data, file.content_type
        )
    except Exception as exc:
        logger.exception(
            "profile photo R2 upload failed for user_id=%s error_type=%s error=%s",
            user_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "profile_photo_upload_failed",
                "message": "Could not save the photo. Please try again.",
            },
        ) from exc

    try:
        sb = await asyncio.to_thread(_supabase)
        await asyncio.to_thread(
            lambda: (
                sb.table("profiles")
                .update({"profile_photo_path": path})
                .eq("id", user_id)
                .execute()
            )
        )
    except Exception as exc:
        logger.exception(
            "profile photo database update failed for user_id=%s error_type=%s error=%s",
            user_id,
            type(exc).__name__,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "profile_photo_upload_failed",
                "message": "Could not save the photo. Please try again.",
            },
        ) from exc

    # The client does not use this URL during onboarding. Avoid a second R2
    # round-trip just to build a response; subsequent profile reads create the
    # signed URL when it is actually needed.
    return {"profile_photo_url": None}


async def get_public_profile(
    conn,
    user_id: uuid.UUID,
    caller_id: uuid.UUID,
    ride_id: uuid.UUID | None = None,
) -> dict:
    """Public-facing profile: name, photo, verification, rating, ride history.

    phone_number is included only when a profile is opened from the exact ride
    where the caller has a confirmed booking and the ride is still scheduled
    or in progress. It disappears after the ride is completed and is never
    exposed from search or an arbitrary public-profile URL.
    """
    profile = await conn.fetchrow(
        """
        SELECT id, display_name, role, profile_photo_path, verification_status,
               rating_avg, rating_count, phone_number
        FROM profiles
        WHERE id = $1
        """,
        user_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Profile not found"},
        )

    if profile["role"] == "driver":
        total_rides = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM rides r
            WHERE r.driver_id = $1
              AND r.status = 'completed'
              AND EXISTS (SELECT 1 FROM bookings b WHERE b.ride_id = r.id)
            """,
            user_id,
        )
        recent_rows = await conn.fetch(
            """
            SELECT origin_address, destination_address, departure_datetime
            FROM rides r
            WHERE r.driver_id = $1
              AND r.status = 'completed'
              AND EXISTS (SELECT 1 FROM bookings b WHERE b.ride_id = r.id)
            ORDER BY r.departure_datetime DESC
            LIMIT 3
            """,
            user_id,
        )
    else:
        total_rides = await conn.fetchval(
            "SELECT COUNT(*) FROM bookings WHERE passenger_id = $1 AND status = 'completed'",
            user_id,
        )
        recent_rows = await conn.fetch(
            """
            SELECT r.origin_address, r.destination_address, r.departure_datetime
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.passenger_id = $1 AND b.status = 'completed'
            ORDER BY r.departure_datetime DESC
            LIMIT 3
            """,
            user_id,
        )

    photo_url = None
    if profile["profile_photo_path"]:
        photo_url = storage_service.generate_signed_url(
            "profile-photos", profile["profile_photo_path"]
        )

    phone_number = None
    if caller_id == user_id:
        phone_number = profile["phone_number"]
    elif ride_id is not None:
        shared_booking = await conn.fetchval(
            """
            SELECT 1
            FROM bookings b
            JOIN rides r ON r.id = b.ride_id
            WHERE b.status = 'confirmed'
              AND r.id = $3
              AND r.status IN ('scheduled', 'in_progress')
              AND (
                (r.driver_id = $1 AND b.passenger_id = $2)
                OR (r.driver_id = $2 AND b.passenger_id = $1)
              )
            LIMIT 1
            """,
            user_id,
            caller_id,
            ride_id,
        )
        if shared_booking:
            phone_number = profile["phone_number"]

    return {
        "id": str(profile["id"]),
        "display_name": profile["display_name"],
        "role": profile["role"],
        "profile_photo_url": photo_url,
        "verification_status": profile["verification_status"],
        "rating_avg": float(profile["rating_avg"]) if profile["rating_avg"] is not None else None,
        "rating_count": profile["rating_count"] or 0,
        "total_rides": total_rides or 0,
        "recent_rides": [
            {
                "origin_address": r["origin_address"],
                "destination_address": r["destination_address"],
                "departure_datetime": r["departure_datetime"].isoformat() if r["departure_datetime"] else None,
            }
            for r in recent_rows
        ],
        "phone_number": phone_number,
    }


def _format_profile(row: dict) -> dict:
    photo_url = None
    if row.get("profile_photo_path"):
        photo_url = storage_service.generate_signed_url(
            "profile-photos", row["profile_photo_path"]
        )
    return {
        "id": row["id"],
        "email": row["email"],
        "phone_number": row.get("phone_number"),
        "display_name": row["display_name"],
        "role": row["role"],
        "profile_photo_url": photo_url,
        "verification_status": row["verification_status"],
        "is_submission_locked": row["is_submission_locked"],
        "rating_avg": float(row["rating_avg"]) if row.get("rating_avg") is not None else None,
        "rating_count": row.get("rating_count") or 0,
        "created_at": str(row["created_at"]),
        "language_preference": row.get("language_preference"),
        "date_of_birth": str(row["date_of_birth"]) if row.get("date_of_birth") else None,
        "gender": row.get("gender"),
        "org_verified_at": str(row["org_verified_at"]) if row.get("org_verified_at") else None,
        "org_verified_domain": row.get("org_verified_domain"),
    }
