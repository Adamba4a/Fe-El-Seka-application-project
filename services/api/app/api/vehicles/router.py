from fastapi import APIRouter, Depends, status

from app.dependencies.roles import get_current_driver
from app.dependencies.verification import get_current_verified_driver
from app.models.vehicle import VehicleRegister, VehicleResponse, VehicleUpdate
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
