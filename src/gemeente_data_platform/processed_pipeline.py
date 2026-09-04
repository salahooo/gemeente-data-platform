"""Orkestreer de raw-naar-processed transformatie zonder CBS API-calls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gemeente_data_platform.population_transformation import build_processed_tables
from gemeente_data_platform.processed_storage import (
    PROCESSED_ROOT,
    RawRun,
    publish_processed_run,
    read_raw_collection,
    select_raw_run,
)


@dataclass(frozen=True)
class ProcessedSummary:
    """Compact resultaat van één succesvol gepubliceerde processed run."""

    raw_run: RawRun
    output_directory: Path
    table_rows: dict[str, int]
    table_columns: dict[str, list[str]]
    quality_report: dict[str, object]


def transform_raw_run(
    dataset_code: str,
    raw_run_selector: str | None = None,
    output_root: Path = PROCESSED_ROOT,
) -> ProcessedSummary:
    """Selecteer, verifieer en transformeer één raw run naar processed opslag."""
    raw_run = select_raw_run(dataset_code, raw_run_selector)
    records = read_raw_collection(raw_run, "population_records.json")
    regions = read_raw_collection(raw_run, "regions.json")
    periods = read_raw_collection(raw_run, "periods.json")
    tables = build_processed_tables(records, regions, periods, raw_run.quality_report)
    table_frames = {
        "dim_municipality": tables.dim_municipality,
        "dim_period": tables.dim_period,
        "fact_population": tables.fact_population,
    }
    output_directory = publish_processed_run(
        dataset_code=dataset_code,
        dataset_title=raw_run.manifest["dataset_title"],
        raw_run=raw_run,
        tables=table_frames,
        quality_report=tables.quality_report,
        output_root=output_root,
    )
    return ProcessedSummary(
        raw_run=raw_run,
        output_directory=output_directory,
        table_rows={name: len(dataframe) for name, dataframe in table_frames.items()},
        table_columns={
            name: list(dataframe.columns) for name, dataframe in table_frames.items()
        },
        quality_report=tables.quality_report,
    )
