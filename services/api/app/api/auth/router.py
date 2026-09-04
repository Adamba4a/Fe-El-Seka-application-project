import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.dependencies.auth import get_current_user
from app.models.auth import (
    OtpRequest,
    OtpSentResponse,
    OtpVerifyRequest,
    PasswordSignInRequest,
    RefreshRequest,
    SessionResponse,
    SetPasswordRequest,
)
from app.services import auth_service, fraud_signal_service

router = APIRouter()


@router.post("/request-otp", response_model=OtpSentResponse)
def request_otp(body: OtpRequest) -> OtpSentResponse:
    result = auth_service.request_otp(body.email)
    return OtpSentResponse(**result)


@router.post("/verify-otp", response_model=SessionResponse)
def verify_otp(body: OtpVerifyRequest, request: Request, background_tasks: BackgroundTasks) -> SessionResponse:
    result = auth_service.verify_otp(body.email, body.otp)
    background_tasks.add_task(
        fraud_signal_service.record_signal,
        event_type="signup",
        user_id=uuid.UUID(result["user"]["id"]),
        device_id=request.headers.get("x-device-id"),
        ip_address=request.client.host if request.client else None,
    )
    return result


@router.post("/sign-in-with-password", response_model=SessionResponse)
def sign_in_with_password(
    body: PasswordSignInRequest, request: Request, background_tasks: BackgroundTasks
) -> SessionResponse:
    result = auth_service.sign_in_with_password(body.email, body.password)
    background_tasks.add_task(
        fraud_signal_service.record_signal,
        event_type="login",
        user_id=uuid.UUID(result["user"]["id"]),
        device_id=request.headers.get("x-device-id"),
        ip_address=request.client.host if request.client else None,
    )
    return result


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    body: SetPasswordRequest,
    profile: dict = Depends(get_current_user),
) -> None:
    auth_service.set_password(profile["id"], body.new_password)


@router.post("/refresh")
def refresh_token(body: RefreshRequest) -> dict:
    return auth_service.refresh_session(body.refresh_token)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(
    request: Request,
    profile: dict = Depends(get_current_user),
) -> None:
    auth_service.sign_out(profile["id"], request.state.token)
