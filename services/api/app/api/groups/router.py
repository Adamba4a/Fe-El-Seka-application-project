from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.models.group import (
    CreateGroupRequest,
    DomainVerificationConfirm,
    DomainVerificationConfirmResponse,
    DomainVerificationRequest,
    DomainVerificationRequestResponse,
    GroupDetailResponse,
    GroupListResponse,
    GroupMemberResponse,
    GroupSummary,
    InviteLinkResponse,
    MembershipResponse,
    SponsorshipDashboardResponse,
    TransferOwnershipRequest,
)
from app.models.ride import RideListResponse
from app.services import group_service

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GroupSummary)
async def create_group(
    payload: CreateGroupRequest,
    profile: dict = Depends(get_current_user),
):
    return await group_service.create_group(profile, payload)


# Registered before "/{group_id}" — otherwise FastAPI would try to parse
# "mine" as a UUID path param and 422 before ever reaching this route
# (same ordering rule rides/router.py follows for its fixed-segment routes).
@router.get("/mine", response_model=list[GroupSummary])
async def list_my_groups(
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.list_my_groups(user_id)


@router.get("", response_model=GroupListResponse)
async def search_groups(
    q: Optional[str] = Query(None),
    route_tag: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _profile: dict = Depends(get_current_user),
):
    return await group_service.search_groups(q, route_tag, limit, offset)


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group_detail(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.get_group_detail(group_id, user_id)


@router.get("/{group_id}/rides", response_model=RideListResponse)
async def list_group_rides(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.list_group_rides(group_id, user_id)


@router.post("/{group_id}/invite-link", response_model=InviteLinkResponse)
async def generate_invite_link(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.generate_invite_link(group_id, user_id)


@router.get("/join/{invite_token}", response_model=GroupDetailResponse)
async def resolve_invite_token(
    invite_token: str,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.resolve_invite_token(invite_token, user_id)


@router.post("/{group_id}/join", response_model=MembershipResponse)
async def join_group(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    return await group_service.join_group(profile, group_id)


@router.post("/{group_id}/domain-verification/request", response_model=DomainVerificationRequestResponse)
async def request_domain_verification(
    group_id: uuid.UUID,
    payload: DomainVerificationRequest,
    profile: dict = Depends(get_current_user),
):
    return await group_service.request_domain_verification(profile, group_id, payload)


@router.post("/domain-verification/confirm", response_model=DomainVerificationConfirmResponse)
async def confirm_domain_verification(
    payload: DomainVerificationConfirm,
    profile: dict = Depends(get_current_user),
):
    return await group_service.confirm_domain_verification(profile, payload)


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_group_members(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.list_group_members(group_id, user_id)


@router.post("/{group_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    await group_service.leave_group(group_id, user_id)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    owner_id = uuid.UUID(str(profile["id"]))
    await group_service.remove_member(group_id, owner_id, user_id)


@router.post("/{group_id}/transfer-ownership", response_model=GroupSummary)
async def transfer_ownership(
    group_id: uuid.UUID,
    payload: TransferOwnershipRequest,
    profile: dict = Depends(get_current_user),
):
    owner_id = uuid.UUID(str(profile["id"]))
    return await group_service.transfer_ownership(group_id, owner_id, payload.new_owner_user_id)


@router.get("/{group_id}/sponsorship-dashboard", response_model=SponsorshipDashboardResponse)
async def get_sponsorship_dashboard(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    user_id = uuid.UUID(str(profile["id"]))
    return await group_service.get_sponsorship_dashboard(group_id, user_id)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_group(
    group_id: uuid.UUID,
    profile: dict = Depends(get_current_user),
):
    owner_id = uuid.UUID(str(profile["id"]))
    await group_service.archive_group(group_id, owner_id)
