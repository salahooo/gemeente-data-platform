"""Database-free production deployment configuration tests."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from gemeente_data_platform.config import PSYCOPG3_DRIVER, Settings
from gemeente_data_platform.deploy_database import (
    _create_roles,
    processed_run_directory,
)
from gemeente_data_platform.deploy_database import main as deploy_database_main
from gemeente_data_platform.pipeline_security import redact


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "port": 10_000,
        "database_url_override": "postgresql+psycopg://cloud_user:opaque-password@db.example.test:5432/gemeente?sslmode=require",
        "api_allowed_origins": "https://dashboard.example.test",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_accepts_port_https_origin_and_ssl_database_url():
    settings = production_settings()
    assert settings.port == 10_000
    assert settings.database_url().host == "db.example.test"
    assert settings.allowed_origins() == ["https://dashboard.example.test"]


def test_cloud_postgresql_url_uses_psycopg3_without_exposing_credentials():
    settings = production_settings(
        database_url_override=(
            "postgresql://cloud_user:opaque-password@db.example.test/gemeente?sslmode=require"
        )
    )
    url = settings.database_url()
    assert url.drivername == PSYCOPG3_DRIVER
    assert "opaque-password" not in str(url)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "database_url_override",
            "postgresql://u:p@localhost/db?sslmode=require",
            "localhost",
        ),
        ("database_url_override", "postgresql://u:p@db.example.test/db", "SSL"),
        ("api_allowed_origins", "*", "non-wildcard"),
        ("api_allowed_origins", "http://dashboard.example.test", "HTTPS"),
    ],
)
def test_production_rejects_unsafe_cloud_settings(field, value, message):
    with pytest.raises(ValidationError, match=message):
        production_settings(**{field: value})


def test_redaction_hides_database_credentials():
    assert "opaque-password" not in redact("postgresql://cloud_user:opaque-password@db.example.test/db")


def test_render_blueprint_is_static_safe_and_has_no_database_service():
    blueprint = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    services = blueprint["services"]
    assert len(services) == 2
    assert blueprint["previews"]["generation"] == "off"
    assert all(service["branch"] == "main" for service in services)
    assert all("postgres" not in service["name"] for service in services)
    api = next(service for service in services if service["runtime"] == "docker")
    site = next(service for service in services if service["runtime"] == "static")
    assert api["plan"] == "free"
    assert "plan" not in site
    assert api["healthCheckPath"] == "/health"
    assert site["routes"] == [
        {"type": "rewrite", "source": "/*", "destination": "/index.html"}
    ]
    protected = {"DATABASE_URL", "API_ALLOWED_ORIGINS", "VITE_API_BASE_URL"}
    assert all(
        item.get("sync") is False
        for service in services
        for item in service.get("envVars", [])
        if item["key"] in protected
    )


def test_database_bootstrap_dry_run_never_connects(monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://cloud_user:opaque-password@db.example.test/gemeente?sslmode=require",
    )
    monkeypatch.setenv("API_ALLOWED_ORIGINS", "https://dashboard.example.test")
    deploy_database_main(["--processed-run", "known-run", "--dry-run"])
    assert "Dry run" in capsys.readouterr().out


def test_processed_run_directory_uses_canonical_cbs_root():
    directory = processed_run_directory("03759ned", "run-20260905")
    assert directory.parts[-4:] == ("processed", "cbs", "03759ned", "run-20260905")


@pytest.mark.parametrize("value", ["../outside", "..\\outside", "/tmp/outside", "."])
def test_processed_run_directory_rejects_path_traversal(value):
    with pytest.raises(ValueError, match="path component"):
        processed_run_directory("03759ned", value)


class _RoleSqlCaptureConnection:
    def __init__(self):
        self.calls = []

    def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters))
        if "rolcreaterole" in str(statement):
            return _ScalarResult(True)
        if parameters and "grant" in parameters:
            return _ScalarResult("SELECT 1")
        if "SELECT format(" in str(statement):
            return _ScalarResult(None)
        return _ScalarResult(None)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


def test_role_creation_sql_binds_password_as_text_for_psycopg3():
    connection = _RoleSqlCaptureConnection()
    settings = production_settings(
        bootstrap_app_password="synthetic-app-password",
        bootstrap_api_password="synthetic-api-password",
    )
    _create_roles(connection, settings)
    role_queries = [
        statement
        for statement, _ in connection.calls
        if "PASSWORD %L" in str(statement)
    ]
    assert len(role_queries) == 2
    assert all(
        "CAST(:password AS text)" in str(statement) for statement in role_queries
    )
    assert all(
        statement._bindparams["password"].type.python_type is str
        for statement in role_queries
    )
