"""Configuratie die via omgevingsvariabelen wordt geladen."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Applicatie-instellingen voor lokale en toekomstige omgevingen."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str | None = None
    cbs_base_url: str = "https://opendata.cbs.nl/ODataApi/OData"
    cbs_dataset_code: str = "03759ned"
    cbs_request_timeout: float = 30.0
    cbs_max_retries: int = 2
    cbs_retry_backoff_seconds: float = 0.5
    cbs_max_pages: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
