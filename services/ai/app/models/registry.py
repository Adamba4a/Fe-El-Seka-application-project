from pydantic import BaseModel


class ReloadRequest(BaseModel):
    model_type: str | None = None  # None means reload all


class ReloadResponse(BaseModel):
    reloaded: list[str]
    skipped: list[str]
    errors: dict[str, str]
