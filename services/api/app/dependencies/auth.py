from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.core.config import settings

_bearer = HTTPBearer()


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    token = credentials.credentials
    sb = _supabase()

    try:
        user_resp = sb.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or expired token",
            },
        )

    if not user_resp or not user_resp.user:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or expired token",
            },
        )

    user_id = user_resp.user.id

    profile_resp = (
        sb.table("profiles").select("*").eq("id", user_id).single().execute()
    )
    if not profile_resp.data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "message": "Profile not found. Please complete profile setup.",
            },
        )

    profile = profile_resp.data

    if profile["verification_status"] == "suspended":
        raise HTTPException(
            status_code=401,
            detail={
                "error": "account_suspended",
                "message": "Your account has been suspended. Contact support.",
            },
        )

    request.state.user = profile
    request.state.token = token
    return profile
