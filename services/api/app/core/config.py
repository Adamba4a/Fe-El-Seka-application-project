from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_service_role_key: str
    supabase_jwt_secret: str = ""
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
    resend_api_key: str = ""
    webhook_secret: str = ""
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 54325
    osrm_url: str = "http://osrm:5000"
    internal_secret: str = ""
    firebase_service_account_secret_name: str = "firebase_service_account"
    ai_service_url: str = "http://localhost:8001"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
