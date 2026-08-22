import asyncio
import time

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from supabase import create_client

from app.core.config import settings

_bearer = HTTPBearer()

# Cached JWKS from Supabase Auth. The project has migrated off the legacy
# static HS256 shared secret onto per-project asymmetric signing keys
# (ES256) — tokens must be verified against Supabase's current public
# key(s), fetched from its JWKS endpoint, not a static secret. Cached to
# avoid a network round trip on every request (the whole point of
# verifying locally instead of calling /auth/v1/user); refreshed on a TTL
# and eagerly on an unrecognized `kid` (key rotation).
_JWKS_TTL_SECONDS = 3600
_jwks_cache: list[dict] = []
_jwks_fetched_at = 0.0
_jwks_lock = asyncio.Lock()


async def _fetch_jwks() -> list[dict]:
    url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json().get("keys", [])


async def _get_signing_key(kid: str | None) -> dict | None:
    global _jwks_cache, _jwks_fetched_at

    if time.time() - _jwks_fetched_at > _JWKS_TTL_SECONDS:
        async with _jwks_lock:
            if time.time() - _jwks_fetched_at > _JWKS_TTL_SECONDS:
                _jwks_cache = await _fetch_jwks()
                _jwks_fetched_at = time.time()

    key = next((k for k in _jwks_cache if k.get("kid") == kid), None)
    if key is not None:
        return key

    # Might be a freshly rotated key our cache doesn't know about yet.
    async with _jwks_lock:
        _jwks_cache = await _fetch_jwks()
        _jwks_fetched_at = time.time()
    return next((k for k in _jwks_cache if k.get("kid") == kid), None)


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    token = credentials.credentials

    try:
        kid = jwt.get_unverified_header(token).get("kid")
        key = await _get_signing_key(kid)
        if key is None:
            raise JWTError(f"Unknown signing key: {kid}")
        payload = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "ES256")],
            audience="authenticated",
        )
    except (JWTError, httpx.HTTPError):
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
