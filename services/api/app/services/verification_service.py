import asyncio
import logging

from fastapi import BackgroundTasks, HTTPException, UploadFile
from supabase import create_client

from app.core.config import settings
from app.services import ai_client, storage_service

logger = logging.getLogger(__name__)

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
    selfie: UploadFile,
    license: UploadFile | None,
    background_tasks: BackgroundTasks,
) -> dict:
    # Every Supabase/R2 call below is a synchronous network call. Running it
    # directly inside this async handler would block the whole event loop for
    # its duration, stalling every other request the API is serving — offload
    # each one to a thread instead.
    sb = await asyncio.to_thread(_supabase)

    # Check lock
    profile = (
        await asyncio.to_thread(
            lambda: sb.table("profiles")
            .select("is_submission_locked, display_name")
            .eq("id", user_id)
            .single()
            .execute()
        )
    ).data
    if profile and profile["is_submission_locked"]:
        support_email = await asyncio.to_thread(_get_support_email)
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
    pending = await asyncio.to_thread(
        lambda: sb.table("verification_submissions")
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
    selfie_data = await _validate_and_read(selfie)
    license_data = None
    if license and user_role == "driver":
        license_data = await _validate_and_read(license)

    # Determine attempt number using a Postgres-side MAX to avoid a TOCTOU race.
    # The SELECT is non-locking but runs after the above validation; under concurrent
    # submits the DB UNIQUE constraint on (user_id, attempt_number) will reject
    # the duplicate insert, so at most one row wins.
    previous = await asyncio.to_thread(
        lambda: sb.table("verification_submissions")
        .select("attempt_number")
        .eq("user_id", user_id)
        .order("attempt_number", desc=True)
        .limit(1)
        .execute()
    )
    attempt_number = (previous.data[0]["attempt_number"] + 1) if previous.data else 1

    front_ext = "jpg" if front_id.content_type == "image/jpeg" else "png"
    back_ext = "jpg" if back_id.content_type == "image/jpeg" else "png"
    selfie_ext = "jpg" if selfie.content_type == "image/jpeg" else "png"

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
        await asyncio.to_thread(
            lambda: sb.table("verification_submissions").insert(row).execute()
        )
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
    #
    # The selfie doubles as the user's public profile photo: it becomes their
    # avatar throughout the app (not just a verification artifact), so it is
    # stored in the profile-photos bucket and set on profiles.profile_photo_path
    # exactly as the Settings photo upload does.
    profile_photo_path = f"{user_id}/profile.{selfie_ext}"

    # These uploads are independent, so run them concurrently instead of
    # waiting on each one in turn — total time drops from the sum of all
    # uploads to roughly the slowest one.
    upload_tasks = [
        asyncio.to_thread(
            storage_service.upload_file,
            "identity-documents",
            row["front_id_path"],
            front_data,
            front_id.content_type,
        ),
        asyncio.to_thread(
            storage_service.upload_file,
            "identity-documents",
            row["back_id_path"],
            back_data,
            back_id.content_type,
        ),
        asyncio.to_thread(
            storage_service.upload_file,
            "profile-photos",
            profile_photo_path,
            selfie_data,
            selfie.content_type,
        ),
    ]
    if license_data:
        upload_tasks.append(
            asyncio.to_thread(
                storage_service.upload_file,
                "identity-documents",
                row["license_path"],
                license_data,
                license.content_type,
            )
        )
    await asyncio.gather(*upload_tasks)

    await asyncio.to_thread(
        lambda: sb.table("profiles")
        .update({
            "verification_status": "pending_review",
            "profile_photo_path": profile_photo_path,
        })
        .eq("id", user_id)
        .execute()
    )

    # Advisory-only AI triage: runs after the response is sent so OCR/face-match
    # latency never delays the signup flow. Failure/timeout just leaves the
    # ai_* columns NULL — the existing pending_review -> admin review path is
    # unaffected either way.
    background_tasks.add_task(
        _run_ai_verification,
        submission_id=submission_id,
        submission_type=submission_type,
        display_name=(profile or {}).get("display_name") or "",
        front_data=front_data,
        front_content_type=front_id.content_type,
        back_data=back_data,
        back_content_type=back_id.content_type,
        selfie_data=selfie_data,
        selfie_content_type=selfie.content_type,
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


async def _run_ai_verification(
    submission_id: str,
    submission_type: str,
    display_name: str,
    front_data: bytes,
    front_content_type: str,
    back_data: bytes,
    back_content_type: str,
    selfie_data: bytes,
    selfie_content_type: str,
) -> None:
    try:
        readout = await ai_client.verify_submission(
            front_id=(front_data, front_content_type),
            back_id=(back_data, back_content_type),
            selfie=(selfie_data, selfie_content_type),
            display_name=display_name,
            submission_type=submission_type,
        )
        if not readout:
            return

        ocr = readout.get("ocr") or {}
        face = readout.get("face")
        _supabase().table("verification_submissions").update({
            "ai_ocr_text_front": ocr.get("extracted_text_front"),
            "ai_ocr_text_back": ocr.get("extracted_text_back"),
            "ai_name_match_score": ocr.get("name_match_score"),
            "ai_face_match_score": face.get("match_score") if face else None,
            "ai_id_face_detected": face.get("id_face_detected") if face else None,
            "ai_selfie_face_detected": face.get("selfie_face_detected") if face else None,
            "ai_image_quality": readout.get("image_quality"),
            "ai_reasons": readout.get("reasons"),
            "ai_model_version": readout.get("model_version"),
            "ai_processed_at": readout.get("processed_at"),
        }).eq("id", submission_id).execute()
    except Exception:
        logger.warning(
            "AI verification read-out failed for submission %s",
            submission_id,
            exc_info=True,
        )
