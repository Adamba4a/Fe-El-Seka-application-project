from fastapi import Depends, HTTPException

from app.dependencies.auth import get_current_user


async def require_org_verified(profile: dict = Depends(get_current_user)) -> dict:
    if profile.get("org_verified_at") is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "org_verification_required",
                "message": "You must verify a company or university email before using this feature.",
            },
        )
    return profile
