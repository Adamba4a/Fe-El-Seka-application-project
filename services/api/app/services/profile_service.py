from fastapi import HTTPException, UploadFile
from supabase import create_client

from app.core.config import settings
from app.services import storage_service

_ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}
_MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB


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


def update_profile(user_id: str, display_name: str | None) -> dict:
    sb = _supabase()
    updates: dict = {}
    if display_name is not None:
        updates["display_name"] = display_name
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
    storage_service.upload_file("profile-photos", path, data, file.content_type)

    sb = _supabase()
    (
        sb.table("profiles")
        .update({"profile_photo_path": path})
        .eq("id", user_id)
        .execute()
    )

    signed_url = storage_service.generate_signed_url("profile-photos", path)
    return {"profile_photo_url": signed_url}


def _format_profile(row: dict) -> dict:
    photo_url = None
    if row.get("profile_photo_path"):
        photo_url = storage_service.generate_signed_url(
            "profile-photos", row["profile_photo_path"]
        )
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
        "profile_photo_url": photo_url,
        "verification_status": row["verification_status"],
        "is_submission_locked": row["is_submission_locked"],
        "created_at": str(row["created_at"]),
    }
