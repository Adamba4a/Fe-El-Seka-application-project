from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.core.config import settings
from app.dependencies.roles import get_current_admin
from app.services import audit_service, auth_service

router = APIRouter()


class SuspendRequest(BaseModel):
    reason: str


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.post("/{user_id}/suspend")
def suspend_user(
    user_id: str,
    body: SuspendRequest,
    profile: dict = Depends(get_current_admin),
) -> dict:
    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "Suspension reason is required",
            },
        )

    sb = _supabase()
    p = (
        sb.table("profiles")
        .select("verification_status")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not p.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found"},
        )
    if p.data["verification_status"] == "suspended":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "User is already suspended"},
        )

    (
        sb.table("profiles")
        .update({"verification_status": "suspended"})
        .eq("id", user_id)
        .execute()
    )
    # Revoke all refresh tokens immediately (two-layer revocation)
    auth_service.revoke_sessions(user_id)

    audit_id = audit_service.append_log(
        profile["id"], "suspended", user_id, reason=body.reason.strip()
    )
    return {"user_id": user_id, "new_status": "suspended", "audit_log_id": audit_id}


@router.post("/{user_id}/reinstate")
def reinstate_user(
    user_id: str,
    profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    p = (
        sb.table("profiles")
        .select("verification_status")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not p.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found"},
        )
    if p.data["verification_status"] != "suspended":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "User is not suspended"},
        )

    (
        sb.table("profiles")
        .update({"verification_status": "verified"})
        .eq("id", user_id)
        .execute()
    )
    audit_id = audit_service.append_log(profile["id"], "reinstated", user_id)
    return {"user_id": user_id, "new_status": "verified", "audit_log_id": audit_id}
