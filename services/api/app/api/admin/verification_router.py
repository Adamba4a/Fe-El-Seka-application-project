from fastapi import APIRouter, Depends, HTTPException
from supabase import create_client

from app.core.config import settings
from app.dependencies.roles import get_current_admin
from app.models.verification import AdminQueueResponse, AdminSubmissionDetail, RejectRequest
from app.services import audit_service, storage_service

router = APIRouter()


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.get("/queue", response_model=AdminQueueResponse)
def get_queue(
    type: str | None = None,
    page: int = 1,
    limit: int = 20,
    profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    query = (
        sb.table("verification_submissions")
        .select("id, user_id, submission_type, submitted_at, attempt_number, profiles(display_name, phone_number)")
        .eq("status", "pending_review")
        .order("submitted_at", desc=False)
    )
    if type:
        query = query.eq("submission_type", type)

    count_resp = sb.table("verification_submissions").select("id", count="exact").eq("status", "pending_review")
    if type:
        count_resp = count_resp.eq("submission_type", type)
    total = count_resp.execute().count or 0

    offset = (page - 1) * limit
    resp = query.range(offset, offset + limit - 1).execute()

    items = []
    for row in (resp.data or []):
        p = row.get("profiles") or {}
        items.append({
            "submission_id": row["id"],
            "user_id": row["user_id"],
            "user_name": p.get("display_name", ""),
            "phone_number": p.get("phone_number", ""),
            "submission_type": row["submission_type"],
            "submitted_at": str(row["submitted_at"]),
            "attempt_number": row["attempt_number"],
        })
    return {"total": total, "page": page, "items": items}


@router.get("/{submission_id}", response_model=AdminSubmissionDetail)
def get_submission(submission_id: str, profile: dict = Depends(get_current_admin)) -> dict:
    sb = _supabase()
    resp = sb.table("verification_submissions").select(
        "*, profiles(display_name, phone_number)"
    ).eq("id", submission_id).single().execute()

    if not resp.data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Submission not found"})

    row = resp.data
    p = row.get("profiles") or {}
    doc_urls = storage_service.get_identity_document_urls(row)

    return {
        "submission_id": row["id"],
        "user_id": row["user_id"],
        "user_name": p.get("display_name", ""),
        "phone_number": p.get("phone_number", ""),
        "submission_type": row["submission_type"],
        "submitted_at": str(row["submitted_at"]),
        "attempt_number": row["attempt_number"],
        "document_signed_urls": doc_urls,
    }


@router.post("/{submission_id}/approve")
def approve_submission(submission_id: str, profile: dict = Depends(get_current_admin)) -> dict:
    sb = _supabase()
    sub = sb.table("verification_submissions").select("status, user_id").eq("id", submission_id).single().execute()
    if not sub.data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Submission not found"})
    if sub.data["status"] != "pending_review":
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Submission already processed"})

    user_id = sub.data["user_id"]
    import datetime
    now = datetime.datetime.utcnow().isoformat()
    sb.table("verification_submissions").update({
        "status": "approved", "reviewer_id": profile["id"], "reviewed_at": now,
    }).eq("id", submission_id).execute()
    sb.table("profiles").update({"verification_status": "verified"}).eq("id", user_id).execute()

    audit_id = audit_service.append_log(profile["id"], "approved", user_id, submission_id=submission_id)
    return {"submission_id": submission_id, "user_id": user_id, "new_status": "verified", "audit_log_id": audit_id}


@router.post("/{submission_id}/reject")
def reject_submission(
    submission_id: str,
    body: RejectRequest,
    profile: dict = Depends(get_current_admin),
) -> dict:
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail={"error": "validation_error", "message": "Rejection reason is required"})

    sb = _supabase()
    sub = sb.table("verification_submissions").select("status, user_id, attempt_number").eq("id", submission_id).single().execute()
    if not sub.data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Submission not found"})
    if sub.data["status"] != "pending_review":
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Submission already processed"})

    user_id = sub.data["user_id"]
    is_third = sub.data["attempt_number"] >= 3

    import datetime
    now = datetime.datetime.utcnow().isoformat()
    sb.table("verification_submissions").update({
        "status": "rejected",
        "rejection_reason": body.reason.strip(),
        "reviewer_id": profile["id"],
        "reviewed_at": now,
        "is_locked": is_third,
    }).eq("id", submission_id).execute()

    profile_update: dict = {"verification_status": "rejected"}
    if is_third:
        profile_update["is_submission_locked"] = True
    sb.table("profiles").update(profile_update).eq("id", user_id).execute()

    audit_id = audit_service.append_log(
        profile["id"], "rejected", user_id, submission_id=submission_id, reason=body.reason.strip()
    )
    return {
        "submission_id": submission_id,
        "user_id": user_id,
        "new_status": "rejected",
        "is_locked": is_third,
        "audit_log_id": audit_id,
    }


@router.post("/users/{user_id}/unlock")
def unlock_user(user_id: str, profile: dict = Depends(get_current_admin)) -> dict:
    sb = _supabase()
    p = sb.table("profiles").select("is_submission_locked").eq("id", user_id).single().execute()
    if not p.data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found"})
    if not p.data["is_submission_locked"]:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "User is not locked"})

    sb.table("profiles").update({"is_submission_locked": False}).eq("id", user_id).execute()
    # Reset attempt_number on latest locked submission to allow one more
    sb.table("verification_submissions").update({"is_locked": False}).eq("user_id", user_id).eq("is_locked", True).execute()

    audit_id = audit_service.append_log(profile["id"], "unlocked", user_id)
    return {"user_id": user_id, "is_submission_locked": False, "audit_log_id": audit_id}


@router.get("/history")
def get_history(page: int = 1, limit: int = 20, profile: dict = Depends(get_current_admin)) -> dict:
    sb = _supabase()
    offset = (page - 1) * limit
    resp = sb.table("verification_submissions").select(
        "id, user_id, status, reviewed_at, reviewer_id, profiles(display_name)"
    ).neq("status", "pending_review").order("reviewed_at", desc=True).range(offset, offset + limit - 1).execute()

    total_resp = sb.table("verification_submissions").select("id", count="exact").neq("status", "pending_review").execute()
    total = total_resp.count or 0

    items = []
    for row in (resp.data or []):
        p = row.get("profiles") or {}
        items.append({
            "submission_id": row["id"],
            "user_name": p.get("display_name", ""),
            "outcome": row["status"],
            "reviewed_by": row.get("reviewer_id", ""),
            "reviewed_at": str(row.get("reviewed_at", "")),
        })
    return {"total": total, "page": page, "items": items}
