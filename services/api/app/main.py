import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin.car_maintenance_router import router as admin_car_maintenance_router
from app.api.admin.dashboard_router import router as admin_dashboard_router
from app.api.admin.financial_router import router as admin_financial_router
from app.api.admin.moderation_router import router as admin_moderation_router
from app.api.admin.rides_router import router as admin_rides_router
from app.api.admin.sponsored_groups_router import router as admin_sponsored_groups_router
from app.api.admin.users_router import router as admin_users_router
from app.api.admin.vehicle_updates_router import router as admin_vehicle_updates_router
from app.api.admin.verification_router import router as admin_verification_router
from app.api.admin.wallet_router import router as admin_wallet_router
from app.api.admin.wallet_topup_router import router as admin_wallet_topup_router
from app.api.admin.withdrawal_router import router as admin_withdrawal_router
from app.api.auth.router import router as auth_router
from app.api.bookings.router import router as bookings_router
from app.api.geocode.router import router as geocode_router
from app.api.groups.router import router as groups_router
from app.api.health import router as health_router
from app.api.internal.revocation_router import router as internal_router
from app.api.internal.route_intelligence_router import router as route_intelligence_router
from app.api.org_access.router import router as org_access_router
from app.api.profiles.router import router as profiles_router
from app.api.ratings.router import router as ratings_router
from app.api.reports.router import router as reports_router
from app.api.rides.recurring_router import router as recurring_rides_router
from app.api.rides.router import router as rides_router
from app.api.routes.router import router as routes_router
from app.api.search.router import router as search_router
from app.api.users.router import router as users_router
from app.api.vehicles.router import router as vehicles_router
from app.api.verification.router import router as verification_router
from app.api.wallet.router import router as wallet_router
from app.api.wallet_topup.router import router as wallet_topup_router
from app.api.wallet_withdrawals.router import router as wallet_withdrawals_router
from app.core.config import settings
from app.core.database import close_pool, create_pool
from app.services import ai_client as ai_client_module
from app.services.booking_service import booking_expiry_loop
from app.services.continuous_learning_config_service import (
    continuous_learning_config_refresh_loop,
    init_continuous_learning_config,
)
from app.services.driver_reminder_service import driver_reminder_loop
from app.services.fcm_service import initialize_fcm
from app.services.location_history_service import location_history_retention_loop
from app.services.model_lifecycle_service import init_rollout_cache, rollout_cache_refresh_loop
from app.services.model_monitoring_service import model_monitoring_loop
from app.services.moderation_service import init_moderation_config, moderation_config_refresh_loop
from app.services.notification_dispatcher import notification_dispatcher_loop
from app.services.notification_service import email_retry_loop
from app.services.pricing_service import init_pricing_config, pricing_config_refresh_loop
from app.services.ranking_config_service import init_ranking_config, ranking_config_refresh_loop
from app.services.recurring_ride_service import recurring_ride_generation_loop
from app.services.retraining_scheduler_service import retraining_scheduler_loop

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    pool = await create_pool(settings.database_url)
    app.state.pool = pool
    await init_pricing_config()
    await init_ranking_config()
    await init_moderation_config()
    await init_continuous_learning_config()
    await init_rollout_cache()
    try:
        await initialize_fcm()
    except Exception as exc:
        logging.getLogger(__name__).warning("FCM initialization skipped: %s", exc)
    app.state.ai_http_client = await ai_client_module.init(settings.ai_service_url)
    app.state.ai_verify_http_client = await ai_client_module.init_verify(settings.ai_service_url)
    email_task = asyncio.create_task(email_retry_loop())
    expiry_task = asyncio.create_task(booking_expiry_loop())
    pricing_task = asyncio.create_task(pricing_config_refresh_loop())
    ranking_task = asyncio.create_task(ranking_config_refresh_loop())
    moderation_task = asyncio.create_task(moderation_config_refresh_loop())
    continuous_learning_config_task = asyncio.create_task(continuous_learning_config_refresh_loop())
    rollout_cache_task = asyncio.create_task(rollout_cache_refresh_loop())
    dispatcher_task = asyncio.create_task(notification_dispatcher_loop())
    reminder_task = asyncio.create_task(driver_reminder_loop())
    retraining_scheduler_task = asyncio.create_task(retraining_scheduler_loop())
    model_monitoring_task = asyncio.create_task(model_monitoring_loop())
    recurring_generation_task = asyncio.create_task(recurring_ride_generation_loop())
    location_history_retention_task = asyncio.create_task(location_history_retention_loop())
    yield
    location_history_retention_task.cancel()
    recurring_generation_task.cancel()
    model_monitoring_task.cancel()
    retraining_scheduler_task.cancel()
    reminder_task.cancel()
    dispatcher_task.cancel()
    rollout_cache_task.cancel()
    continuous_learning_config_task.cancel()
    moderation_task.cancel()
    ranking_task.cancel()
    pricing_task.cancel()
    expiry_task.cancel()
    email_task.cancel()
    await ai_client_module.close()
    await ai_client_module.close_verify()
    app.state.ai_http_client = None
    app.state.ai_verify_http_client = None
    await close_pool()
    app.state.pool = None


app = FastAPI(
    title="Triplyy API",
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


@app.middleware("http")
async def maintenance_gate(request: Request, call_next):
    # /health stays reachable even during maintenance so Bunny's health
    # probe doesn't treat the container as unhealthy and restart it.
    if settings.maintenance_mode and request.url.path not in ("/health", "/api/health"):
        return JSONResponse(
            status_code=503,
            content={"error": "maintenance", "message": "Triplyy is temporarily offline for maintenance."},
            headers={"Retry-After": "3600"},
        )
    return await call_next(request)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    # A status-code handler intercepts every HTTPException(404, ...) before the
    # HTTPException handler below runs, so it must forward a dict detail (e.g.
    # {"error": "not_found", "message": "Ride not found"}) itself, or every
    # explicit 404 raise across the app would surface as this generic message
    # instead of the specific one the route set. Only genuinely-unrouted
    # requests (Starlette's own 404, whose detail is the plain string "Not
    # Found") fall through to the generic message.
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return JSONResponse(status_code=404, content=detail)
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": "Resource not found"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # FastAPI's default HTTPException handler wraps whatever `detail` a route
    # raised inside {"detail": ...}. Every raise site in this app passes a
    # dict detail (e.g. {"error": "duplicate_payment_reference", "message":
    # "..."}) expecting it to reach the client as-is — several frontend call
    # sites even have their own `.detail` unwrap workarounds for this. Flatten
    # it here instead so the wire shape matches what every raise site (and
    # the 404/validation handlers above/below) already produces, and callers
    # reading `err.error` / `err.message` directly get the real message
    # instead of always falling back to a generic one.
    detail = exc.detail
    content = detail if isinstance(detail, dict) else {"error": "http_error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


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
    admin_dashboard_router,
    prefix="/api/admin/dashboard",
    tags=["admin"],
)
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
    admin_rides_router,
    prefix="/api/admin/rides",
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
app.include_router(
    admin_wallet_topup_router,
    prefix="/api/admin/wallet-topup-requests",
    tags=["admin-wallet-topup"],
)
app.include_router(
    admin_withdrawal_router,
    prefix="/api/admin/withdrawal-requests",
    tags=["admin-withdrawal-requests"],
)
app.include_router(
    admin_sponsored_groups_router,
    prefix="/api/admin/sponsored-groups",
    tags=["admin-sponsored-groups"],
)
app.include_router(
    admin_car_maintenance_router,
    prefix="/api/admin/car-maintenance-rewards",
    tags=["admin-car-maintenance"],
)
app.include_router(
    admin_moderation_router,
    prefix="/api/admin/moderation",
    tags=["admin"],
)
app.include_router(
    admin_financial_router,
    prefix="/api/admin/financial",
    tags=["admin"],
)
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
# Must be registered before rides_router: GET /api/v1/rides/recurring would
# otherwise be shadowed by rides_router's GET /{ride_id} (Starlette matches
# routes in registration order, and "recurring" structurally matches that
# single-segment path parameter before FastAPI's UUID validation ever runs).
app.include_router(recurring_rides_router, prefix="/api/v1/rides/recurring", tags=["rides"])
app.include_router(rides_router, prefix="/api/v1/rides", tags=["rides"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(bookings_router, prefix="/api/v1/bookings", tags=["bookings"])
app.include_router(ratings_router, prefix="/api/v1/ratings", tags=["ratings"])
app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(wallet_router, prefix="/api/v1/drivers/me", tags=["wallet"])
app.include_router(wallet_topup_router, prefix="/api/wallet/topup", tags=["wallet-topup"])
app.include_router(wallet_withdrawals_router, prefix="/api/wallet/withdrawals", tags=["wallet-withdrawals"])
app.include_router(internal_router, prefix="/api/v1/internal", tags=["internal"])
app.include_router(routes_router, prefix="/api/routes", tags=["routes"])
app.include_router(geocode_router, prefix="/api/geocode", tags=["geocode"])
app.include_router(groups_router, prefix="/api/groups", tags=["groups"])
app.include_router(org_access_router, prefix="/api/v1/org-access", tags=["org-access"])
app.include_router(route_intelligence_router, prefix="/internal/route-intelligence", tags=["internal"])
