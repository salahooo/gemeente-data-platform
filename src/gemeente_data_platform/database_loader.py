"""Idempotente snapshot-load vanuit een gevalideerde processed run."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from gemeente_data_platform.processed_storage import PROCESSED_ROOT
from gemeente_data_platform.raw_storage import sha256_file, verify_checksums


@dataclass(frozen=True)
class ProcessedRun:
    directory: Path
    manifest: dict[str, Any]
    quality: dict[str, Any]


def select_processed_run(
    dataset_code: str, selected: str | None = None
) -> ProcessedRun:
    """Selecteer de nieuwste volledig checksumgeldige processed run."""
    root = PROCESSED_ROOT / dataset_code
    candidates = [root / selected] if selected else sorted(root.iterdir(), reverse=True)
    for directory in candidates:
        if directory.is_dir():
            try:
                return load_processed_run(directory)
            except (OSError, ValueError, json.JSONDecodeError):
                if selected:
                    raise
    raise ValueError("No complete and valid processed run is available.")


def load_processed_run(directory: Path) -> ProcessedRun:
    """Valideer manifest, verwachte bestanden en checksums."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    required = {"dim_municipality", "dim_period", "fact_population"}
    if not required.issubset(manifest.get("tables", {})):
        raise ValueError("Processed manifest lacks required tables.")
    checksums = manifest.get("checksums_sha256")
    if not isinstance(checksums, dict) or not verify_checksums(directory, checksums):
        raise ValueError("Processed run checksum verification failed.")
    quality = json.loads(
        (directory / "quality_report.json").read_text(encoding="utf-8")
    )
    return ProcessedRun(directory, manifest, quality)


def load_snapshot(engine: Any, run: ProcessedRun, dry_run: bool = False) -> str:
    """Laad een snapshot transactioneel; een eerder geslaagde run is een no-op."""
    run_id = str(uuid.uuid4())
    processed_id = run.manifest["processed_run_id"]
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one_or_none()
    if revision != "20260904_02":
        raise ValueError("Database migration revision is not at the required head.")
    if dry_run:
        return "dry-run"
    with engine.begin() as connection:
        existing = connection.execute(
            text("SELECT status FROM ops.etl_run WHERE processed_run_id = :run"),
            {"run": processed_id},
        ).scalar_one_or_none()
        if existing == "success":
            return "skipped"
        connection.execute(
            text(
                "INSERT INTO ops.etl_run (run_id, processed_run_id, raw_run_id, raw_manifest_checksum, processed_manifest_checksum, started_at, status, application_version) VALUES (:id, :processed, :raw, :raw_checksum, :processed_checksum, :started, 'running', :version)"
            ),
            {
                "id": run_id,
                "processed": processed_id,
                "raw": run.manifest["raw_run_id"],
                "raw_checksum": run.manifest["raw_manifest_checksum"],
                "processed_checksum": sha256_file(run.directory / "manifest.json"),
                "started": datetime.now(UTC),
                "version": run.manifest["transformation_version"],
            },
        )
    try:
        frames = {
            name: pd.read_parquet(run.directory / f"{name}.parquet", engine="pyarrow")
            for name in ("dim_municipality", "dim_period", "fact_population")
        }
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM core.fact_population"))
            connection.execute(text("DELETE FROM core.dim_municipality"))
            connection.execute(text("DELETE FROM core.dim_period"))
            for name, frame in frames.items():
                rows = (
                    frame.astype(object)
                    .where(pd.notna(frame), None)
                    .to_dict(orient="records")
                )
                connection.execute(
                    text(
                        f"INSERT INTO core.{name} ({', '.join(frame.columns)}) VALUES ({', '.join(':' + column for column in frame.columns)})"
                    ),
                    rows,
                )
            actual = connection.execute(
                text("SELECT COUNT(*) FROM core.fact_population")
            ).scalar_one()
            if actual != len(frames["fact_population"]):
                raise ValueError("Database fact reconciliation failed.")
            connection.execute(
                text(
                    "UPDATE ops.etl_run SET status = 'success', finished_at = :now, loaded_at = :now, dim_municipality_count = :m, dim_period_count = :p, fact_population_count = :f WHERE run_id = :id"
                ),
                {
                    "now": datetime.now(UTC),
                    "m": len(frames["dim_municipality"]),
                    "p": len(frames["dim_period"]),
                    "f": actual,
                    "id": run_id,
                },
            )
    except Exception as exc:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE ops.etl_run SET status = 'failed', finished_at = :now, error_category = :category, error_message = :message WHERE run_id = :id"
                ),
                {
                    "now": datetime.now(UTC),
                    "category": type(exc).__name__,
                    "message": str(exc)[:300],
                    "id": run_id,
                },
            )
        raise
    return "success"
