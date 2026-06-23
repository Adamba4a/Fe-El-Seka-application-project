from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    supabase_url: str
    supabase_anon_key: str = ""
    supabase_service_role_key: str
    supabase_jwt_secret: str = ""
    api_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]
    resend_api_key: str = ""
    webhook_secret: str = ""
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 54325
    osrm_url: str = "http://osrm:5000"
    internal_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
