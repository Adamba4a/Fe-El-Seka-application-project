from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_pool
from app.models.group import (
    CreateGroupRequest,
    DashboardContactResponse,
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
    SponsorshipActivityItem,
    SponsorshipDashboardResponse,
)
from app.models.ride import RideListResponse
from app.services import notification_service
from app.services.domain_verification_service import (
    _check_domain_otp_resend_rate,
    _generate_otp,
    _get_domain_blocklist,
    _get_platform_setting,
    _hash_otp,
)


def _derive_group_name(domain: str) -> str:
    label = domain.split(".")[0]
    words = [w for w in re.split(r"[-_]+", label) if w]
    return " ".join(w.capitalize() for w in words) or domain


async def _get_new_domain_rate_limit(conn) -> tuple[int, int]:
    limit = int(await _get_platform_setting(conn, "group_new_domain_rate_limit", "5"))
    window_minutes = int(
        await _get_platform_setting(conn, "group_new_domain_rate_limit_window_minutes", "60")
    )
    return limit, window_minutes


def _require_verified(profile: dict) -> None:
    # Groups' trust floor is org-email verification (Spec 025), not National ID
    # (Spec 021) — a user who signed in with a verified company/university email
    # can create, join, and domain-verify groups without completing ID
    # verification. Mirrors dependencies/org_access.require_org_verified, but
    # applied inline here since these checks live inside the service layer
    # rather than as router-level dependencies.
    if profile.get("org_verified_at") is None:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "org_verification_required",
                "message": "You must verify a company or university email before using Groups.",
            },
        )


def _to_membership(row) -> MembershipResponse:
    return MembershipResponse(
        id=str(row["id"]),
        group_id=str(row["group_id"]),
        user_id=str(row["user_id"]),
        role=row["role"],
        joined_at=row["joined_at"].isoformat(),
    )


def _to_summary(row) -> GroupSummary:
    d = dict(row)
    dashboard_contact_user_id = d.get("dashboard_contact_user_id")
    return GroupSummary(
        id=str(d["id"]),
        name=d["name"],
        type=d["type"],
        description=d["description"],
        route_tags=list(d["route_tags"]) if d["route_tags"] else [],
        member_count=d["member_count"],
        is_sponsored=bool(d.get("is_sponsored", False)),
        funded_balance_egp=d.get("funded_balance_egp", Decimal("0.00")),
        dashboard_contact_user_id=str(dashboard_contact_user_id) if dashboard_contact_user_id else None,
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
            SELECT id, name, type, description, route_tags, member_count,
                   is_sponsored, funded_balance_egp, dashboard_contact_user_id
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
            SELECT id, name, type, description, route_tags, owner_id, member_count,
                   is_sponsored, funded_balance_egp, dashboard_contact_user_id
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
            SELECT g.id, g.name, g.type, g.description, g.route_tags, g.member_count,
                   g.is_sponsored, g.funded_balance_egp, g.dashboard_contact_user_id
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


# ── T030: generate/regenerate the owner's invite link ──────────────────────

async def generate_invite_link(group_id: uuid.UUID, user_id: uuid.UUID) -> InviteLinkResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT owner_id FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
        )
        if group_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )
        if group_row["owner_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "not_group_owner",
                    "message": "Only the group owner can manage its invite link.",
                },
            )

        row = await conn.fetchrow(
            """
            UPDATE groups
            SET invite_token = replace(gen_random_uuid()::text, '-', '')
            WHERE id = $1
            RETURNING invite_token
            """,
            group_id,
        )

    invite_token = row["invite_token"]
    return InviteLinkResponse(
        invite_token=invite_token,
        invite_url=f"{settings.frontend_base_url}/groups/join/{invite_token}",
    )


# ── T032: resolve an invite token to the join screen's group detail ────────

async def resolve_invite_token(invite_token: str, user_id: uuid.UUID) -> GroupDetailResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, type, description, route_tags, owner_id, member_count,
                   is_sponsored, funded_balance_egp, dashboard_contact_user_id
            FROM groups
            WHERE invite_token = $1 AND archived_at IS NULL
            """,
            invite_token,
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "invite_link_invalid",
                    "message": "This invite link is invalid, expired, or has been revoked.",
                },
            )
        membership = await conn.fetchval(
            "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id = $2",
            row["id"], user_id,
        )

    return GroupDetailResponse(
        **_to_summary(row).model_dump(),
        is_member=membership is not None,
        is_owner=row["owner_id"] == user_id,
    )


# ── T033: join a general group (directory or resolved-invite-link path) ────

async def join_group(profile: dict, group_id: uuid.UUID) -> MembershipResponse:
    _require_verified(profile)
    user_id = uuid.UUID(str(profile["id"]))

    pool = get_pool()
    async with pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT id, type FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
        )
        if group_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )

        existing = await conn.fetchrow(
            """
            SELECT id, group_id, user_id, role, joined_at
            FROM group_memberships WHERE group_id = $1 AND user_id = $2
            """,
            group_id, user_id,
        )
        if existing is not None:
            return _to_membership(existing)

        if group_row["type"] != "general":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "domain_verification_required",
                    "message": "You must verify a matching company or university email to join this group.",
                },
            )

        membership = await conn.fetchrow(
            """
            INSERT INTO group_memberships (group_id, user_id, role)
            VALUES ($1, $2, 'member')
            RETURNING id, group_id, user_id, role, joined_at
            """,
            group_id, user_id,
        )

    return _to_membership(membership)


# ── T038/T039: request a company/university domain-verification OTP ────────

async def request_domain_verification(
    profile: dict, payload: DomainVerificationRequest
) -> DomainVerificationRequestResponse:
    _require_verified(profile)
    user_id = uuid.UUID(str(profile["id"]))

    email = payload.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_email", "message": "Enter a valid email address."},
        )
    domain = email.rsplit("@", 1)[1]

    pool = get_pool()
    async with pool.acquire() as conn:
        blocklist = await _get_domain_blocklist(conn)
        if domain in blocklist:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "blocklisted_domain",
                    "message": "Personal email providers can't be used for company or university groups.",
                },
            )

        _check_domain_otp_resend_rate(email)

        is_first_for_domain = not await conn.fetchval(
            "SELECT 1 FROM domain_verifications WHERE domain = $1 AND verified_at IS NOT NULL",
            domain,
        )

        code = _generate_otp()
        salt = secrets.token_hex(16)
        otp_hash = f"{salt}${_hash_otp(code, salt)}"

        row = await conn.fetchrow(
            """
            INSERT INTO domain_verifications
                (user_id, email, domain, requested_group_type, otp_code_hash, otp_expires_at, is_first_for_domain)
            VALUES ($1, $2, $3, $4, $5, now() + interval '5 minutes', $6)
            RETURNING id
            """,
            user_id, email, domain, payload.requested_group_type, otp_hash, is_first_for_domain,
        )

    try:
        await notification_service.send_domain_verification_email(email, code)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "otp_send_failed",
                "message": "Could not send the verification code. Try again.",
            },
        )

    return DomainVerificationRequestResponse(verification_id=str(row["id"]), expires_in_seconds=300)


# ── T041: confirm the OTP, then create/attach the domain's group ───────────

async def confirm_domain_verification(
    profile: dict, payload: DomainVerificationConfirm
) -> DomainVerificationConfirmResponse:
    _require_verified(profile)
    user_id = uuid.UUID(str(profile["id"]))
    try:
        verification_id = uuid.UUID(payload.verification_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "otp_invalid", "message": "Incorrect code."},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            verification = await conn.fetchrow(
                """
                SELECT id, domain, requested_group_type, otp_code_hash, otp_expires_at,
                       verified_at, is_first_for_domain
                FROM domain_verifications
                WHERE id = $1 AND user_id = $2
                FOR UPDATE
                """,
                verification_id, user_id,
            )
            if verification is None:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "otp_invalid", "message": "Incorrect code."},
                )

            if verification["verified_at"] is not None:
                # A verification_id is single-use: once confirmed, it must not be
                # replayable to re-grant membership without a fresh OTP challenge.
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "otp_already_used",
                        "message": "This code has already been used. Request a new one.",
                    },
                )

            if verification["otp_expires_at"] < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=410,
                    detail={
                        "error": "otp_expired",
                        "message": "Code has expired. Request a new one.",
                    },
                )
            salt, _, expected_hash = verification["otp_code_hash"].partition("$")
            if _hash_otp(payload.code.strip(), salt) != expected_hash:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "otp_invalid", "message": "Incorrect code."},
                )
            await conn.execute(
                "UPDATE domain_verifications SET verified_at = now() WHERE id = $1",
                verification_id,
            )

            domain = verification["domain"]

            # Spec 025 (org-only access gate): a successful Groups domain
            # verification also satisfies the org-email gate, but only credits
            # it once — a later verification of a second domain (e.g. to join
            # another group) must not overwrite the account's original grant.
            await conn.execute(
                """
                UPDATE profiles
                SET org_verified_at = now(),
                    org_verified_domain = $2
                WHERE id = $1 AND org_verified_at IS NULL
                """,
                user_id, domain,
            )

            group_row = await conn.fetchrow(
                """
                SELECT id, name, type, description, route_tags, owner_id, member_count, archived_at
                FROM groups WHERE domain = $1
                """,
                domain,
            )

            if group_row is not None and group_row["archived_at"] is not None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "domain_group_archived",
                        "message": "The group for this domain has been archived and is no longer accepting members.",
                    },
                )

            created_new_group = False
            if group_row is None:
                if verification["is_first_for_domain"]:
                    limit, window_minutes = await _get_new_domain_rate_limit(conn)
                    # Exclude the verification row we just marked verified_at on above —
                    # otherwise this confirmation counts itself, tightening the effective
                    # quota to limit - 1.
                    recent_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM domain_verifications
                        WHERE is_first_for_domain = true
                          AND verified_at IS NOT NULL
                          AND id != $1
                          AND created_at > now() - ($2 || ' minutes')::interval
                        """,
                        verification_id,
                        str(window_minutes),
                    )
                    if recent_count >= limit:
                        raise HTTPException(
                            status_code=429,
                            detail={
                                "error": "domain_registration_rate_limited",
                                "message": (
                                    "Too many new company/university domains registered "
                                    "recently. Try again later."
                                ),
                            },
                        )

                # ON CONFLICT guards against a concurrent first-verifier on the
                # same domain winning the race between our existence check
                # above and this insert.
                group_row = await conn.fetchrow(
                    """
                    INSERT INTO groups (name, type, description, route_tags, owner_id, domain)
                    VALUES ($1, $2, $3, '{}', $4, $5)
                    ON CONFLICT (domain) DO NOTHING
                    RETURNING id, name, type, description, route_tags, owner_id, member_count,
                              is_sponsored, funded_balance_egp, dashboard_contact_user_id
                    """,
                    _derive_group_name(domain), verification["requested_group_type"],
                    f"Domain-verified group for {domain}.", user_id, domain,
                )
                created_new_group = group_row is not None
                if group_row is None:
                    group_row = await conn.fetchrow(
                        """
                        SELECT id, name, type, description, route_tags, owner_id, member_count,
                               is_sponsored, funded_balance_egp, dashboard_contact_user_id
                        FROM groups WHERE domain = $1 AND archived_at IS NULL
                        """,
                        domain,
                    )
                    if group_row is None:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "error": "domain_group_archived",
                                "message": (
                                    "The group for this domain has been archived and is "
                                    "no longer accepting members."
                                ),
                            },
                        )

            if created_new_group:
                await conn.execute(
                    """
                    INSERT INTO group_memberships (group_id, user_id, role, domain_verification_id)
                    VALUES ($1, $2, 'owner', $3)
                    """,
                    group_row["id"], user_id, verification_id,
                )
                membership = await conn.fetchrow(
                    """
                    SELECT id, group_id, user_id, role, joined_at
                    FROM group_memberships WHERE group_id = $1 AND user_id = $2
                    """,
                    group_row["id"], user_id,
                )
            else:
                membership = await conn.fetchrow(
                    """
                    SELECT id, group_id, user_id, role, joined_at
                    FROM group_memberships WHERE group_id = $1 AND user_id = $2
                    """,
                    group_row["id"], user_id,
                )
                if membership is None:
                    membership = await conn.fetchrow(
                        """
                        INSERT INTO group_memberships (group_id, user_id, role, domain_verification_id)
                        VALUES ($1, $2, 'member', $3)
                        RETURNING id, group_id, user_id, role, joined_at
                        """,
                        group_row["id"], user_id, verification_id,
                    )

            # Re-fetch: the membership INSERT above fires trg_group_memberships_count,
            # so group_row's member_count (captured before/around that insert) is stale.
            group_row = await conn.fetchrow(
                """
                SELECT id, name, type, description, route_tags, owner_id, member_count,
                       is_sponsored, funded_balance_egp, dashboard_contact_user_id
                FROM groups WHERE id = $1
                """,
                group_row["id"],
            )

    return DomainVerificationConfirmResponse(
        membership=_to_membership(membership),
        group=_to_summary(group_row),
    )


# ── T053 support: list a group's members (for the MemberList UI) ───────────

async def list_group_members(group_id: uuid.UUID, user_id: uuid.UUID) -> list[GroupMemberResponse]:
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
                    "message": "You must be a member of this group to view its members.",
                },
            )
        rows = await conn.fetch(
            """
            SELECT m.id, m.user_id, p.display_name, m.role, m.joined_at
            FROM group_memberships m
            JOIN profiles p ON p.id = m.user_id
            WHERE m.group_id = $1
            ORDER BY (m.role = 'owner') DESC, m.joined_at ASC
            """,
            group_id,
        )

    return [
        GroupMemberResponse(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            display_name=r["display_name"],
            role=r["role"],
            joined_at=r["joined_at"].isoformat(),
        )
        for r in rows
    ]


# ── T047: a member leaves a group ───────────────────────────────────────────

async def leave_group(group_id: uuid.UUID, user_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            membership = await conn.fetchrow(
                "SELECT role FROM group_memberships WHERE group_id = $1 AND user_id = $2 FOR UPDATE",
                group_id, user_id,
            )
            if membership is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "not_a_group_member", "message": "You are not a member of this group."},
                )

            if membership["role"] == "owner":
                other_members = await conn.fetchval(
                    "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id != $2",
                    group_id, user_id,
                )
                if other_members:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "ownership_transfer_required",
                            "message": "Transfer ownership to another member before leaving this group.",
                        },
                    )

            await conn.execute(
                "DELETE FROM group_memberships WHERE group_id = $1 AND user_id = $2",
                group_id, user_id,
            )


# ── T049: owner removes another member ──────────────────────────────────────

async def remove_member(group_id: uuid.UUID, owner_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT owner_id FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
        )
        if group_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )
        if group_row["owner_id"] != owner_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "not_group_owner", "message": "Only the group owner can remove members."},
            )
        if target_user_id == owner_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "cannot_remove_owner",
                    "message": "The owner can't remove themselves. Transfer ownership or leave instead.",
                },
            )

        result = await conn.execute(
            "DELETE FROM group_memberships WHERE group_id = $1 AND user_id = $2",
            group_id, target_user_id,
        )
        if result == "DELETE 0":
            raise HTTPException(
                status_code=404,
                detail={"error": "not_a_group_member", "message": "That user is not a member of this group."},
            )


# ── T050: transfer group ownership to another member ────────────────────────

async def transfer_ownership(
    group_id: uuid.UUID, owner_id: uuid.UUID, new_owner_user_id: str
) -> GroupSummary:
    try:
        new_owner_id = uuid.UUID(new_owner_user_id)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_user_id", "message": "new_owner_user_id must be a valid UUID."},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            group_row = await conn.fetchrow(
                "SELECT owner_id FROM groups WHERE id = $1 AND archived_at IS NULL FOR UPDATE",
                group_id,
            )
            if group_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "group_not_found", "message": "Group not found."},
                )
            if group_row["owner_id"] != owner_id:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "not_group_owner",
                        "message": "Only the group owner can transfer ownership.",
                    },
                )
            if new_owner_id == owner_id:
                raise HTTPException(
                    status_code=400,
                    detail={"error": "already_owner", "message": "That user is already the owner."},
                )

            target_is_member = await conn.fetchval(
                "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id = $2",
                group_id, new_owner_id,
            )
            if not target_is_member:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "not_a_group_member",
                        "message": "The new owner must already be a member of this group.",
                    },
                )

            await conn.execute(
                "UPDATE group_memberships SET role = 'member' WHERE group_id = $1 AND user_id = $2",
                group_id, owner_id,
            )
            await conn.execute(
                "UPDATE group_memberships SET role = 'owner' WHERE group_id = $1 AND user_id = $2",
                group_id, new_owner_id,
            )
            row = await conn.fetchrow(
                """
                UPDATE groups SET owner_id = $2 WHERE id = $1
                RETURNING id, name, type, description, route_tags, member_count,
                          is_sponsored, funded_balance_egp, dashboard_contact_user_id
                """,
                group_id, new_owner_id,
            )

    return _to_summary(row)


# ── T028: list a sponsored group's members for the admin UI (no membership
# requirement on the caller — admins aren't members of the org they sponsor) ─
async def list_members_admin(group_id: uuid.UUID) -> list[GroupMemberResponse]:
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
        rows = await conn.fetch(
            """
            SELECT m.id, m.user_id, p.display_name, m.role, m.joined_at
            FROM group_memberships m
            JOIN profiles p ON p.id = m.user_id
            WHERE m.group_id = $1
            ORDER BY (m.role = 'owner') DESC, m.joined_at ASC
            """,
            group_id,
        )

    return [
        GroupMemberResponse(
            id=str(r["id"]),
            user_id=str(r["user_id"]),
            display_name=r["display_name"],
            role=r["role"],
            joined_at=r["joined_at"].isoformat(),
        )
        for r in rows
    ]


# ── T024: assign/reassign the sponsorship dashboard contact ────────────────
async def set_dashboard_contact(
    group_id: uuid.UUID, admin_id: uuid.UUID, user_id: str
) -> DashboardContactResponse:
    try:
        target_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_user_id", "message": "user_id must be a valid UUID."},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            group_row = await conn.fetchrow(
                "SELECT id FROM groups WHERE id = $1 AND archived_at IS NULL FOR UPDATE",
                group_id,
            )
            if group_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "group_not_found", "message": "Group not found."},
                )

            target_is_member = await conn.fetchval(
                "SELECT 1 FROM group_memberships WHERE group_id = $1 AND user_id = $2",
                group_id, target_user_id,
            )
            if not target_is_member:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "not_a_group_member",
                        "message": "The dashboard contact must already be a member of this group.",
                    },
                )

            row = await conn.fetchrow(
                "UPDATE groups SET dashboard_contact_user_id = $2 WHERE id = $1 "
                "RETURNING id, dashboard_contact_user_id",
                group_id, target_user_id,
            )

    return DashboardContactResponse(
        group_id=str(row["id"]), dashboard_contact_user_id=str(row["dashboard_contact_user_id"])
    )


# ── T025: read-only sponsorship dashboard for the assigned contact ─────────
async def get_sponsorship_dashboard(
    group_id: uuid.UUID, requesting_user_id: uuid.UUID
) -> SponsorshipDashboardResponse:
    pool = get_pool()
    async with pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT funded_balance_egp, member_count, is_sponsored, dashboard_contact_user_id "
            "FROM groups WHERE id = $1 AND archived_at IS NULL",
            group_id,
        )
        if group_row is None or not group_row["is_sponsored"]:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Sponsored group not found."},
            )
        if group_row["dashboard_contact_user_id"] != requesting_user_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "not_dashboard_contact",
                    "message": "Only the assigned dashboard contact can view this dashboard.",
                },
            )

        activity_rows = await conn.fetch(
            """
            SELECT dle.type, dle.amount_egp, dle.ride_id, dle.booking_id, dle.created_at
            FROM driver_ledger_entries dle
            JOIN rides r ON r.id = dle.ride_id
            WHERE r.group_id = $1
              AND dle.type IN ('SPONSORED_RIDE_CREDIT', 'SPONSORED_RIDE_REVERSAL')
            ORDER BY dle.created_at DESC
            LIMIT 50
            """,
            group_id,
        )

    return SponsorshipDashboardResponse(
        funded_balance_egp=group_row["funded_balance_egp"],
        member_count=group_row["member_count"],
        recent_activity=[
            SponsorshipActivityItem(
                type=r["type"],
                amount_egp=r["amount_egp"],
                ride_id=str(r["ride_id"]),
                booking_id=str(r["booking_id"]),
                created_at=r["created_at"].isoformat(),
            )
            for r in activity_rows
        ],
    )


# ── T051: archive (soft-delete) a group ─────────────────────────────────────

async def archive_group(group_id: uuid.UUID, owner_id: uuid.UUID) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        group_row = await conn.fetchrow(
            "SELECT owner_id FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
        )
        if group_row is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "group_not_found", "message": "Group not found."},
            )
        if group_row["owner_id"] != owner_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "not_group_owner", "message": "Only the group owner can archive this group."},
            )

        await conn.execute("UPDATE groups SET archived_at = now() WHERE id = $1", group_id)
