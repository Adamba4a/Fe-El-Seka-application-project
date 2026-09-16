from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.dependencies.roles import get_current_admin
from app.models.support import SupportRequest, SupportStatus, SupportStatusUpdate
from app.services import support_service

router = APIRouter()
admin_router = APIRouter()


@router.post("", status_code=201)
async def submit(body: SupportRequest, request: Request):
    # Uvicorn controls trusted proxy handling; never parse forwarded headers here.
    return await support_service.submit_report(body, request.client.host if request.client else "unknown")


@admin_router.get("")
async def list_reports(
    status: SupportStatus | None = None,
    page: int = Query(1, ge=1, le=100000),
    admin: dict = Depends(get_current_admin),
):
    return await support_service.list_reports(status, page)


@admin_router.patch("/{report_id}")
async def update_status(report_id: UUID, body: SupportStatusUpdate, admin: dict = Depends(get_current_admin)):
    return await support_service.update_status(report_id, body.status, UUID(str(admin["id"])))
