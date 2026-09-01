from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.core.database import get_pool
from app.dependencies.org_access import require_org_verified
from app.dependencies.roles import get_current_driver
from app.models.recurring_ride import (
    RecurringRideDefinitionCreateRequest,
    RecurringRideDefinitionDetailResponse,
    RecurringRideDefinitionListResponse,
    RecurringRideDefinitionResponse,
    RecurringRideDefinitionUpdateRequest,
    RecurringRideDefinitionUpdateResponse,
)
from app.services import recurring_ride_service
from app.services.recurring_ride_service import RecurringRideServiceError

router = APIRouter()


def _service_error_response(exc: RecurringRideServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message},
    )


async def _get_own_active_vehicle(driver_id: uuid.UUID, vehicle_id: uuid.UUID) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, seat_count FROM vehicles WHERE id = $1 AND driver_id = $2 AND is_active = true",
            vehicle_id, driver_id,
        )
    if row is None:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "no_active_vehicle",
                "message": "You need an active vehicle to post a ride.",
            },
        )
    return dict(row)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/recurring
# ─────────────────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_recurring_definition(
    payload: RecurringRideDefinitionCreateRequest,
    profile: dict = Depends(get_current_driver),
    _org_verified: dict = Depends(require_org_verified),
) -> RecurringRideDefinitionResponse:
    driver_id = uuid.UUID(str(profile["id"]))
    vehicle = await _get_own_active_vehicle(driver_id, payload.vehicle_id)

    try:
        return await recurring_ride_service.create_definition(
            driver_id, payload.vehicle_id, vehicle["seat_count"], payload
        )
    except RecurringRideServiceError as exc:
        return _service_error_response(exc)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/rides/recurring
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_recurring_definitions(
    profile: dict = Depends(get_current_driver),
) -> RecurringRideDefinitionListResponse:
    driver_id = uuid.UUID(str(profile["id"]))
    return await recurring_ride_service.list_definitions(driver_id)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/rides/recurring/{definition_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{definition_id}")
async def get_recurring_definition(
    definition_id: uuid.UUID,
    profile: dict = Depends(get_current_driver),
) -> RecurringRideDefinitionDetailResponse:
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        return await recurring_ride_service.get_definition(driver_id, definition_id)
    except RecurringRideServiceError as exc:
        return _service_error_response(exc)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/rides/recurring/{definition_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/{definition_id}")
async def edit_recurring_definition(
    definition_id: uuid.UUID,
    payload: RecurringRideDefinitionUpdateRequest,
    profile: dict = Depends(get_current_driver),
) -> RecurringRideDefinitionUpdateResponse:
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        return await recurring_ride_service.edit_definition(driver_id, definition_id, payload)
    except RecurringRideServiceError as exc:
        return _service_error_response(exc)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/rides/recurring/{definition_id}/end
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{definition_id}/end")
async def end_recurring_definition(
    definition_id: uuid.UUID,
    profile: dict = Depends(get_current_driver),
) -> RecurringRideDefinitionResponse:
    driver_id = uuid.UUID(str(profile["id"]))
    try:
        return await recurring_ride_service.end_definition(driver_id, definition_id)
    except RecurringRideServiceError as exc:
        return _service_error_response(exc)
