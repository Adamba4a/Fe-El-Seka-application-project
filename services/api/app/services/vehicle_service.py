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


def request_vehicle_update(driver_id: str, data: dict) -> dict:
    sb = _supabase()
    vehicle = sb.table("vehicles").select("id").eq("driver_id", driver_id).execute()
    if not vehicle.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No vehicle registered"},
        )

    # Supersede any existing pending request
    sb.table("vehicle_update_requests").update({
        "status": "rejected",
        "rejection_reason": "Superseded by newer request",
    }).eq("driver_id", driver_id).eq("status", "pending_review").execute()

    insert_data: dict = {"driver_id": driver_id, "vehicle_id": vehicle.data[0]["id"]}
    insert_data.update({k: v for k, v in data.items() if v is not None})

    resp = sb.table("vehicle_update_requests").insert(insert_data).execute()
    return _format_update_request(resp.data[0])


def get_pending_vehicle_update(driver_id: str) -> dict | None:
    sb = _supabase()
    resp = (
        sb.table("vehicle_update_requests")
        .select("*")
        .eq("driver_id", driver_id)
        .eq("status", "pending_review")
        .order("submitted_at", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    return _format_update_request(resp.data[0])


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


def _format_update_request(row: dict) -> dict:
    return {
        "id": row["id"],
        "plate_number": row.get("plate_number"),
        "make": row.get("make"),
        "model": row.get("model"),
        "year": row.get("year"),
        "status": row["status"],
        "submitted_at": str(row["submitted_at"]),
        "rejection_reason": row.get("rejection_reason"),
    }
