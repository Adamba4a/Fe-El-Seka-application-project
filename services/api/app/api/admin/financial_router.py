from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.database import get_pool
from app.dependencies.roles import get_current_admin
from app.services import financial_report_service

router = APIRouter()


def _parse_range(start: str | None, end: str | None) -> tuple[date, date]:
    if not start or not end:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "start and end are required"},
        )
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "start/end must be YYYY-MM-DD dates"},
        )
    if end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "message": "end must not be before start"},
        )
    return start_date, end_date


@router.get("/report")
async def get_report(
    start: str | None = None,
    end: str | None = None,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    start_date, end_date = _parse_range(start, end)
    pool = get_pool()
    async with pool.acquire() as conn:
        return await financial_report_service.get_report(conn, start_date, end_date)


@router.get("/report/export")
async def export_report(
    start: str | None = None,
    end: str | None = None,
    _admin: dict = Depends(get_current_admin),
) -> StreamingResponse:
    start_date, end_date = _parse_range(start, end)
    pool = get_pool()
    conn = await pool.acquire()

    async def _generate():
        try:
            async for line in financial_report_service.stream_report_csv(conn, start_date, end_date):
                yield line
        finally:
            await pool.release(conn)

    filename = f"financial_report_{start_date.isoformat()}_{end_date.isoformat()}.csv"
    return StreamingResponse(
        _generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/drivers/balances")
async def get_driver_balances(_admin: dict = Depends(get_current_admin)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await financial_report_service.get_driver_balances(conn)
