"""Safe local and cloud configuration for the platform."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}
SSL_MODES = {"require", "verify-ca", "verify-full"}


class Settings(BaseSettings):
    """Configuration with fail-fast rules for a public deployment.

    ``DATABASE_URL`` is a runtime secret. Local Compose retains file-backed
    passwords, so no credential has to be placed in a cloud build.
    """

    app_env: str = "development"
    log_level: str = "INFO"
    port: int = Field(default=8000, validation_alias="PORT")
    database_url_override: SecretStr | None = Field(
        default=None, validation_alias="DATABASE_URL", repr=False
    )
    bootstrap_app_password: SecretStr | None = Field(
        default=None, validation_alias="BOOTSTRAP_APP_PASSWORD", repr=False
    )
    bootstrap_api_password: SecretStr | None = Field(
        default=None, validation_alias="BOOTSTRAP_API_PASSWORD", repr=False
    )
    database_host: str = "localhost"
    database_port: int = 5433
    database_name: str = "gemeente_data"
    database_user: str = "gemeente_app"
    database_password_file: Path = Path("secrets/app_password.txt")
    database_password: SecretStr | None = None
    database_connect_timeout: int = 10
    database_pool_size: int = 5
    database_max_overflow: int = 2
    database_pool_timeout: int = 10
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

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    @field_validator("app_env")
    @classmethod
    def normalise_environment(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_public_deployment(self) -> "Settings":
        if self.port < 1 or self.port > 65535:
            raise ValueError("PORT must be between 1 and 65535.")
        if self.app_env != "production":
            return self
        raw_url = self._override_value()
        if not raw_url:
            raise ValueError("Production requires DATABASE_URL.")
        parsed = make_url(raw_url)
        if parsed.host and parsed.host.lower() in LOCAL_DATABASE_HOSTS:
            raise ValueError("Production DATABASE_URL must not target localhost.")
        if not parsed.username or not parsed.password:
            raise ValueError("Production DATABASE_URL requires database credentials.")
        if parsed.query.get("sslmode", "").lower() not in SSL_MODES:
            raise ValueError("Production DATABASE_URL requires PostgreSQL SSL.")
        origins = self.allowed_origins()
        if not origins or "*" in origins:
            raise ValueError("Production requires explicit non-wildcard CORS origins.")
        if any(not origin.startswith("https://") for origin in origins):
            raise ValueError("Production CORS origins must use HTTPS.")
        return self

    def _override_value(self) -> str | None:
        return (
            self.database_url_override.get_secret_value()
            if self.database_url_override is not None
            else None
        )

    def allowed_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.api_allowed_origins.split(",")
            if origin.strip()
        ]

    def database_url(self) -> URL:
        """Return a URL without formatting its password for logging."""
        override = self._override_value()
        if override:
            return make_url(override)
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
        """Use cloud DATABASE_URL or the local least-privilege API role."""
        if self._override_value():
            return self.database_url()
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
