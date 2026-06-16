from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.models.profile import ProfileResponse, ProfileSetup, ProfileUpdate
from app.services import profile_service

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
    return profile_service.update_profile(profile["id"], body.display_name)


@router.post("/me/photo")
async def upload_photo(
    photo: UploadFile = File(...),
    profile: dict = Depends(get_current_user),
) -> dict:
    return await profile_service.upload_profile_photo(profile["id"], photo)
