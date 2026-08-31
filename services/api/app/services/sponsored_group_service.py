from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException

from app.core.database import get_pool
from app.models.group import (
    AddFundsResponse,
    DeleteSponsoredGroupResponse,
    GroupSummary,
    SponsoredGroupCreateRequest,
    UnsponsorGroupResponse,
)
from app.services.group_service import _derive_group_name, _get_sponsor_domains, _to_summary


async def list_sponsored_groups() -> list[GroupSummary]:
    """Admin lookup surface for T009's Group ID gap: every other admin action
    on this page (add funds, manage domains, assign a dashboard contact)
    needs a group_id, but create_or_upgrade_sponsored_group only ever returns
    one at creation time — without this, the id is gone the moment the admin
    navigates away or refreshes."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, description, route_tags, member_count,
                   is_sponsored, funded_balance_egp, dashboard_contact_user_id
            FROM groups
            WHERE is_sponsored = true AND archived_at IS NULL
            ORDER BY name ASC
            """
        )
        groups = []
        for row in rows:
            domains = await _get_sponsor_domains(conn, row["id"])
            groups.append(_to_summary({**dict(row), "sponsor_domains": domains}))
    return groups


async def create_or_upgrade_sponsored_group(
    admin_id: uuid.UUID, payload: SponsoredGroupCreateRequest
) -> GroupSummary:
    """Create a new sponsored group covering one or more eligible email
    domains, or add those domains to an existing sponsored group if `name`
    matches one — a sponsored group can list multiple domains (e.g. every
    Cairo University faculty subdomain) so students on different domains
    still land in one shared group rather than being fragmented per-domain."""
    if payload.funded_balance_egp is None or payload.funded_balance_egp < 0:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "funded_balance_egp must be 0.00 or greater"},
        )

    domains = payload.domains

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            claimed = await conn.fetchval(
                "SELECT domain FROM group_sponsor_domains WHERE domain = ANY($1::text[]) LIMIT 1",
                domains,
            )
            if claimed:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "domain_already_sponsored",
                        "message": f"'{claimed}' is already an eligible domain for another sponsored group.",
                    },
                )

            name = (payload.name or "").strip() or _derive_group_name(domains[0])
            existing_name = await conn.fetchval(
                "SELECT id FROM groups WHERE archived_at IS NULL AND lower(name) = lower($1)",
                name,
            )
            if existing_name:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "duplicate_group_name",
                        "message": f"A group named '{name}' already exists. Please choose a different name.",
                    },
                )
            row = await conn.fetchrow(
                """
                INSERT INTO groups
                    (name, description, route_tags, owner_id, is_sponsored, funded_balance_egp)
                VALUES ($1, $2, '{}', $3, true, $4)
                RETURNING id, name, description, route_tags, member_count,
                          is_sponsored, funded_balance_egp, dashboard_contact_user_id
                """,
                name,
                f"Sponsored group for {', '.join(domains)}.",
                admin_id,
                payload.funded_balance_egp,
            )
            await conn.execute(
                "INSERT INTO group_memberships (group_id, user_id, role) VALUES ($1, $2, 'owner')",
                row["id"],
                admin_id,
            )
            await conn.executemany(
                "INSERT INTO group_sponsor_domains (group_id, domain) VALUES ($1, $2)",
                [(row["id"], d) for d in domains],
            )

    return _to_summary({**dict(row), "member_count": 1, "sponsor_domains": domains})


async def add_sponsor_domain(group_id: uuid.UUID, domain: str) -> "SponsorDomainsResponse":
    """Add another eligible domain to an existing sponsored group — the fix
    for domain fragmentation: an admin can attach every subdomain of the same
    organization to one group instead of creating a separate group per domain."""
    from app.models.group import SponsorDomainsResponse

    domain = domain.strip().lower()
    if not domain:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_domain", "message": "domain must not be empty"},
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            group_row = await conn.fetchrow(
                "SELECT id, is_sponsored FROM groups WHERE id = $1 AND archived_at IS NULL FOR UPDATE",
                group_id,
            )
            if group_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "group_not_found", "message": "Group not found."},
                )
            if not group_row["is_sponsored"]:
                raise HTTPException(
                    status_code=422,
                    detail={"error": "not_sponsored", "message": "This group is not sponsored."},
                )

            claimed_by_other = await conn.fetchval(
                "SELECT group_id FROM group_sponsor_domains WHERE domain = $1", domain
            )
            if claimed_by_other is not None and claimed_by_other != group_id:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "domain_already_sponsored",
                        "message": "This domain is already eligible for another sponsored group.",
                    },
                )
            if claimed_by_other is None:
                await conn.execute(
                    "INSERT INTO group_sponsor_domains (group_id, domain) VALUES ($1, $2)",
                    group_id, domain,
                )

            domains = await conn.fetch(
                "SELECT domain FROM group_sponsor_domains WHERE group_id = $1 ORDER BY domain ASC",
                group_id,
            )

    return SponsorDomainsResponse(group_id=str(group_id), domains=[d["domain"] for d in domains])


async def remove_sponsor_domain(group_id: uuid.UUID, domain: str) -> "SponsorDomainsResponse":
    from app.models.group import SponsorDomainsResponse

    domain = domain.strip().lower()

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            group_exists = await conn.fetchval(
                "SELECT 1 FROM groups WHERE id = $1 AND archived_at IS NULL", group_id
            )
            if not group_exists:
                raise HTTPException(
                    status_code=404,
                    detail={"error": "group_not_found", "message": "Group not found."},
                )
            await conn.execute(
                "DELETE FROM group_sponsor_domains WHERE group_id = $1 AND domain = $2",
                group_id, domain,
            )
            domains = await conn.fetch(
                "SELECT domain FROM group_sponsor_domains WHERE group_id = $1 ORDER BY domain ASC",
                group_id,
            )

    return SponsorDomainsResponse(group_id=str(group_id), domains=[d["domain"] for d in domains])


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


async def delete_sponsored_group(group_id: uuid.UUID) -> DeleteSponsoredGroupResponse:
    """Admin action: soft-delete (archive) a sponsored group. Releases its
    claimed domains so they can be attached to a different sponsored group
    later, and reports whatever funded balance was still on the books at
    deletion time so the admin has an audit trail of what was cleared."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, is_sponsored, funded_balance_egp FROM groups "
                "WHERE id = $1 AND archived_at IS NULL FOR UPDATE",
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

            await conn.execute(
                "UPDATE groups SET archived_at = now(), funded_balance_egp = 0 WHERE id = $1",
                group_id,
            )
            await conn.execute("DELETE FROM group_sponsor_domains WHERE group_id = $1", group_id)

    return DeleteSponsoredGroupResponse(
        group_id=str(group_id), cleared_funded_balance_egp=row["funded_balance_egp"]
    )


async def unsponsor_group(group_id: uuid.UUID) -> UnsponsorGroupResponse:
    """Admin action: convert a sponsored group back to a regular, unfunded
    group. Unlike delete, the group and its memberships stay active — only
    sponsorship (is_sponsored, funded balance, eligible domains) is removed."""
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, is_sponsored, funded_balance_egp FROM groups "
                "WHERE id = $1 AND archived_at IS NULL FOR UPDATE",
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

            await conn.execute(
                "UPDATE groups SET is_sponsored = false, funded_balance_egp = 0 WHERE id = $1",
                group_id,
            )
            await conn.execute("DELETE FROM group_sponsor_domains WHERE group_id = $1", group_id)

    return UnsponsorGroupResponse(
        group_id=str(group_id),
        is_sponsored=False,
        cleared_funded_balance_egp=row["funded_balance_egp"],
    )
