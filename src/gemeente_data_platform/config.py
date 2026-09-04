"""Configuratie die via omgevingsvariabelen wordt geladen."""

from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Applicatie-instellingen voor lokale en toekomstige omgevingen."""

    app_env: str = "development"
    log_level: str = "INFO"
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "gemeente_data"
    database_user: str = "gemeente_app"
    database_password_file: Path = Path("secrets/app_password.txt")
    database_password: SecretStr | None = None
    database_connect_timeout: int = 10
    database_application_name: str = "gemeente-data-platform"
    database_sslmode: str = "disable"
    api_database_user: str = "gemeente_api"
    api_database_password_file: Path = Path("secrets/api_password.txt")
    api_title: str = "Gemeente Data Platform API"
    api_version: str = "0.1.0"
    api_allowed_origins: str = ""
    pipeline_root: Path = Path("data/runs")
    pipeline_runtime_root: Path = Path("data/runtime")
    pipeline_lock_timeout_seconds: float = 5.0
    cbs_base_url: str = "https://opendata.cbs.nl/ODataApi/OData"
    cbs_dataset_code: str = "03759ned"
    cbs_request_timeout: float = 30.0
    cbs_max_retries: int = 2
    cbs_retry_backoff_seconds: float = 0.5
    cbs_max_pages: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def database_url(self) -> URL:
        """Maak een SQLAlchemy-URL zonder wachtwoord in logs samen te stellen."""
        password = (
            self.database_password.get_secret_value()
            if self.database_password
            else None
        )
        if password is None:
            path = self.database_password_file
            path = path if path.is_absolute() else PROJECT_ROOT / path
            password = path.read_text(encoding="utf-8").strip()
        if not password:
            raise ValueError("Database password is unavailable.")
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={
                "connect_timeout": str(self.database_connect_timeout),
                "application_name": self.database_application_name,
                "sslmode": self.database_sslmode,
            },
        )

    def api_database_url(self) -> URL:
        """Maak de URL voor de afzonderlijke read-only API-rol."""
        path = self.api_database_password_file
        path = path if path.is_absolute() else PROJECT_ROOT / path
        password = path.read_text(encoding="utf-8").strip()
        if not password:
            raise ValueError("API database password is unavailable.")
        return URL.create(
            "postgresql+psycopg",
            username=self.api_database_user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={
                "connect_timeout": str(self.database_connect_timeout),
                "application_name": "gemeente-data-platform-api",
                "sslmode": self.database_sslmode,
            },
        )


settings = Settings()
