from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
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

    # Verify the JWT signature locally instead of calling Supabase Auth's
    # /auth/v1/user endpoint — that network round trip on every authenticated
    # request was a major latency contributor, especially over mobile
    # networks. Supabase signs these tokens HS256 against SUPABASE_JWT_SECRET.
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or expired token",
            },
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Invalid or expired token",
            },
        )

    sb = _supabase()
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
