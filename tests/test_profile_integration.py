"""Guarded profile load/grant proof on the existing isolated test database only."""

import json
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from gemeente_data_platform.api_repository import MartRepository
from gemeente_data_platform.profile_pipeline import digest, load_profile
from tests.test_api_integration import _api_settings
from tests.test_database_integration import _url
from tests.test_profile import profile_run

pytestmark = pytest.mark.integration


def test_profile_transaction_idempotence_and_least_privilege(tmp_path):
    url = _url()  # Hard guard: only localhost:5434/gemeente_data_test.
    env = os.environ | {
        "DATABASE_HOST": "localhost",
        "DATABASE_PORT": "5434",
        "DATABASE_NAME": "gemeente_data_test",
    }
    env["DATABASE_URL"] = ""
    env["APP_ENV"] = "development"
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env
    )
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.begin() as c:
            c.execute(
                text(
                    "INSERT INTO core.dim_period VALUES "
                    "('2026JJ00',2026,'2026',true,false) ON CONFLICT DO NOTHING"
                )
            )
            c.execute(
                text(
                    "INSERT INTO core.dim_municipality VALUES "
                    "(:code,'Test',2026,2026,true) ON CONFLICT DO NOTHING"
                ),
                [{"code": f"GM{i:04}"} for i in range(8000, 8250)],
            )
            c.execute(
                text(
                    "INSERT INTO core.fact_population VALUES "
                    "(:code,'2026JJ00',60,NULL) ON CONFLICT DO NOTHING"
                ),
                [{"code": f"GM{i:04}"} for i in range(8000, 8250)],
            )
        directory = profile_run(tmp_path)
        assert load_profile(engine, directory) == "success"
        assert load_profile(engine, directory) == "skipped"
        api_engine = create_engine(_api_settings().api_database_url())
        try:
            repo = MartRepository(api_engine)
            assert len(repo.age_profile("GM8000", 2026)) == 5
            assert repo.data_quality()[1]["record_count"] == 1250
            with api_engine.connect() as c:
                assert not c.execute(
                    text(
                        "SELECT has_table_privilege(current_user,"
                        "'mart.v_municipality_age_profile','INSERT,UPDATE,DELETE')"
                    )
                ).scalar_one()
                for sql in (
                    "SELECT * FROM core.fact_age_profile",
                    "SELECT * FROM ops.age_snapshot",
                    "DELETE FROM mart.v_municipality_age_profile",
                ):
                    with pytest.raises(DBAPIError):
                        c.execute(text(sql))
                    c.rollback()
        finally:
            api_engine.dispose()
        path = directory / "profile.json"
        data = json.loads(path.read_text())
        for row in data["rows"]:
            if row["region_code"] == "GM8000":
                row["region_code"] = row["municipality_code"] = "GM9999"
        data["checksum"] = digest(data["rows"])
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="references"):
            load_profile(engine, directory)
        assert len(MartRepository(engine).age_profile("GM8000", 2026)) == 5
    finally:
        with engine.begin() as c:
            c.execute(text("DELETE FROM core.fact_age_profile WHERE year=2026"))
            c.execute(text("DELETE FROM ops.age_snapshot WHERE year=2026"))
            c.execute(
                text(
                    "DELETE FROM core.fact_population WHERE "
                    "municipality_code BETWEEN 'GM8000' AND 'GM8249'"
                )
            )
            c.execute(
                text(
                    "DELETE FROM core.dim_municipality WHERE "
                    "municipality_code BETWEEN 'GM8000' AND 'GM8249'"
                )
            )
        engine.dispose()
