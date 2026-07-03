import re
from datetime import datetime

from pydantic import BaseModel, field_validator

# Accept Arabic Unicode block + Latin letters
_PLATE_RE = re.compile(
    r"^[؀-ۿa-zA-Z]{1,3}\s?\d{1,4}$"
    r"|^\d{1,4}\s?[؀-ۿa-zA-Z]{1,3}$"
    r"|^\d{1,5}$"
)
_CURRENT_YEAR = datetime.now().year


class VehicleRegister(BaseModel):
    plate_number: str
    make: str
    model: str
    year: int
    color: str
    seat_count: int

    @field_validator("plate_number")
    @classmethod
    def validate_plate(cls, v: str) -> str:
        if not _PLATE_RE.match(v.strip()):
            raise ValueError("Invalid plate number format")
        return v.strip().upper()

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if not 2000 <= v <= _CURRENT_YEAR + 1:
            raise ValueError(f"Year must be between 2000 and {_CURRENT_YEAR}")
        return v

    @field_validator("seat_count")
    @classmethod
    def validate_seat_count(cls, v: int) -> int:
        if not 2 <= v <= 7:
            raise ValueError("Seat count must be between 2 and 7")
        return v


class VehicleUpdate(BaseModel):
    color: str | None = None
    seat_count: int | None = None

    @field_validator("seat_count")
    @classmethod
    def validate_seat_count(cls, v: int | None) -> int | None:
        if v is not None and not 2 <= v <= 7:
            raise ValueError("Seat count must be between 2 and 7")
        return v


class VehicleUpdateRequest(BaseModel):
    plate_number: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None

    @field_validator("plate_number")
    @classmethod
    def validate_plate(cls, v: str | None) -> str | None:
        if v is not None and not _PLATE_RE.match(v.strip()):
            raise ValueError("Invalid plate number format")
        return v.strip().upper() if v else v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int | None) -> int | None:
        if v is not None and not 2000 <= v <= _CURRENT_YEAR + 1:
            raise ValueError(f"Year must be between 2000 and {_CURRENT_YEAR}")
        return v


class VehicleResponse(BaseModel):
    id: str
    plate_number: str
    make: str
    model: str
    year: int
    color: str
    seat_count: int
    registered_at: str


class VehicleUpdateRequestResponse(BaseModel):
    id: str
    plate_number: str | None
    make: str | None
    model: str | None
    year: int | None
    status: str
    submitted_at: str
    rejection_reason: str | None
