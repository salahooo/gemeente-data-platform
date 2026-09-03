"""Configuratie die via omgevingsvariabelen wordt geladen."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Applicatie-instellingen voor lokale en toekomstige omgevingen."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
