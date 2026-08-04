from pydantic import BaseModel


class ReloadRequest(BaseModel):
    model_type: str | None = None  # None means reload all


class ReloadResponse(BaseModel):
    reloaded: list[str]
    skipped: list[str]
    errors: dict[str, str]


class ShadowRequest(BaseModel):
    model_type: str
    storage_version: str


class ShadowResponse(BaseModel):
    status: str
    storage_version: str


class PromoteRequest(BaseModel):
    model_type: str
    storage_version: str


class PromoteResponse(BaseModel):
    status: str
    storage_version: str


class DiscardCandidateRequest(BaseModel):
    model_type: str


class DiscardCandidateResponse(BaseModel):
    status: str
