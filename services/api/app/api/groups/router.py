from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.auth import get_current_user
from app.models.group import (
    CreateGroupRequest,
    GroupDetailResponse,
    GroupListResponse,
    GroupSummary,
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
    type_filter: Optional[str] = Query(None, alias="type"),
    route_tag: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _profile: dict = Depends(get_current_user),
):
    return await group_service.search_groups(q, type_filter, route_tag, limit, offset)


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
