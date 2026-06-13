from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: str = ""
    model_registry_bucket: str = "model-registry"
    ai_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
