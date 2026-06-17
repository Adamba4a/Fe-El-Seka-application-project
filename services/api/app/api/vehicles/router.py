from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.roles import get_current_driver
from app.dependencies.verification import get_current_verified_driver
from app.models.vehicle import (
    VehicleRegister,
    VehicleResponse,
    VehicleUpdate,
    VehicleUpdateRequest,
    VehicleUpdateRequestResponse,
)
from app.services import vehicle_service

router = APIRouter()


@router.post(
    "/register",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_vehicle(
    body: VehicleRegister,
    profile: dict = Depends(get_current_verified_driver),
) -> dict:
    return vehicle_service.register_vehicle(profile["id"], body.model_dump())


@router.get("/me", response_model=VehicleResponse)
def get_vehicle(profile: dict = Depends(get_current_driver)) -> dict:
    return vehicle_service.get_vehicle_me(profile["id"])


@router.put("/me", response_model=VehicleResponse)
def update_vehicle(
    body: VehicleUpdate,
    profile: dict = Depends(get_current_verified_driver),
) -> dict:
    return vehicle_service.update_vehicle(profile["id"], body.color, body.seat_count)


@router.post("/me/update-request", response_model=VehicleUpdateRequestResponse)
def submit_vehicle_update_request(
    body: VehicleUpdateRequest,
    profile: dict = Depends(get_current_verified_driver),
) -> dict:
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(
            status_code=422,
            detail={"error": "empty_request", "message": "No fields to update"},
        )
    return vehicle_service.request_vehicle_update(profile["id"], data)


@router.get("/me/update-request", response_model=VehicleUpdateRequestResponse)
def get_vehicle_update_request(
    profile: dict = Depends(get_current_driver),
) -> dict:
    result = vehicle_service.get_pending_vehicle_update(profile["id"])
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "No pending update request"},
        )
    return result
