"""Veilige integratietests voor uitsluitend gemeente_data_test:5434."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from gemeente_data_platform.config import Settings
from gemeente_data_platform.database_loader import ProcessedRun, load_snapshot
from gemeente_data_platform.database_validator import validate_database_snapshot
from gemeente_data_platform.deploy_database import preflight_database
from gemeente_data_platform.raw_storage import sha256_file

pytestmark = pytest.mark.integration


def _url() -> URL:
    if os.getenv("RUN_DB_INTEGRATION") != "1":
        pytest.skip("Set RUN_DB_INTEGRATION=1 for integration tests.")
    if (
        os.getenv("TEST_DATABASE_HOST", "localhost"),
        os.getenv("TEST_DATABASE_PORT", "5434"),
        os.getenv("TEST_DATABASE_NAME", "gemeente_data_test"),
    ) != ("localhost", "5434", "gemeente_data_test"):
        raise RuntimeError("Safety guard rejected a non-isolated database target.")
    password = (
        Path(os.getenv("TEST_DATABASE_PASSWORD_FILE", "secrets/app_password.txt"))
        .read_text()
        .strip()
    )
    return URL.create(
        "postgresql+psycopg",
        username="gemeente_app",
        password=password,
        host="localhost",
        port=5434,
        database="gemeente_data_test",
    )


@pytest.fixture(scope="module")
def engine():
    _url()
    env = os.environ | {"DATABASE_PORT": "5434", "DATABASE_NAME": "gemeente_data_test"}
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"], check=False, env=env
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env
    )
    result = create_engine(_url())
    yield result
    result.dispose()


@pytest.fixture(autouse=True)
def clean_database(engine):
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM core.fact_population"))
        connection.execute(text("DELETE FROM core.dim_municipality"))
        connection.execute(text("DELETE FROM core.dim_period"))
        connection.execute(text("DELETE FROM ops.etl_run"))


def _seed(connection):
    connection.execute(
        text(
            "INSERT INTO core.dim_municipality VALUES ('GM9001', 'Een', 2025, 2026, true)"
        )
    )
    connection.execute(
        text(
            "INSERT INTO core.dim_period VALUES ('2025JJ00', 2025, '2025', true, true)"
        )
    )


def test_migration_lifecycle_objects_and_revision(engine):
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one()
            == "20260905_01"
        )
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('core', 'ops')"
                )
            ).scalar_one()
            == 4
        )
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM information_schema.views WHERE table_schema = 'mart'"
                )
            ).scalar_one()
            == 5
        )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO core.dim_municipality VALUES ('BAD', 'X', 2025, 2025, false)",
        "INSERT INTO core.dim_municipality VALUES ('GM9002', '', 2025, 2025, false)",
        "INSERT INTO core.dim_municipality VALUES ('GM9002', 'X', 2026, 2025, false)",
        "INSERT INTO core.dim_period VALUES ('BAD', 2025, 'X', true, true)",
    ],
)
def test_dimension_constraints_reject_invalid_values(engine, statement):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            c.execute(text(statement))


def test_fact_constraints_foreign_keys_and_null_average(engine):
    with engine.begin() as c:
        _seed(c)
        c.execute(
            text(
                "INSERT INTO core.fact_population VALUES ('GM9001', '2025JJ00', 10, NULL)"
            )
        )
    for statement in [
        "INSERT INTO core.fact_population VALUES ('GM9001', '2025JJ00', 10, 1)",
        "INSERT INTO core.fact_population VALUES ('GM9001', '2025JJ00', -1, 1)",
        "INSERT INTO core.fact_population VALUES ('GM9001', '2025JJ00', 1, -1)",
        "INSERT INTO core.fact_population VALUES ('GM9999', '2025JJ00', 1, 1)",
        "INSERT INTO core.fact_population VALUES ('GM9001', '2026JJ00', 1, 1)",
    ]:
        with pytest.raises(IntegrityError):
            with engine.begin() as c:
                c.execute(text(statement))


def _run(tmp_path: Path, run_id: str, population: int = 11) -> ProcessedRun:
    tmp_path.mkdir(parents=True, exist_ok=True)
    frames = {
        "dim_municipality": pd.DataFrame(
            [["GM9001", "Een", 2025, 2026, True]],
            columns=[
                "municipality_code",
                "municipality_name",
                "first_observed_year",
                "last_observed_year",
                "is_active_latest_period",
            ],
        ),
        "dim_period": pd.DataFrame(
            [
                ["2025JJ00", 2025, "2025", True, True],
                ["2026JJ00", 2026, "2026", True, False],
            ],
            columns=[
                "period_code",
                "year",
                "period_label",
                "has_january_population",
                "has_average_population",
            ],
        ),
        "fact_population": pd.DataFrame(
            [
                ["GM9001", "2025JJ00", 10, 10.0],
                ["GM9001", "2026JJ00", population, None],
            ],
            columns=[
                "municipality_code",
                "period_code",
                "population_january_1",
                "average_population",
            ],
        ),
    }
    for name, frame in frames.items():
        frame.to_parquet(tmp_path / f"{name}.parquet", index=False)
    quality = {
        "statistics_by_year": {
            "2025": {
                "active_municipality_count": 1,
                "january_population_sum": 10,
                "missing_average_population_count": 0,
            },
            "2026": {
                "active_municipality_count": 1,
                "january_population_sum": population,
                "missing_average_population_count": 1,
            },
        },
        "warnings": [],
    }
    (tmp_path / "quality_report.json").write_text(json.dumps(quality))
    checksums = {p.name: sha256_file(p) for p in tmp_path.iterdir()}
    manifest = {
        "processed_run_id": run_id,
        "raw_run_id": "raw-test",
        "raw_manifest_checksum": "a" * 64,
        "transformation_version": "test",
        "tables": {name: {"rows": len(frame)} for name, frame in frames.items()},
        "checksums_sha256": checksums,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return ProcessedRun(tmp_path, manifest, quality)


def test_loader_dry_run_load_idempotency_and_views(engine, tmp_path):
    run = _run(tmp_path, "run-one")
    assert load_snapshot(engine, run, dry_run=True) == "dry-run"
    assert load_snapshot(engine, run) == "success"
    assert load_snapshot(engine, run) == "skipped"
    with engine.connect() as c:
        assert (
            c.execute(text("SELECT count(*) FROM core.fact_population")).scalar_one()
            == 2
        )
        assert c.execute(
            text(
                "SELECT municipality_count, population_january_1_sum, average_population_sum FROM mart.v_national_population_by_year WHERE year=2025"
            )
        ).one() == (1, 10, 10)
        assert c.execute(
            text(
                "SELECT average_population_sum IS NULL, missing_average_population_count FROM mart.v_national_population_by_year WHERE year=2026"
            )
        ).one() == (True, 1)
        assert c.execute(
            text(
                "SELECT previous_population_january_1, population_change_absolute, population_change_percent, same_municipality_code_only FROM mart.v_municipality_year_over_year WHERE year=2026"
            )
        ).one() == (10, 1, 10.0, True)
        assert (
            c.execute(
                text(
                    "SELECT pipeline_run_id FROM ops.etl_run WHERE processed_run_id='run-one'"
                )
            ).scalar_one()
            is None
        )
    assert (
        validate_database_snapshot(engine, run)["table_counts"]["fact_population"] == 2
    )


def test_loader_records_pipeline_lineage(engine, tmp_path):
    run = _run(tmp_path, "lineage")
    assert load_snapshot(engine, run, pipeline_run_id="pipeline-20260904") == "success"
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT pipeline_run_id FROM ops.etl_run WHERE processed_run_id='lineage'"
                )
            ).scalar_one()
            == "pipeline-20260904"
        )
        assert c.execute(
            text("SELECT processed_run_id, pipeline_run_id FROM mart.v_dataset_lineage")
        ).one() == ("lineage", "pipeline-20260904")


def test_loader_new_snapshot_replaces_previous_snapshot(engine, tmp_path):
    assert load_snapshot(engine, _run(tmp_path / "one", "run-one", 11)) == "success"
    assert load_snapshot(engine, _run(tmp_path / "two", "run-two", 15)) == "success"
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT population_january_1 FROM core.fact_population WHERE period_code='2026JJ00'"
                )
            ).scalar_one()
            == 15
        )


def test_privileges_are_least_privilege(engine):
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT rolcanlogin FROM pg_roles WHERE rolname='gemeente_reader'")
            ).scalar_one()
            is False
        )
        assert c.execute(
            text("SELECT has_schema_privilege('gemeente_reader', 'mart', 'USAGE')")
        ).scalar_one()
        assert not c.execute(
            text(
                "SELECT has_table_privilege('gemeente_reader', 'core.fact_population', 'INSERT')"
            )
        ).scalar_one()
        assert not c.execute(
            text(
                "SELECT has_table_privilege('gemeente_reader', 'ops.etl_run', 'SELECT')"
            )
        ).scalar_one()
        assert not c.execute(
            text(
                "SELECT has_database_privilege('gemeente_reader', current_database(), 'CREATE')"
            )
        ).scalar_one()
        assert c.execute(
            text(
                "SELECT has_table_privilege('gemeente_reader', 'mart.v_national_population_by_year', 'SELECT')"
            )
        ).scalar_one()
        assert (
            c.execute(
                text(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication FROM pg_roles WHERE rolname='gemeente_app'"
                )
            ).scalar_one()
            is False
        )


def test_cloud_preflight_is_idempotent_when_local_prerequisites_exist(engine):
    settings = Settings(
        database_host="localhost",
        database_port=5434,
        database_name="gemeente_data_test",
        database_user="gemeente_bootstrap",
        database_password_file=Path("secrets/postgres_password.txt"),
    )
    bootstrap_engine = create_engine(settings.database_url())
    try:
        preflight_database(bootstrap_engine, settings, create_roles=False)
        preflight_database(bootstrap_engine, settings, create_roles=False)
    finally:
        bootstrap_engine.dispose()


def test_loader_rollback_preserves_previous_snapshot_and_records_failure(
    engine, tmp_path, monkeypatch
):
    """Een fout na start van de loadtransactie rolt core terug en audit veilig."""
    assert load_snapshot(engine, _run(tmp_path / "stable", "stable", 11)) == "success"
    before = (
        engine.connect()
        .execute(
            text(
                "SELECT population_january_1 FROM core.fact_population WHERE period_code='2026JJ00'"
            )
        )
        .scalar_one()
    )
    original_execute = Connection.execute

    def fail_on_delete(self, statement, *args, **kwargs):
        if "DELETE FROM core.fact_population" in str(statement):
            raise RuntimeError("test transaction failure")
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Connection, "execute", fail_on_delete)
    with pytest.raises(RuntimeError, match="test transaction failure"):
        load_snapshot(engine, _run(tmp_path / "broken", "broken", 99))
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT population_january_1 FROM core.fact_population WHERE period_code='2026JJ00'"
                )
            ).scalar_one()
            == before
        )
        failure = c.execute(
            text(
                "SELECT status, error_message FROM ops.etl_run WHERE processed_run_id='broken'"
            )
        ).one()
        assert failure[0] == "failed"
        assert "postgresql" not in failure[1].lower()
