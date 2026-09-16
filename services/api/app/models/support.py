from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

SupportStatus = Literal["open", "in_progress", "resolved"]


class SupportRequest(BaseModel):
    id: UUID
    email: str = Field(min_length=3, max_length=254)
    description: str = Field(min_length=10, max_length=5000)
    locale: Literal["en", "ar"] = "en"
    website: str = Field(default="", max_length=200)

    @field_validator("email", "description", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        # Bounded, conservative contact-address validation; no DNS/network lookup.
        import re

        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
            r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",
            value,
        ):
            raise ValueError("Invalid email address")
        local = value.split("@")[0]
        if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
            raise ValueError("Invalid email address")
        return value.lower()


class SupportStatusUpdate(BaseModel):
    status: SupportStatus
