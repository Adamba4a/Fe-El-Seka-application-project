from fastapi import HTTPException, UploadFile
from supabase import create_client

from app.core.config import settings
from app.services import storage_service

_ALLOWED_TYPES = {"image/jpeg", "image/png"}
_MAX_DOC_BYTES = 10 * 1024 * 1024  # 10 MB


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _get_support_email() -> str:
    sb = _supabase()
    resp = (
        sb.table("platform_settings")
        .select("value")
        .eq("key", "support_email")
        .single()
        .execute()
    )
    return resp.data["value"] if resp.data else "support@felseka.com"


async def _validate_and_read(file: UploadFile) -> bytes:
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_media",
                "message": "Only JPEG and PNG accepted",
            },
        )
    data = await file.read()
    if len(data) > _MAX_DOC_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message": "Document must be under 10 MB",
            },
        )
    return data


async def submit_documents(
    user_id: str,
    user_role: str,
    front_id: UploadFile,
    back_id: UploadFile,
    license: UploadFile | None,
) -> dict:
    sb = _supabase()

    # Check lock
    profile = (
        sb.table("profiles")
        .select("is_submission_locked")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )
    if profile and profile["is_submission_locked"]:
        support_email = _get_support_email()
        raise HTTPException(
            status_code=403,
            detail={
                "error": "submission_locked",
                "message": (
                    f"You have exhausted all submission attempts."
                    f" Please contact us at {support_email} for a manual review."
                ),
                "support_email": support_email,
            },
        )

    # Check for existing pending submission
    pending = (
        sb.table("verification_submissions")
        .select("id")
        .eq("user_id", user_id)
        .eq("status", "pending_review")
        .execute()
    )
    if pending.data:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": "You already have a submission under review.",
            },
        )

    submission_type = "driver_id_license" if user_role == "driver" else "passenger_id"

    # Read and validate all file contents before touching storage so we fail
    # fast on bad input without creating orphaned objects.
    import uuid
    submission_id = str(uuid.uuid4())

    front_data = await _validate_and_read(front_id)
    back_data = await _validate_and_read(back_id)
    license_data = None
    if license and user_role == "driver":
        license_data = await _validate_and_read(license)

    # Determine attempt number using a Postgres-side MAX to avoid a TOCTOU race.
    # The SELECT is non-locking but runs after the above validation; under concurrent
    # submits the DB UNIQUE constraint on (user_id, attempt_number) will reject
    # the duplicate insert, so at most one row wins.
    previous = (
        sb.table("verification_submissions")
        .select("attempt_number")
        .eq("user_id", user_id)
        .order("attempt_number", desc=True)
        .limit(1)
        .execute()
    )
    attempt_number = (previous.data[0]["attempt_number"] + 1) if previous.data else 1

    front_ext = "jpg" if front_id.content_type == "image/jpeg" else "png"
    back_ext = "jpg" if back_id.content_type == "image/jpeg" else "png"

    # Build the DB row first; upload to storage only after a successful insert
    # so we never create orphaned storage objects.
    row: dict = {
        "id": submission_id,
        "user_id": user_id,
        "submission_type": submission_type,
        "attempt_number": attempt_number,
        # Paths are pre-computed so they can be inserted before the upload.
        "front_id_path": f"{user_id}/nid_front_{submission_id}.{front_ext}",
        "back_id_path": f"{user_id}/nid_back_{submission_id}.{back_ext}",
    }
    if license_data:
        lic_ext = "jpg" if license.content_type == "image/jpeg" else "png"
        row["license_path"] = f"{user_id}/license_{submission_id}.{lic_ext}"

    # Insert the DB row first — if this fails (duplicate attempt_number, lock, etc.)
    # we have not uploaded anything and can return a clean error.
    try:
        sb.table("verification_submissions").insert(row).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "conflict",
                "message": "Submission could not be recorded. Please try again.",
            },
        ) from exc

    # DB row committed — now upload. A storage failure here is recoverable:
    # the row exists so the admin queue will surface the submission; missing
    # files will appear as broken signed URLs, prompting an admin to request
    # a resubmission rather than silently losing data.
    storage_service.upload_file(
        "identity-documents",
        row["front_id_path"],
        front_data,
        front_id.content_type,
    )
    storage_service.upload_file(
        "identity-documents",
        row["back_id_path"],
        back_data,
        back_id.content_type,
    )
    if license_data:
        storage_service.upload_file(
            "identity-documents",
            row["license_path"],
            license_data,
            license.content_type,
        )

    (
        sb.table("profiles")
        .update({"verification_status": "pending_review"})
        .eq("id", user_id)
        .execute()
    )

    return {
        "submission_id": submission_id,
        "status": "pending_review",
        "attempt_number": attempt_number,
    }


def get_status(user_id: str) -> dict:
    sb = _supabase()
    profile = (
        sb.table("profiles")
        .select("verification_status, is_submission_locked")
        .eq("id", user_id)
        .single()
        .execute()
        .data
    )

    latest = (
        sb.table("verification_submissions")
        .select("attempt_number, rejection_reason, is_locked")
        .eq("user_id", user_id)
        .order("attempt_number", desc=True)
        .limit(1)
        .execute()
    )

    sub = latest.data[0] if latest.data else None
    lockout_message = None

    if profile and profile["is_submission_locked"]:
        support_email = _get_support_email()
        lockout_message = (
            f"You have exhausted all submission attempts."
            f" Contact {support_email} for manual review."
        )

    return {
        "verification_status": (
            profile["verification_status"] if profile else "unverified"
        ),
        "attempt_number": sub["attempt_number"] if sub else None,
        "is_locked": profile["is_submission_locked"] if profile else False,
        "rejection_reason": sub["rejection_reason"] if sub else None,
        "lockout_message": lockout_message,
    }
