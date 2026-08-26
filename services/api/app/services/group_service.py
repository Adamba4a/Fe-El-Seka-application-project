from __future__ import annotations

import uuid
from typing import Optional

from fastapi import HTTPException

from app.core.database import get_pool
from app.models.group import (
    CreateGroupRequest,
    GroupDetailResponse,
    GroupListResponse,
    GroupSummary,
)
from app.models.ride import RideListResponse


async def _get_platform_setting(conn, key: str, default: str) -> str:
    value = await conn.fetchval("SELECT value FROM platform_settings WHERE key = $1", key)
    return value if value is not None else default


async def _get_domain_blocklist(conn) -> set[str]:
    raw = await _get_platform_setting(
        conn,
        "group_domain_blocklist",
        "gmail.com,yahoo.com,outlook.com,hotmail.com,icloud.com,protonmail.com",
    )
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


async def _get_new_domain_rate_limit(conn) -> tuple[int, int]:
    limit = int(await _get_platform_setting(conn, "group_new_domain_rate_limit", "5"))
    window_minutes = int(
        await _get_platform_setting(conn, "group_new_domain_rate_limit_window_minutes", "60")
    )
    return limit, window_minutes


def _require_verified(profile: dict) -> None:
    # Groups reuses the platform's existing endpoint-level identity-verification
    # gating pattern (Spec 021) rather than a middleware gate — see
    # dependencies/auth.get_current_user, which only globally blocks 'suspended'.
    # National ID verification remains the hard trust floor for group creation
    # and joining (FR-016), independent of any domain-verification status.
    if profile.get("verification_status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "identity_verification_required",
                "message": "You must complete National ID verification before using Groups.",
            },
        )


def _to_summary(row) -> GroupSummary:
    return GroupSummary(
        id=str(row["id"]),
        name=row["name"],
        type=row["type"],
        description=row["description"],
        route_tags=list(row["route_tags"]) if row["route_tags"] else [],
        member_count=row["member_count"],
    )


# ── T013: create a general group ────────────────────────────────────────────

async def create_group(profile: dict, payload: CreateGroupRequest) -> GroupSummary:
    _require_verified(profile)
    owner_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO groups (name, type, description, route_tags, owner_id)
                VALUES ($1, 'general', $2, $3, $4)
                RETURNING id, name, type, description, route_tags
                """,
                payload.name, payload.description, payload.route_tags, owner_id,
            )
            await conn.execute(
                "INSERT INTO group_memberships (group_id, user_id, role) VALUES ($1, $2, 'owner')",
                row["id"], owner_id,
            )

    # The membership insert above always succeeds exactly once for a brand-new
    # group, so member_count is deterministically 1 without a second round trip.
    return _to_summary({**dict(row), "member_count": 1})


# ── T015: directory search ──────────────────────────────────────────────────

async def search_groups(
    q: Optional[str],
    type_filter: Optional[str],
    route_tag: Optional[str],
    limit: int,
    offset: int,
) -> GroupListResponse:
    limit = min(max(limit, 1), 50)
    offset = max(offset, 0)

    where = ["archived_at IS NULL"]
    params: list = []

    if q:
        params.append(f"%{q}%")
        where.append(f"name ILIKE ${len(params)}")
    if type_filter:
        params.append(type_filter)
        where.append(f"type = ${len(params)}")
    if route_tag:
        params.append(route_tag)
        where.append(f"${len(params)} = ANY(route_tags)")

    where_clause = " AND ".join(where)

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, name, type, description, route_tags, member_count
            FROM groups
            WHERE {where_clause}
            ORDER BY member_count DESC, name ASC
            LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
            """,
            *params, limit, offset,
        )
        total = await conn.fetchval(f"SELECT COUNT(*) FROM groups WHERE {where_clause}", *params)

    return GroupListResponse(items=[_to_summary(r) for r in rows], total=total)


# ── T017: group detail ──────────────────────────────────────────────────────

async def get_group_detail(group_id: uuid.UUID, user_id: uuid.UUID) -> GroupDetailResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, type, description, route_tags, owner_id, member_count
            FROM groups
            WHERE id = $1 AND archived_at IS NULL
            """,
            group_id,
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )
        membership = await conn.fetchval(
            "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id = $2",
            group_id, user_id,
        )

    return GroupDetailResponse(
        **_to_summary(row).model_dump(),
        is_member=membership is not None,
        is_owner=row["owner_id"] == user_id,
    )


# ── T028 support: groups the caller belongs to ──────────────────────────────

async def list_my_groups(user_id: uuid.UUID) -> list[GroupSummary]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT g.id, g.name, g.type, g.description, g.route_tags, g.member_count
            FROM groups g
            JOIN group_memberships m ON m.group_id = g.id
            WHERE m.user_id = $1 AND g.archived_at IS NULL
            ORDER BY g.name ASC
            """,
            user_id,
        )
    return [_to_summary(r) for r in rows]


# ── T025: group-scoped ride listing ─────────────────────────────────────────

async def list_group_rides(group_id: uuid.UUID, user_id: uuid.UUID) -> RideListResponse:
    from app.services.ride_service import _RIDE_COLS, _to_response

    pool = get_pool()
    async with pool.acquire() as conn:
        group_exists = await conn.fetchval(
            "SELECT 1 FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
        )
        if not group_exists:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )
        is_member = await conn.fetchval(
            "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id = $2",
            group_id, user_id,
        )
        if not is_member:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "not_a_group_member",
                    "message": "You must be a member of this group to view its rides.",
                },
            )
        rows = await conn.fetch(
            f"""
            SELECT {_RIDE_COLS} FROM rides
            WHERE group_id = $1 AND status = 'scheduled' AND departure_datetime > now()
            ORDER BY departure_datetime ASC
            """,
            group_id,
        )

    rides = [_to_response(dict(r)) for r in rows]
    return RideListResponse(rides=rides, total=len(rides), page=1, page_size=len(rides))
