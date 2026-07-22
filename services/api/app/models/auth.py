from pydantic import BaseModel, field_validator


class OtpRequest(BaseModel):
    email: str


class OtpVerifyRequest(BaseModel):
    email: str
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be a 6-digit number")
        return v


class PasswordSignInRequest(BaseModel):
    email: str
    password: str


class SetPasswordRequest(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class SessionUserResponse(BaseModel):
    id: str
    email: str
    is_new_user: bool


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: SessionUserResponse


class OtpSentResponse(BaseModel):
    message: str
    expires_in_seconds: int


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: object = None
