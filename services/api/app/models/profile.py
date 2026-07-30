from typing import Literal

from pydantic import BaseModel, field_validator


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

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not 2 <= len(v) <= 50:
            raise ValueError("Display name must be 2–50 characters")
        return v


class ProfileResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    profile_photo_url: str | None
    verification_status: str
    is_submission_locked: bool
    rating_avg: float | None = None
    rating_count: int = 0
    created_at: str


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
