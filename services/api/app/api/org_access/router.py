from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.models.org_access import (
    OrgAccessConfirm,
    OrgAccessConfirmResponse,
    OrgAccessRequest,
    OrgAccessRequestResponse,
)
from app.services import org_access_service

router = APIRouter()


@router.post("/request", status_code=201, response_model=OrgAccessRequestResponse)
async def request_org_access_verification(
    payload: OrgAccessRequest,
    profile: dict = Depends(get_current_user),
):
    return await org_access_service.request_verification(profile, payload)


@router.post("/confirm", response_model=OrgAccessConfirmResponse)
async def confirm_org_access_verification(
    payload: OrgAccessConfirm,
    profile: dict = Depends(get_current_user),
):
    return await org_access_service.confirm_verification(profile, payload)
