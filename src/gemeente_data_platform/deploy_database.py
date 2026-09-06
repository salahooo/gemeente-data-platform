"""Explicit, guarded managed-PostgreSQL deployment procedure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import String, bindparam, text

from alembic import command
from gemeente_data_platform.config import PROJECT_ROOT, Settings
from gemeente_data_platform.database import create_database_engine
from gemeente_data_platform.database_loader import load_processed_run, load_snapshot
from gemeente_data_platform.database_validator import validate_database_snapshot
from gemeente_data_platform.pipeline_security import redact
from gemeente_data_platform.processed_storage import PROCESSED_ROOT
from gemeente_data_platform.profile_pipeline import load_profile, read_run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explicit managed PostgreSQL bootstrap; never calls CBS."
    )
    runs = parser.add_mutually_exclusive_group(required=True)
    runs.add_argument("--processed-run")
    runs.add_argument("--profile-run", help="Load only a validated CBS 70072ned run")
    parser.add_argument("--dataset-code", default="03759ned")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--migrate-only", action="store_true")
    parser.add_argument(
        "--create-roles",
        action="store_true",
        help=(
            "Create the documented least-privilege roles when the provider permits it."
        ),
    )
    return parser.parse_args(argv)


def _missing_roles(connection: Any) -> set[str]:
    present = set(
        connection.execute(
            text(
                "SELECT rolname FROM pg_roles "
                "WHERE rolname IN ('gemeente_app', 'gemeente_reader', 'gemeente_api')"
            )
        ).scalars()
    )
    return {"gemeente_app", "gemeente_reader", "gemeente_api"} - present


def _create_roles(connection: Any, settings: Settings) -> None:
    app_password = settings.bootstrap_app_password
    api_password = settings.bootstrap_api_password
    if app_password is None or api_password is None:
        raise ValueError(
            "--create-roles requires BOOTSTRAP_APP_PASSWORD and "
            "BOOTSTRAP_API_PASSWORD runtime secrets."
        )
    if not connection.execute(
        text("SELECT rolcreaterole FROM pg_roles WHERE rolname = current_user")
    ).scalar_one():
        raise ValueError(
            "Provider login cannot CREATE ROLE. Create gemeente_app, gemeente_reader "
            "and gemeente_api manually in the provider console, then rerun preflight."
        )
    for role, password in (
        ("gemeente_app", app_password.get_secret_value()),
        ("gemeente_api", api_password.get_secret_value()),
    ):
        create_sql = connection.execute(
            text(
                "SELECT format("
                f"'CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOREPLICATION PASSWORD %L', CAST(:password AS text)) "
                "WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :role)"
            ).bindparams(bindparam("password", type_=String())),
            {"password": password, "role": role},
        ).scalar_one_or_none()
        if create_sql:
            connection.execute(text(create_sql))
    connection.execute(
        text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
            "'gemeente_reader') THEN CREATE ROLE gemeente_reader NOLOGIN NOSUPERUSER "
            "NOCREATEDB NOCREATEROLE NOREPLICATION; END IF; END $$"
        )
    )
    for grant in (
        "GRANT CONNECT, CREATE ON DATABASE %I TO gemeente_app",
        "GRANT CONNECT ON DATABASE %I TO gemeente_reader, gemeente_api",
    ):
        statement = connection.execute(
            text("SELECT format(:grant, current_database())"), {"grant": grant}
        ).scalar_one()
        connection.execute(text(statement))
    connection.execute(text("GRANT USAGE, CREATE ON SCHEMA public TO gemeente_app"))


def preflight_database(engine: Any, settings: Settings, create_roles: bool) -> None:
    """Verify all prerequisites before immutable revisions are invoked."""
    with engine.begin() as connection:
        connection.execute(text("SELECT 1"))
        missing = _missing_roles(connection)
        if missing and create_roles:
            _create_roles(connection, settings)
            missing = _missing_roles(connection)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(
                f"Managed database is missing required roles: {names}. "
                "Create them with the provider console or rerun with --create-roles "
                "using a provider login with CREATEROLE."
            )
        can_create = connection.execute(
            text(
                "SELECT has_database_privilege("
                "current_user, current_database(), 'CREATE')"
            )
        ).scalar_one()
        if not can_create:
            raise ValueError(
                "Provider login lacks CREATE on the target database; "
                "Alembic cannot run."
            )


def processed_run_directory(dataset_code: str, processed_run: str) -> Path:
    """Resolve only one canonical, non-traversing processed run directory."""
    dataset = _safe_path_component(dataset_code, "dataset code")
    run_id = _safe_path_component(processed_run, "processed run id")
    candidate = (PROCESSED_ROOT / dataset / run_id).resolve()
    root = PROCESSED_ROOT.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Processed run path must stay within canonical storage.")
    return candidate


def _safe_path_component(value: str, label: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label.capitalize()} must be a single path component.")
    if Path(value).is_absolute():
        raise ValueError(f"{label.capitalize()} must be a relative path component.")
    return value


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        settings = Settings()
        if settings.app_env != "production":
            raise ValueError("Bootstrap requires APP_ENV=production.")
        # Settings validates URL, SSL, CORS and disallows localhost before I/O.
        if args.dry_run:
            if args.profile_run:
                read_run(processed_run_directory("70072ned", args.profile_run))
            print("Dry run: connectivity -> migrations -> load -> validate -> ready")
            return
        engine = create_database_engine()
        preflight_database(engine, settings, args.create_roles)
        command.upgrade(Config(str(PROJECT_ROOT / "alembic.ini")), "head")
        if args.migrate_only:
            print("Migrations completed; no pipeline load was requested.")
            return
        if args.profile_run:
            result = load_profile(
                engine, processed_run_directory("70072ned", args.profile_run)
            )
            print(f"Profile deployment completed: {result}")
            return
        run = load_processed_run(
            processed_run_directory(args.dataset_code, args.processed_run)
        )
        load_snapshot(engine, run)
        validate_database_snapshot(engine, run)
        print("Managed database bootstrap completed and snapshot is ready.")
    except Exception as exc:
        print(f"DEPLOYMENT DATABASE ERROR: {redact(str(exc))}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
