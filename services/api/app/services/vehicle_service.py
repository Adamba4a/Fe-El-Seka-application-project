from fastapi import HTTPException
from supabase import create_client

from app.core.config import settings


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def register_vehicle(driver_id: str, data: dict) -> dict:
    sb = _supabase()
    existing = sb.table("vehicles").select("id").eq("driver_id", driver_id).execute()
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "already_exists",
                "message": "You already have a registered vehicle",
            },
        )

    resp = sb.table("vehicles").insert({
        "driver_id": driver_id,
        "plate_number": data["plate_number"],
        "make": data["make"],
        "model": data["model"],
        "year": data["year"],
        "color": data["color"],
        "seat_count": data["seat_count"],
    }).execute()
    return _format(resp.data[0])


def get_vehicle_me(driver_id: str) -> dict:
    sb = _supabase()
    resp = sb.table("vehicles").select("*").eq("driver_id", driver_id).execute()
    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No vehicle registered yet"},
        )
    return _format(resp.data[0])


def update_vehicle(driver_id: str, color: str | None, seat_count: int | None) -> dict:
    sb = _supabase()
    updates: dict = {}
    if color is not None:
        updates["color"] = color
    if seat_count is not None:
        updates["seat_count"] = seat_count
    if not updates:
        return get_vehicle_me(driver_id)

    existing = sb.table("vehicles").select("id").eq("driver_id", driver_id).execute()
    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No vehicle registered"},
        )

    resp = sb.table("vehicles").update(updates).eq("driver_id", driver_id).execute()
    return _format(resp.data[0])


def _format(row: dict) -> dict:
    return {
        "id": row["id"],
        "plate_number": row["plate_number"],
        "make": row["make"],
        "model": row["model"],
        "year": row["year"],
        "color": row["color"],
        "seat_count": row["seat_count"],
        "registered_at": str(row["registered_at"]),
    }
