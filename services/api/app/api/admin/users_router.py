import json
import logging
import time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.core.config import settings
from app.dependencies.roles import get_current_admin
from app.services import audit_service, auth_service, storage_service

router = APIRouter()
logger = logging.getLogger(__name__)

_VALID_ROLES = ("passenger", "driver", "admin")
_VALID_STATUSES = ("unverified", "pending_review", "verified", "rejected", "suspended")


class SuspendRequest(BaseModel):
    reason: str


def _supabase():
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@router.get("/")
def list_users(
    q: str | None = None,
    role: str | None = None,
    status: str | None = None,
    page: int = 1,
    limit: int = 20,
    _profile: dict = Depends(get_current_admin),
) -> dict:
    if role is not None and role not in _VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"role must be one of {', '.join(_VALID_ROLES)}"},
        )
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": f"status must be one of {', '.join(_VALID_STATUSES)}"},
        )
    limit = min(max(limit, 1), 100)
    page = max(page, 1)

    sb = _supabase()

    def _filtered(query):
        if role:
            query = query.eq("role", role)
        if status:
            query = query.eq("verification_status", status)
        if q:
            query = query.or_(f"display_name.ilike.%{q}%,email.ilike.%{q}%")
        return query

    total = (
        _filtered(sb.table("profiles").select("id", count="exact")).execute().count or 0
    )

    offset = (page - 1) * limit
    resp = (
        _filtered(
            sb.table("profiles").select(
                "id, display_name, email, role, verification_status, created_at"
            )
        )
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    items = [
        {
            "user_id": row["id"],
            "display_name": row.get("display_name") or "",
            "email": row.get("email") or "",
            "role": row["role"],
            "verification_status": row["verification_status"],
            "created_at": str(row["created_at"]),
        }
        for row in (resp.data or [])
    ]
    return {"total": total, "page": page, "items": items}


@router.get("/{user_id}")
def get_user_detail(
    user_id: str,
    _profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    p = (
        sb.table("profiles")
        .select(
            "id, display_name, email, role, verification_status, created_at,"
            " phone_number, profile_photo_path, org_verified_at, org_verified_domain"
        )
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not p or not p.data:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "User not found"})

    row = p.data
    role = row["role"]

    result: dict = {
        "profile": {
            "user_id": row["id"],
            "display_name": row.get("display_name") or "",
            "email": row.get("email") or "",
            "phone_number": row.get("phone_number"),
            "role": role,
            "verification_status": row["verification_status"],
            "created_at": str(row["created_at"]),
            "is_admin_role": role == "admin",
            "profile_photo_signed_url": storage_service.generate_signed_url(
                "profile-photos", row.get("profile_photo_path")
            ),
            "org_verified_at": (
                str(row["org_verified_at"]) if row.get("org_verified_at") else None
            ),
            "org_verified_domain": row.get("org_verified_domain"),
        },
        "rides": [],
        "bookings": [],
    }

    if role == "driver":
        rides_resp = (
            sb.table("rides")
            .select("id, status, created_at")
            .eq("driver_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        result["rides"] = [
            {"ride_id": r["id"], "status": r["status"], "created_at": str(r["created_at"])}
            for r in (rides_resp.data or [])
        ]

        vehicle_resp = (
            sb.table("vehicles")
            .select("id, plate_number, make, model, year, color, seat_count, is_active, registered_at")
            .eq("driver_id", user_id)
            .maybe_single()
            .execute()
        )
        vehicle_row = vehicle_resp.data if vehicle_resp else None
        result["vehicle"] = (
            {
                "vehicle_id": vehicle_row["id"],
                "plate_number": vehicle_row["plate_number"],
                "make": vehicle_row["make"],
                "model": vehicle_row["model"],
                "year": vehicle_row["year"],
                "color": vehicle_row["color"],
                "seat_count": vehicle_row["seat_count"],
                "is_active": vehicle_row["is_active"],
                "registered_at": str(vehicle_row["registered_at"]),
            }
            if vehicle_row
            else None
        )

    if role == "passenger":
        bookings_resp = (
            sb.table("bookings")
            .select("id, status, created_at")
            .eq("passenger_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        result["bookings"] = [
            {"booking_id": b["id"], "status": b["status"], "created_at": str(b["created_at"])}
            for b in (bookings_resp.data or [])
        ]

    ratings_resp = (
        sb.table("ratings")
        .select("stars, comment, created_at")
        .eq("ratee_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    rating_items = ratings_resp.data or []
    rating_count = len(rating_items)
    rating_avg = round(sum(i["stars"] for i in rating_items) / rating_count, 2) if rating_count else 0.0
    result["ratings_received"] = {
        "rating_avg": rating_avg,
        "rating_count": rating_count,
        "items": [
            {"stars": i["stars"], "comment": i.get("comment"), "created_at": str(i["created_at"])}
            for i in rating_items
        ],
    }

    filed_by_resp = (
        sb.table("reports")
        .select("id, status, created_at")
        .eq("reporter_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    filed_against_resp = (
        sb.table("reports")
        .select("id, status, created_at")
        .eq("reported_user_id", user_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    result["reports"] = {
        "filed_by_user": [
            {"report_id": r["id"], "status": r["status"], "created_at": str(r["created_at"])}
            for r in (filed_by_resp.data or [])
        ],
        "filed_against_user": [
            {"report_id": r["id"], "status": r["status"], "created_at": str(r["created_at"])}
            for r in (filed_against_resp.data or [])
        ],
    }

    if role == "driver":
        wallet_resp = (
            sb.table("driver_wallets")
            .select("balance_egp, reserved_egp")
            .eq("driver_id", user_id)
            .maybe_single()
            .execute()
        )
        wallet_row = wallet_resp.data if wallet_resp else None
        balance = Decimal(str(wallet_row["balance_egp"])) if wallet_row else Decimal("0.00")
        reserved = Decimal(str(wallet_row["reserved_egp"])) if wallet_row else Decimal("0.00")
        available = balance - reserved

        ledger_resp = (
            sb.table("driver_ledger_entries")
            .select("id, type, amount_egp, created_at")
            .eq("driver_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        result["wallet"] = {
            "balance_egp": str(balance),
            "available_egp": str(available),
            "recent_ledger": [
                {
                    "id": e["id"],
                    "type": e["type"],
                    "amount_egp": str(e["amount_egp"]),
                    "created_at": str(e["created_at"]),
                }
                for e in (ledger_resp.data or [])
            ],
        }

    return result


@router.post("/{user_id}/suspend")
def suspend_user(
    user_id: str,
    body: SuspendRequest,
    profile: dict = Depends(get_current_admin),
) -> dict:
    started = time.monotonic()
    if not body.reason or not body.reason.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_error",
                "message": "Suspension reason is required",
            },
        )

    sb = _supabase()
    p = (
        sb.table("profiles")
        .select("role, verification_status")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not p.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found"},
        )
    if p.data["role"] == "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "forbidden",
                "message": "Admin-role accounts cannot be suspended through this mechanism",
            },
        )
    if p.data["verification_status"] == "suspended":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "User is already suspended"},
        )

    (
        sb.table("profiles")
        .update({"verification_status": "suspended"})
        .eq("id", user_id)
        .execute()
    )
    # Revoke all refresh tokens immediately (two-layer revocation)
    auth_service.revoke_sessions(user_id)

    audit_id = audit_service.append_log(
        profile["id"], "suspended", user_id, reason=body.reason.strip()
    )

    logger.info(json.dumps({
        "event": "admin_user_action",
        "admin_id": str(profile["id"]),
        "action_type": "suspended",
        "target_user_id": str(user_id),
        "reason": body.reason.strip(),
        "duration_ms": round((time.monotonic() - started) * 1000, 1),
    }))

    return {"user_id": user_id, "new_status": "suspended", "audit_log_id": audit_id}


@router.post("/{user_id}/reinstate")
def reinstate_user(
    user_id: str,
    profile: dict = Depends(get_current_admin),
) -> dict:
    sb = _supabase()
    p = (
        sb.table("profiles")
        .select("verification_status")
        .eq("id", user_id)
        .single()
        .execute()
    )
    if not p.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found"},
        )
    if p.data["verification_status"] != "suspended":
        raise HTTPException(
            status_code=409,
            detail={"error": "conflict", "message": "User is not suspended"},
        )

    (
        sb.table("profiles")
        .update({"verification_status": "verified"})
        .eq("id", user_id)
        .execute()
    )
    audit_id = audit_service.append_log(profile["id"], "reinstated", user_id)
    return {"user_id": user_id, "new_status": "verified", "audit_log_id": audit_id}
