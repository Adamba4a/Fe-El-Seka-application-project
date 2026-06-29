import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from app.api.users.router import router as users_router
from app.api.admin.users_router import router as admin_users_router
from app.api.admin.vehicle_updates_router import router as admin_vehicle_updates_router
from app.api.admin.verification_router import router as admin_verification_router
from app.api.admin.wallet_router import router as admin_wallet_router
from app.api.auth.router import router as auth_router
from app.api.health import router as health_router
from app.api.internal.revocation_router import router as internal_router
from app.api.internal.route_intelligence_router import router as route_intelligence_router
from app.api.profiles.router import router as profiles_router
from app.api.routes.router import router as routes_router
from app.api.bookings.router import router as bookings_router
from app.api.rides.router import router as rides_router
from app.api.search.router import router as search_router
from app.api.vehicles.router import router as vehicles_router
from app.api.verification.router import router as verification_router
from app.core.config import settings
from app.core.database import close_pool, create_pool
from app.services.booking_service import booking_expiry_loop
from app.services.driver_reminder_service import driver_reminder_loop
from app.services.fcm_service import initialize_fcm
from app.services.notification_dispatcher import notification_dispatcher_loop
from app.services.notification_service import email_retry_loop
from app.services.pricing_service import init_pricing_config, pricing_config_refresh_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    pool = await create_pool(settings.database_url)
    app.state.pool = pool
    await init_pricing_config()
    try:
        await initialize_fcm()
    except Exception as exc:
        logging.getLogger(__name__).warning("FCM initialization skipped: %s", exc)
    email_task = asyncio.create_task(email_retry_loop())
    expiry_task = asyncio.create_task(booking_expiry_loop())
    pricing_task = asyncio.create_task(pricing_config_refresh_loop())
    dispatcher_task = asyncio.create_task(notification_dispatcher_loop())
    reminder_task = asyncio.create_task(driver_reminder_loop())
    yield
    reminder_task.cancel()
    dispatcher_task.cancel()
    pricing_task.cancel()
    expiry_task.cancel()
    email_task.cancel()
    await close_pool()
    app.state.pool = None


app = FastAPI(
    title="Fe El Seka API",
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": "Resource not found"},
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": str(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc, exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": str(exc)},
    )


app.include_router(health_router)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/api/profiles", tags=["profiles"])
app.include_router(
    verification_router,
    prefix="/api/verification",
    tags=["verification"],
)
app.include_router(vehicles_router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(
    admin_verification_router,
    prefix="/api/admin/verification",
    tags=["admin"],
)
app.include_router(
    admin_users_router,
    prefix="/api/admin/users",
    tags=["admin"],
)
app.include_router(
    admin_vehicle_updates_router,
    prefix="/api/admin/vehicle-updates",
    tags=["admin"],
)
app.include_router(
    admin_wallet_router,
    prefix="/api/admin/drivers",
    tags=["admin"],
)
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(rides_router, prefix="/api/v1/rides", tags=["rides"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(bookings_router, prefix="/api/v1/bookings", tags=["bookings"])
app.include_router(internal_router, prefix="/api/v1/internal", tags=["internal"])
app.include_router(routes_router, prefix="/api/routes", tags=["routes"])
app.include_router(route_intelligence_router, prefix="/internal/route-intelligence", tags=["internal"])
