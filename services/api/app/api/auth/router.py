from fastapi import APIRouter, Depends, Request, status

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
from app.services import auth_service

router = APIRouter()


@router.post("/request-otp", response_model=OtpSentResponse)
def request_otp(body: OtpRequest) -> OtpSentResponse:
    result = auth_service.request_otp(body.email)
    return OtpSentResponse(**result)


@router.post("/verify-otp", response_model=SessionResponse)
def verify_otp(body: OtpVerifyRequest) -> SessionResponse:
    result = auth_service.verify_otp(body.email, body.otp)
    return result


@router.post("/sign-in-with-password", response_model=SessionResponse)
def sign_in_with_password(body: PasswordSignInRequest) -> SessionResponse:
    result = auth_service.sign_in_with_password(body.email, body.password)
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
