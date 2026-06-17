import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.core.config import settings
from app.dependencies.roles import get_current_admin

router = APIRouter()


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class RejectRequest(BaseModel):
    reason: str


@router.post("/{request_id}/approve")
def approve_vehicle_update(
    request_id: str,
    profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    resp = sb.table("vehicle_update_requests").select("*").eq("id", request_id).execute()
    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Request not found"},
        )
    req = resp.data[0]
    if req["status"] != "pending_review":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "Request already processed"},
        )

    updates: dict = {}
    for field in ("plate_number", "make", "model", "year"):
        if req.get(field) is not None:
            updates[field] = req[field]

    if updates:
        sb.table("vehicles").update(updates).eq("id", req["vehicle_id"]).execute()

    now = datetime.datetime.utcnow().isoformat()
    sb.table("vehicle_update_requests").update({
        "status": "approved",
        "reviewer_id": profile["id"],
        "reviewed_at": now,
    }).eq("id", request_id).execute()

    return {"request_id": request_id, "status": "approved"}


@router.post("/{request_id}/reject")
def reject_vehicle_update(
    request_id: str,
    body: RejectRequest,
    profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    resp = sb.table("vehicle_update_requests").select("id, status").eq("id", request_id).execute()
    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Request not found"},
        )
    if resp.data[0]["status"] != "pending_review":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "Request already processed"},
        )

    now = datetime.datetime.utcnow().isoformat()
    sb.table("vehicle_update_requests").update({
        "status": "rejected",
        "rejection_reason": body.reason.strip(),
        "reviewer_id": profile["id"],
        "reviewed_at": now,
    }).eq("id", request_id).execute()

    return {"request_id": request_id, "status": "rejected"}
