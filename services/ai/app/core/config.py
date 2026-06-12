from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ai_version: str = "0.1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
