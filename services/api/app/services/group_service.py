import logging

from fastapi import HTTPException
from supabase import create_client

from app.core.config import settings

logger = logging.getLogger(__name__)


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def _get_platform_setting(sb, key: str, default: str) -> str:
    resp = (
        sb.table("platform_settings")
        .select("value")
        .eq("key", key)
        .maybe_single()
        .execute()
    )
    return resp.data["value"] if resp.data else default


def _get_domain_blocklist(sb) -> set[str]:
    raw = _get_platform_setting(
        sb,
        "group_domain_blocklist",
        "gmail.com,yahoo.com,outlook.com,hotmail.com,icloud.com,protonmail.com",
    )
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _get_new_domain_rate_limit(sb) -> tuple[int, int]:
    limit = int(_get_platform_setting(sb, "group_new_domain_rate_limit", "5"))
    window_minutes = int(
        _get_platform_setting(sb, "group_new_domain_rate_limit_window_minutes", "60")
    )
    return limit, window_minutes


def _require_verified(profile: dict) -> None:
    # Groups reuses the platform's existing endpoint-level identity-verification
    # gating pattern (Spec 021) rather than a middleware gate — see
    # dependencies/auth.get_current_user, which only globally blocks 'suspended'.
    # National ID verification remains the hard trust floor for group creation
    # and joining (FR-016), independent of any domain-verification status.
    if profile.get("verification_status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "identity_verification_required",
                "message": "You must complete National ID verification before using Groups.",
            },
        )
