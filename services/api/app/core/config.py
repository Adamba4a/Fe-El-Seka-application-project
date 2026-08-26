from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_service_role_key: str
    api_version: str = "0.1.0"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        # Allows CORS_ORIGINS=https://a.com,https://b.com in .env.prod instead
        # of requiring JSON-array syntax.
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    # Used to build user-facing links (e.g. group invite links) from the API,
    # which has no other notion of the frontend's own origin.
    frontend_base_url: str = "http://localhost:3000"
    resend_api_key: str = ""
    webhook_secret: str = ""
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 54325
    osrm_url: str = "http://osrm:5000"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    # Nominatim's usage policy requires a way to identify the calling
    # application (User-Agent) — requests without one are liable to be
    # throttled or dropped, which is what caused the reverse-geocode calls
    # from mobile clients to time out and fall back to raw coordinates.
    nominatim_user_agent: str = "TriplyyApp/1.0 (+https://triplyy.net)"
    internal_secret: str = ""
    firebase_service_account_secret_name: str = "firebase_service_account"
    ai_service_url: str = "http://localhost:8001"

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
