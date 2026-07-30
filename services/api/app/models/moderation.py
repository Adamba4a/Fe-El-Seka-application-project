from __future__ import annotations

from pydantic import BaseModel, Field


class ResolveReportRequest(BaseModel):
    action: str = Field(pattern="^(warn|suspend|dismiss)$")
    reason: str = Field(min_length=1)


class ReinstateUserRequest(BaseModel):
    reason: str = Field(min_length=1)
