from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class DeviceTokenRequest(BaseModel):
    token: str
    platform: Literal["web", "android", "ios"]


class DeviceTokenResponse(BaseModel):
    token_id: UUID
    user_id: UUID
    platform: str
    last_seen_at: datetime
