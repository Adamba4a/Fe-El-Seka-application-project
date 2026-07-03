from pydantic import BaseModel


class ModelVersions(BaseModel):
    match_score: str | None = None
    ride_ranker: str | None = None
    price_recommender: str | None = None


class HealthResponse(BaseModel):
    status: str  # "ok" | "degraded" | "unavailable"
    ai_version: str
    models: ModelVersions
