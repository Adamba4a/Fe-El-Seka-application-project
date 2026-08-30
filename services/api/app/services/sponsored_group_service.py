from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException

from app.core.database import get_pool
from app.models.group import AddFundsResponse, GroupSummary, SponsoredGroupCreateRequest
from app.services.group_service import _derive_group_name, _to_summary


async def create_or_upgrade_sponsored_group(
    admin_id: uuid.UUID, payload: SponsoredGroupCreateRequest
) -> GroupSummary:
    """T007: create a new sponsored group for `domain`, or auto-upgrade an
    existing non-sponsored one in place (FR-001/002/003, research.md §1,
    clarification #1 — never a second record for the same domain)."""
    if payload.funded_balance_egp is None or payload.funded_balance_egp < 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "funded_balance_egp must be 0.00 or greater"},
        )

    domain = payload.domain.strip().lower()

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id, is_sponsored FROM groups WHERE domain = $1 AND archived_at IS NULL FOR UPDATE",
                domain,
            )

            if existing is not None:
                if existing["is_sponsored"]:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "already_sponsored",
                            "message": "This domain's group is already sponsored.",
                        },
                    )
                row = await conn.fetchrow(
                    """
                    UPDATE groups
                    SET is_sponsored = true, funded_balance_egp = $2
                    WHERE id = $1
                    RETURNING id, name, type, description, route_tags, member_count,
                              is_sponsored, funded_balance_egp, dashboard_contact_user_id
                    """,
                    existing["id"],
                    payload.funded_balance_egp,
                )
                return _to_summary(row)

            name = (payload.name or "").strip() or _derive_group_name(domain)
            row = await conn.fetchrow(
                """
                INSERT INTO groups
                    (name, type, description, route_tags, owner_id, domain, is_sponsored, funded_balance_egp)
                VALUES ($1, $2, $3, '{}', $4, $5, true, $6)
                RETURNING id, name, type, description, route_tags, member_count,
                          is_sponsored, funded_balance_egp, dashboard_contact_user_id
                """,
                name,
                payload.requested_group_type,
                f"Sponsored group for {domain}.",
                admin_id,
                domain,
                payload.funded_balance_egp,
            )
            await conn.execute(
                "INSERT INTO group_memberships (group_id, user_id, role) VALUES ($1, $2, 'owner')",
                row["id"],
                admin_id,
            )

    return _to_summary({**dict(row), "member_count": 1})


async def add_funds(group_id: uuid.UUID, amount_egp: Decimal) -> AddFundsResponse:
    """T008: top up a sponsored group's funded balance (FR-002)."""
    if amount_egp is None or amount_egp <= 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "amount_egp must be greater than 0.00 EGP"},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, is_sponsored, funded_balance_egp FROM groups WHERE id = $1 FOR UPDATE",
                group_id,
            )
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "group_not_found", "message": "Group not found."},
                )
            if not row["is_sponsored"]:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "not_sponsored", "message": "This group is not sponsored."},
                )

            updated = await conn.fetchrow(
                """
                UPDATE groups SET funded_balance_egp = funded_balance_egp + $2
                WHERE id = $1
                RETURNING funded_balance_egp
                """,
                group_id,
                amount_egp,
            )

    return AddFundsResponse(group_id=str(group_id), new_funded_balance_egp=updated["funded_balance_egp"])
