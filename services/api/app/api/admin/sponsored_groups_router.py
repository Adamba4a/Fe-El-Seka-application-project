from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.dependencies.roles import get_current_admin
from app.models.group import (
    AddFundsRequest,
    AddFundsResponse,
    DashboardContactRequest,
    DashboardContactResponse,
    GroupMemberResponse,
    GroupSummary,
    SponsoredGroupCreateRequest,
)
from app.services import group_service, sponsored_group_service

router = APIRouter()


@router.post("", response_model=GroupSummary)
async def create_or_upgrade_sponsored_group(
    body: SponsoredGroupCreateRequest,
    admin: dict = Depends(get_current_admin),
) -> GroupSummary:
    admin_id = uuid.UUID(str(admin["id"]))
    return await sponsored_group_service.create_or_upgrade_sponsored_group(admin_id, body)


@router.post("/{group_id}/add-funds", response_model=AddFundsResponse)
async def add_funds(
    group_id: uuid.UUID,
    body: AddFundsRequest,
    _admin: dict = Depends(get_current_admin),
) -> AddFundsResponse:
    return await sponsored_group_service.add_funds(group_id, body.amount_egp)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_members(
    group_id: uuid.UUID,
    _admin: dict = Depends(get_current_admin),
) -> list[GroupMemberResponse]:
    return await group_service.list_members_admin(group_id)


@router.post("/{group_id}/dashboard-contact", response_model=DashboardContactResponse)
async def set_dashboard_contact(
    group_id: uuid.UUID,
    body: DashboardContactRequest,
    admin: dict = Depends(get_current_admin),
) -> DashboardContactResponse:
    admin_id = uuid.UUID(str(admin["id"]))
    return await group_service.set_dashboard_contact(group_id, admin_id, body.user_id)
