import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.core.config import settings
from app.core.database import get_pool
from app.dependencies.auth import get_current_user
from app.models.profile import ProfileResponse, ProfileSetup, ProfileUpdate, PublicProfileResponse
from app.services import profile_service, rating_service

router = APIRouter()
_bearer = HTTPBearer()


def _auth_user(credentials: HTTPAuthorizationCredentials):
    """Resolve Supabase auth user without requiring a profile row.
    Still checks for suspension so a suspended user cannot create a second profile."""
    sb = create_client(settings.supabase_url, settings.supabase_service_role_key)
    try:
        user_resp = sb.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid token"},
        )
    if not user_resp or not user_resp.user:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Invalid token"},
        )
    # Check for suspension — a profile row may not exist yet, so tolerate no-data.
    # Wrapped in try/except so a transient DB error doesn't block profile creation.
    try:
        profile_resp = (
            sb.table("profiles")
            .select("verification_status")
            .eq("id", user_resp.user.id)
            .maybe_single()
            .execute()
        )
        if (
            profile_resp.data
            and profile_resp.data.get("verification_status") == "suspended"
        ):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "account_suspended",
                    "message": "Your account has been suspended.",
                },
            )
    except HTTPException:
        raise
    except Exception:
        pass  # No profile row yet — suspension check skipped; allow through.
    return user_resp.user


@router.post(
    "/setup",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup_profile(
    body: ProfileSetup,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    user = _auth_user(credentials)
    return profile_service.setup_profile(
        user.id, user.email or "", body.role, body.display_name
    )


@router.get("/me", response_model=ProfileResponse)
def get_profile(profile: dict = Depends(get_current_user)) -> dict:
    return profile_service.get_profile_me(profile["id"])


@router.put("/me", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdate,
    profile: dict = Depends(get_current_user),
) -> dict:
    return profile_service.update_profile(
        profile["id"],
        body.display_name,
        body.language_preference,
        body.phone_number,
        body.date_of_birth.isoformat() if body.date_of_birth else None,
    )


@router.post("/me/photo")
async def upload_photo(
    photo: UploadFile = File(...),
    profile: dict = Depends(get_current_user),
) -> dict:
    return await profile_service.upload_profile_photo(profile["id"], photo)


@router.get("/{user_id}/public", response_model=PublicProfileResponse)
async def get_public_profile(
    user_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
) -> dict:
    caller_id = uuid.UUID(str(profile["id"]))
    pool = get_pool()
    async with pool.acquire() as conn:
        return await profile_service.get_public_profile(conn, user_id, caller_id)


@router.get("/{user_id}/rating")
async def get_rating_summary(
    user_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
) -> dict:
    # Open to any authenticated viewer, not just the ratee: get_own_rating_summary
    # already applies the double-blind reveal filter (FR-008) and never attributes
    # a comment to its rater (FR-007), so the result is safe to show on any
    # profile view, not just the ratee's own settings page.
    pool = get_pool()
    async with pool.acquire() as conn:
        summary = await rating_service.get_own_rating_summary(conn, user_id)

    return {
        "rating_avg": summary["rating_avg"],
        "rating_count": summary["rating_count"],
        "comments": [
            {"comment": c["comment"], "created_at": c["created_at"].isoformat()}
            for c in summary["comments"]
        ],
    }
