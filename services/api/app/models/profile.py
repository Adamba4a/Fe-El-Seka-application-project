import re
from typing import Literal

from pydantic import BaseModel, field_validator

_PHONE_RE = re.compile(r"^\+2\d{11}$")


class ProfileSetup(BaseModel):
    role: Literal["passenger", "driver"]
    display_name: str

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not 2 <= len(v) <= 50:
            raise ValueError("Display name must be 2–50 characters")
        return v


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    language_preference: Literal["en", "ar"] | None = None
    phone_number: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not 2 <= len(v) <= 50:
            raise ValueError("Display name must be 2–50 characters")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _PHONE_RE.match(v):
            raise ValueError("Phone number must be an Egyptian number in the format +2 followed by 11 digits, e.g. +201234567890")
        return v


class ProfileResponse(BaseModel):
    id: str
    email: str
    phone_number: str | None
    display_name: str
    role: str
    profile_photo_url: str | None
    verification_status: str
    is_submission_locked: bool
    rating_avg: float | None = None
    rating_count: int = 0
    created_at: str
    language_preference: str | None = None


class PublicRideSummary(BaseModel):
    origin_address: str | None = None
    destination_address: str | None = None
    departure_datetime: str | None = None


class PublicProfileResponse(BaseModel):
    id: str
    display_name: str
    role: str
    profile_photo_url: str | None
    verification_status: str
    rating_avg: float | None = None
    rating_count: int = 0
    total_rides: int = 0
    recent_rides: list[PublicRideSummary] = []
    phone_number: str | None = None
