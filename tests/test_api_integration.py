"""Integration proof that the API role can read marts but cannot mutate data."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import ProgrammingError

from gemeente_data_platform.api import create_app
from gemeente_data_platform.config import Settings

pytestmark = pytest.mark.integration


def _guard() -> None:
    target = (
        os.getenv("RUN_DB_INTEGRATION"),
        os.getenv("TEST_DATABASE_HOST", "localhost"),
        os.getenv("TEST_DATABASE_PORT", "5434"),
        os.getenv("TEST_DATABASE_NAME", "gemeente_data_test"),
    )
    if target[0] != "1":
        pytest.skip("Set RUN_DB_INTEGRATION=1 for integration tests.")
    if target[1:] != ("localhost", "5434", "gemeente_data_test"):
        raise RuntimeError("Safety guard rejected a non-isolated database target.")


@pytest.fixture()
def app_engine():
    _guard()
    migration_env = os.environ | {
        "DATABASE_PORT": "5434",
        "DATABASE_NAME": "gemeente_data_test",
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=migration_env,
    )
    password = Path(os.getenv("TEST_DATABASE_PASSWORD_FILE", "secrets/app_password.txt")).read_text().strip()
    engine = create_engine(URL.create("postgresql+psycopg", username="gemeente_app", password=password, host="localhost", port=5434, database="gemeente_data_test"))
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM core.fact_population"))
        connection.execute(text("DELETE FROM core.dim_municipality"))
        connection.execute(text("DELETE FROM core.dim_period"))
        connection.execute(text("INSERT INTO core.dim_municipality VALUES ('GM0484', 'Alphen aan den Rijn', 2020, 2026, true)"))
        connection.execute(text("INSERT INTO core.dim_period VALUES ('2025JJ00', 2025, '2025', true, true), ('2026JJ00', 2026, '2026', true, false)"))
        connection.execute(text("INSERT INTO core.fact_population VALUES ('GM0484', '2025JJ00', 100, 100), ('GM0484', '2026JJ00', 110, NULL)"))
    yield engine
    engine.dispose()


def _api_settings() -> Settings:
    return Settings(
        database_host="localhost",
        database_port=5434,
        database_name="gemeente_data_test",
        api_database_password_file=Path("secrets/api_password.txt"),
    )


def test_api_role_is_login_read_only_and_endpoints_use_marts(app_engine):
    with app_engine.connect() as connection:
        assert connection.execute(text("SELECT rolcanlogin FROM pg_roles WHERE rolname='gemeente_api'")).scalar_one()
    with TestClient(create_app(settings=_api_settings())) as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/api/v1/years").status_code == 200
        assert client.get("/api/v1/municipalities/GM0484/population").json()["observations"][-1]["average_population"] is None
        assert client.get("/api/v1/national/population").json()[-1]["average_population"] is None
        assert client.get("/api/v1/rankings/population", params={"year": 2026}).json()[0]["municipality_code"] == "GM0484"

    api_engine = create_engine(_api_settings().api_database_url())
    with api_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM mart.v_population_by_municipality_year")).scalar_one() == 2
        for statement in ("INSERT INTO core.dim_period VALUES ('2030JJ00', 2030, '2030', true, true)", "UPDATE core.dim_municipality SET municipality_name='x'", "DELETE FROM core.fact_population", "CREATE TABLE public.not_allowed (id integer)", "SELECT * FROM ops.etl_run"):
            with pytest.raises(ProgrammingError):
                connection.execute(text(statement))
            connection.rollback()
    api_engine.dispose()
