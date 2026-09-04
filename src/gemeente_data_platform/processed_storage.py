"""Selectie, verificatie en atomaire publicatie van processed runs."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from gemeente_data_platform.data_contracts import DataContractError, validate_manifest
from gemeente_data_platform.processed_contracts import validate_processed_tables
from gemeente_data_platform.raw_storage import sha256_file, verify_checksums

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_RUN_ROOT = PROJECT_ROOT / "data" / "raw" / "cbs"
PROCESSED_ROOT = PROJECT_ROOT / "data" / "processed" / "cbs"
REQUIRED_RAW_FILES = {
    "table_info.json",
    "regions.json",
    "periods.json",
    "population_records.json",
    "quality_report.json",
    "manifest.json",
}


@dataclass(frozen=True)
class RawRun:
    """Een geverifieerde raw run die veilig voor transformatie gebruikt kan worden."""

    directory: Path
    manifest: dict[str, Any]
    quality_report: dict[str, Any]

    @property
    def run_id(self) -> str:
        """Geef de draagbare run-id terug."""
        return self.directory.name


def select_raw_run(dataset_code: str, raw_run: str | None = None) -> RawRun:
    """Selecteer expliciet of automatisch de nieuwste volledig geldige raw run."""
    if raw_run is not None:
        candidate = _resolve_raw_run_path(dataset_code, raw_run)
        return load_raw_run(candidate)
    candidates = sorted(
        (path for path in (RAW_RUN_ROOT / dataset_code).iterdir() if path.is_dir()),
        reverse=True,
    )
    for candidate in candidates:
        try:
            return load_raw_run(candidate)
        except (DataContractError, OSError, json.JSONDecodeError):
            continue
    raise DataContractError("No complete and valid raw run is available.")


def load_raw_run(directory: Path) -> RawRun:
    """Laad en verifieer de manifest-, checksum- en bestandscontracten van raw data."""
    if not directory.is_dir():
        raise DataContractError(f"Raw run directory does not exist: {directory.name}.")
    missing = sorted(
        name for name in REQUIRED_RAW_FILES if not (directory / name).is_file()
    )
    if missing:
        raise DataContractError(f"Raw run is incomplete: {', '.join(missing)}.")
    manifest = _read_json(directory / "manifest.json")
    validate_manifest(manifest)
    if not verify_checksums(directory, manifest["checksums_sha256"]):
        raise DataContractError("Raw run checksum verification failed.")
    quality_report = _read_json(directory / "quality_report.json")
    if manifest["quality"] != quality_report:
        raise DataContractError("Raw manifest and quality report are inconsistent.")
    return RawRun(directory=directory, manifest=manifest, quality_report=quality_report)


def read_raw_collection(raw_run: RawRun, filename: str) -> list[dict[str, Any]]:
    """Lees één raw OData-collectie en valideer de ongewijzigde value-lijst."""
    payload = _read_json(raw_run.directory / filename)
    value = payload.get("value")
    if not isinstance(value, list) or not all(
        isinstance(record, dict) for record in value
    ):
        raise DataContractError(
            f"Raw collection {filename} does not contain object records."
        )
    return value


def publish_processed_run(
    dataset_code: str,
    dataset_title: str,
    raw_run: RawRun,
    tables: dict[str, pd.DataFrame],
    quality_report: dict[str, Any],
    output_root: Path = PROCESSED_ROOT,
    run_id: str | None = None,
) -> Path:
    """Schrijf Parquet/CSV, verifieer ze en publiceer de run atomair."""
    processed_run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = output_root / dataset_code / processed_run_id
    temporary = destination.with_name(f".{processed_run_id}.tmp")
    if destination.exists() or temporary.exists():
        raise DataContractError("Processed run-id already exists.")
    temporary.mkdir(parents=True)
    try:
        data_files: dict[str, str] = {}
        for table_name, dataframe in tables.items():
            parquet_name = f"{table_name}.parquet"
            csv_name = f"{table_name}.csv"
            dataframe.to_parquet(
                temporary / parquet_name, index=False, engine="pyarrow"
            )
            dataframe.to_csv(
                temporary / csv_name, index=False, encoding="utf-8", na_rep=""
            )
            data_files[f"{table_name}_parquet"] = parquet_name
            data_files[f"{table_name}_csv"] = csv_name
        _write_json(quality_report, temporary / "quality_report.json")
        data_files["quality_report"] = "quality_report.json"
        reloaded = {
            name: pd.read_parquet(temporary / f"{name}.parquet", engine="pyarrow")
            for name in tables
        }
        validate_processed_tables(
            reloaded["dim_municipality"],
            reloaded["dim_period"],
            reloaded["fact_population"],
        )
        _verify_csv_equivalence(tables, temporary)
        checksums = {
            filename: sha256_file(temporary / filename)
            for filename in data_files.values()
        }
        if not verify_checksums(temporary, checksums):
            raise DataContractError("Processed file checksum verification failed.")
        manifest = {
            "schema_version": "1.0",
            "dataset_code": dataset_code,
            "dataset_title": dataset_title,
            "processed_run_id": processed_run_id,
            "transformed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "raw_run_id": raw_run.run_id,
            "raw_run_path": f"cbs/{dataset_code}/{raw_run.run_id}",
            "raw_manifest_checksum": sha256_file(raw_run.directory / "manifest.json"),
            "selected_periods": raw_run.manifest["selected_periods"],
            "transformation_version": "0.1.0",
            "tables": {
                name: {
                    "files": {
                        "parquet": f"{name}.parquet",
                        "csv": f"{name}.csv",
                    },
                    "rows": len(dataframe),
                    "columns": list(dataframe.columns),
                    "dtypes": {
                        column: str(dtype) for column, dtype in dataframe.dtypes.items()
                    },
                }
                for name, dataframe in tables.items()
            },
            "checksums_sha256": checksums,
            "quality_status": {"validated": True, "parquet_csv_equivalent": True},
            "warnings": quality_report["warnings"],
            "selection_rules": [
                "Alleen actieve januariwaarnemingen worden factrecords.",
                "Historische gemeentecodes worden niet geografisch geharmoniseerd.",
            ],
        }
        _write_json(manifest, temporary / "manifest.json")
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _resolve_raw_run_path(dataset_code: str, raw_run: str) -> Path:
    """Ondersteun een run-id of een draagbaar pad relatief aan de projectroot."""
    supplied = Path(raw_run)
    if supplied.is_absolute() or supplied.parts[:-1]:
        return supplied if supplied.is_absolute() else PROJECT_ROOT / supplied
    return RAW_RUN_ROOT / dataset_code / raw_run


def _read_json(path: Path) -> dict[str, Any]:
    """Lees één JSON-object uit de landing zone."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DataContractError(f"JSON file {path.name} is not an object.")
    return data


def _write_json(data: dict[str, Any], path: Path) -> None:
    """Schrijf een processed metadata-object atomair via de bestaande helper."""
    from gemeente_data_platform.raw_storage import write_json_atomically

    write_json_atomically(data, path)


def _verify_csv_equivalence(tables: dict[str, pd.DataFrame], directory: Path) -> None:
    """Controleer inhoudelijke gelijkwaardigheid tussen Parquet-bron en CSV-export."""
    for name, dataframe in tables.items():
        csv_frame = pd.read_csv(directory / f"{name}.csv", dtype="string")
        expected = dataframe.astype("string").fillna("")
        actual = csv_frame.fillna("")
        if not expected.equals(actual):
            raise DataContractError(f"CSV export differs from {name} data.")
