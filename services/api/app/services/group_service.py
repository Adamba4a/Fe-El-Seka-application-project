from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from fastapi import HTTPException

from app.core.config import settings
from app.core.database import get_pool
from app.models.group import (
    CreateGroupRequest,
    DomainVerificationConfirm,
    DomainVerificationConfirmResponse,
    DomainVerificationRequest,
    DomainVerificationRequestResponse,
    GroupDetailResponse,
    GroupListResponse,
    GroupSummary,
    InviteLinkResponse,
    MembershipResponse,
)
from app.models.ride import RideListResponse
from app.services import notification_service

# In-memory rate limiter keyed by email, mirroring auth_service's
# resend-rate-limit shape (own tracker/keyspace since this gates a
# different email flow — domain verification, not login).
_domain_otp_resend_tracker: dict[str, list[float]] = defaultdict(list)
_domain_otp_resend_lock = Lock()
_RESEND_WINDOW_SECONDS = 900  # 15 minutes
_RESEND_MAX = 3


def _check_domain_otp_resend_rate(email: str) -> None:
    now = time.time()
    with _domain_otp_resend_lock:
        timestamps = [
            t for t in _domain_otp_resend_tracker[email]
            if now - t < _RESEND_WINDOW_SECONDS
        ]
        if len(timestamps) >= _RESEND_MAX:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "otp_rate_limited",
                    "message": "Too many verification requests. Try again in 15 minutes.",
                    "retry_after_seconds": _RESEND_WINDOW_SECONDS,
                },
            )
        timestamps.append(now)
        _domain_otp_resend_tracker[email] = timestamps


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash_otp(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def _derive_group_name(domain: str) -> str:
    label = domain.split(".")[0]
    words = [w for w in re.split(r"[-_]+", label) if w]
    return " ".join(w.capitalize() for w in words) or domain


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


def _to_membership(row) -> MembershipResponse:
    return MembershipResponse(
        id=str(row["id"]),
        group_id=str(row["group_id"]),
        user_id=str(row["user_id"]),
        role=row["role"],
        joined_at=row["joined_at"].isoformat(),
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
            SET invite_token = replace(gen_random_uuid()::text, '-', ''),
                invite_token_revoked_at = now()
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
            SELECT id, name, type, description, route_tags, owner_id, member_count
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

            if verification["verified_at"] is None:
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
                    recent_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM domain_verifications
                        WHERE is_first_for_domain = true
                          AND verified_at IS NOT NULL
                          AND created_at > now() - ($1 || ' minutes')::interval
                        """,
                        str(window_minutes),
                    )
                    if recent_count >= limit:
                        raise HTTPException(
                            status_code=429,
                            detail={
                                "error": "domain_registration_rate_limited",
                                "message": "Too many new company/university domains registered recently. Try again later.",
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
                    RETURNING id, name, type, description, route_tags, owner_id, member_count
                    """,
                    _derive_group_name(domain), verification["requested_group_type"],
                    f"Domain-verified group for {domain}.", user_id, domain,
                )
                created_new_group = group_row is not None
                if group_row is None:
                    group_row = await conn.fetchrow(
                        """
                        SELECT id, name, type, description, route_tags, owner_id, member_count
                        FROM groups WHERE domain = $1 AND archived_at IS NULL
                        """,
                        domain,
                    )
                    if group_row is None:
                        raise HTTPException(
                            status_code=409,
                            detail={
                                "error": "domain_group_archived",
                                "message": "The group for this domain has been archived and is no longer accepting members.",
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

    return DomainVerificationConfirmResponse(
        membership=_to_membership(membership),
        group=_to_summary(group_row),
    )
