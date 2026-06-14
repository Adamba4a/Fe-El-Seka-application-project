from fastapi import APIRouter, Depends, Request, status

from app.dependencies.auth import get_current_user
from app.models.auth import (
    OtpRequest,
    OtpSentResponse,
    OtpVerifyRequest,
    RefreshRequest,
    SessionResponse,
)
from app.services import auth_service

router = APIRouter()


@router.post("/request-otp", response_model=OtpSentResponse)
def request_otp(body: OtpRequest) -> OtpSentResponse:
    result = auth_service.request_otp(body.phone_number)
    return OtpSentResponse(**result)


@router.post("/verify-otp", response_model=SessionResponse)
def verify_otp(body: OtpVerifyRequest) -> SessionResponse:
    result = auth_service.verify_otp(body.phone_number, body.otp)
    return result


@router.post("/refresh")
def refresh_token(body: RefreshRequest) -> dict:
    return auth_service.refresh_session(body.refresh_token)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(
    request: Request,
    profile: dict = Depends(get_current_user),
) -> None:
    auth_service.sign_out(profile["id"], request.state.token)
