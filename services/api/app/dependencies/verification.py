from fastapi import Depends, HTTPException

from app.dependencies.roles import get_current_driver, get_current_passenger


async def get_current_verified_driver(profile: dict = Depends(get_current_driver)) -> dict:
    if profile.get("verification_status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={"error": "verification_required", "message": "Driver verification required to perform this action"},
        )
    return profile


async def get_current_verified_passenger(profile: dict = Depends(get_current_passenger)) -> dict:
    if profile.get("verification_status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={"error": "verification_required", "message": "Passenger verification required to perform this action"},
        )
    return profile
