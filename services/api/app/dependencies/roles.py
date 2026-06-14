from fastapi import Depends, HTTPException

from app.dependencies.auth import get_current_user


async def get_current_admin(profile: dict = Depends(get_current_user)) -> dict:
    if profile.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Admin access required"})
    return profile


async def get_current_driver(profile: dict = Depends(get_current_user)) -> dict:
    if profile.get("role") != "driver":
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Driver role required"})
    return profile


async def get_current_passenger(profile: dict = Depends(get_current_user)) -> dict:
    if profile.get("role") != "passenger":
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Passenger role required"})
    return profile
