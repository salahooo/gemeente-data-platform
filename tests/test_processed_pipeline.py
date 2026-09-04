"""Offline tests voor raw-selectie, processed transformatie en publicatie."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gemeente_data_platform.data_contracts import DataContractError
from gemeente_data_platform.population_transformation import build_processed_tables
from gemeente_data_platform.processed_contracts import (
    ProcessedContractError,
    validate_processed_tables,
)
from gemeente_data_platform.processed_storage import (
    RawRun,
    load_raw_run,
    publish_processed_run,
    select_raw_run,
)
from gemeente_data_platform.raw_storage import sha256_file, write_json_atomically


@pytest.fixture
def raw_fixture() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Kleine raw set met historische, verschijnende en verdwijnende GM-codes."""
    records = [
        _record("GM0001", "2020JJ00", 10, 10.5),
        _record("GM0001", "2021JJ00", 11, 11.5),
        _record("GM0002", "2020JJ00", 20, None),
        _record("GM0002", "2021JJ00", None, None),
        _record("GM0003", "2020JJ00", None, None),
        _record("GM0003", "2021JJ00", None, None),
        _record("GM0004", "2020JJ00", None, None),
        _record("GM0004", "2021JJ00", 40, None),
    ]
    regions = [
        {"Key": "GM0001", "Title": "Een"},
        {"Key": "GM0002", "Title": "Twee"},
        {"Key": "GM0003", "Title": "Historisch"},
        {"Key": "GM0004", "Title": "Vier"},
    ]
    periods = [
        {"Key": "2020JJ00", "Title": "2020"},
        {"Key": "2021JJ00", "Title": "2021"},
    ]
    quality = {
        "period_statistics": {
            "2020JJ00": {
                "active_municipality_count": 2,
                "january_population_sum": 30,
            },
            "2021JJ00": {
                "active_municipality_count": 2,
                "january_population_sum": 51,
            },
        }
    }
    return records, regions, periods, quality


def test_build_processed_tables_keeps_only_active_observations(raw_fixture) -> None:
    """Historische null-records komen niet in processed dimensie of fact."""
    records, regions, periods, quality = raw_fixture

    tables = build_processed_tables(records, regions, periods, quality)

    assert set(tables.dim_municipality["municipality_code"]) == {
        "GM0001",
        "GM0002",
        "GM0004",
    }
    assert len(tables.fact_population) == 4
    assert (
        tables.fact_population.loc[
            tables.fact_population["municipality_code"] == "GM0002",
            "average_population",
        ]
        .isna()
        .all()
    )


def test_dimension_history_and_latest_flag_are_derived(raw_fixture) -> None:
    """First/last zijn observatiejaren en niet juridische datums."""
    records, regions, periods, quality = raw_fixture
    municipality = build_processed_tables(
        records, regions, periods, quality
    ).dim_municipality

    two = municipality.loc[municipality["municipality_code"] == "GM0002"].iloc[0]
    four = municipality.loc[municipality["municipality_code"] == "GM0004"].iloc[0]
    assert (two["first_observed_year"], two["last_observed_year"]) == (2020, 2020)
    assert not two["is_active_latest_period"]
    assert (four["first_observed_year"], four["last_observed_year"]) == (2021, 2021)
    assert four["is_active_latest_period"]


def test_processed_contract_rejects_negative_population(raw_fixture) -> None:
    """Negatieve waarden breken de processed kwaliteitscontrole."""
    records, regions, periods, quality = raw_fixture
    tables = build_processed_tables(records, regions, periods, quality)
    invalid_fact = tables.fact_population.copy()
    invalid_fact.loc[0, "population_january_1"] = -1

    with pytest.raises(ProcessedContractError, match="negative"):
        validate_processed_tables(
            tables.dim_municipality, tables.dim_period, invalid_fact
        )


def test_transformation_rejects_inconsistent_raw_reconciliation(raw_fixture) -> None:
    """Een raw kwaliteitsrapport met onjuiste totalen stopt de transformatie."""
    records, regions, periods, quality = raw_fixture
    quality["period_statistics"]["2020JJ00"]["january_population_sum"] = 31

    with pytest.raises(ProcessedContractError, match="reconciliation"):
        build_processed_tables(records, regions, periods, quality)


def test_transformation_copies_relevant_raw_warnings(raw_fixture) -> None:
    """Bronwaarschuwingen blijven zichtbaar in het processed kwaliteitsrapport."""
    records, regions, periods, quality = raw_fixture
    quality["warnings"] = ["Gemiddelde bevolking ontbreekt voor 2021JJ00."]

    tables = build_processed_tables(records, regions, periods, quality)

    assert (
        "Gemiddelde bevolking ontbreekt voor 2021JJ00."
        in tables.quality_report["warnings"]
    )


def test_publish_processed_run_writes_equivalent_parquet_and_csv(
    tmp_path: Path, raw_fixture
) -> None:
    """Publicatie schrijft beide formaten, quality report en manifest atomair."""
    records, regions, periods, quality = raw_fixture
    tables = build_processed_tables(records, regions, periods, quality)
    raw_run = RawRun(
        directory=tmp_path / "raw-run",
        manifest={
            "dataset_title": "Fixture",
            "selected_periods": ["2020JJ00", "2021JJ00"],
        },
        quality_report=quality,
    )
    raw_run.directory.mkdir()
    write_json_atomically({}, raw_run.directory / "manifest.json")
    output = publish_processed_run(
        "03759ned",
        "Fixture",
        raw_run,
        {
            "dim_municipality": tables.dim_municipality,
            "dim_period": tables.dim_period,
            "fact_population": tables.fact_population,
        },
        tables.quality_report,
        output_root=tmp_path / "processed",
        run_id="20260904T010000000000Z",
    )

    assert (output / "fact_population.parquet").is_file()
    assert (output / "fact_population.csv").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["quality_status"]["parquet_csv_equivalent"]
    assert manifest["tables"]["fact_population"]["files"] == {
        "parquet": "fact_population.parquet",
        "csv": "fact_population.csv",
    }
    assert "manifest.json" not in manifest["checksums_sha256"]


def test_failed_publication_removes_temporary_directory(
    tmp_path: Path, raw_fixture, monkeypatch
) -> None:
    """Een schrijffout laat geen gedeeltelijke processed run achter."""
    records, regions, periods, quality = raw_fixture
    tables = build_processed_tables(records, regions, periods, quality)
    raw_run = RawRun(
        directory=tmp_path / "raw-run",
        manifest={
            "dataset_title": "Fixture",
            "selected_periods": ["2020JJ00", "2021JJ00"],
        },
        quality_report=quality,
    )
    raw_run.directory.mkdir()
    write_json_atomically({}, raw_run.directory / "manifest.json")

    def fail_write(*args, **kwargs) -> None:
        raise OSError("simulated parquet write failure")

    monkeypatch.setattr(type(tables.dim_municipality), "to_parquet", fail_write)
    with pytest.raises(OSError, match="simulated"):
        publish_processed_run(
            "03759ned",
            "Fixture",
            raw_run,
            {"dim_municipality": tables.dim_municipality},
            tables.quality_report,
            output_root=tmp_path / "processed",
            run_id="20260904T010000000001Z",
        )

    temporary = tmp_path / "processed" / "03759ned" / ".20260904T010000000001Z.tmp"
    assert not temporary.exists()
    assert not (tmp_path / "processed" / "03759ned" / "20260904T010000000001Z").exists()


def test_load_raw_run_rejects_bad_checksum(tmp_path: Path) -> None:
    """Een beschadigde raw run wordt nooit stilzwijgend geselecteerd."""
    directory = _create_raw_run(tmp_path / "raw" / "cbs" / "03759ned" / "run-a")
    (directory / "regions.json").write_text('{"value": []}', encoding="utf-8")

    with pytest.raises(DataContractError, match="checksum"):
        load_raw_run(directory)


def test_select_raw_run_chooses_newest_valid_run(tmp_path: Path, monkeypatch) -> None:
    """Automatische selectie slaat onvolledige nieuwere runs over."""
    import gemeente_data_platform.processed_storage as storage

    root = tmp_path / "raw" / "cbs"
    _create_raw_run(root / "03759ned" / "20260101T000000000000Z")
    (root / "03759ned" / "20270101T000000000000Z").mkdir(parents=True)
    monkeypatch.setattr(storage, "RAW_RUN_ROOT", root)

    assert select_raw_run("03759ned").run_id == "20260101T000000000000Z"


def test_select_raw_run_accepts_explicit_run_id(tmp_path: Path, monkeypatch) -> None:
    """Een expliciete run-id kiest precies die checksumgeldige raw run."""
    import gemeente_data_platform.processed_storage as storage

    root = tmp_path / "raw" / "cbs"
    _create_raw_run(root / "03759ned" / "20260101T000000000000Z")
    _create_raw_run(root / "03759ned" / "20270101T000000000000Z")
    monkeypatch.setattr(storage, "RAW_RUN_ROOT", root)

    selected = select_raw_run("03759ned", "20260101T000000000000Z")

    assert selected.run_id == "20260101T000000000000Z"


def _record(
    code: str, period: str, january: int | None, average: float | None
) -> dict[str, Any]:
    """Maak één kleine raw bevolkingsrecordfixture."""
    return {
        "RegioS": code,
        "Perioden": period,
        "BevolkingOp1Januari_1": january,
        "GemiddeldeBevolking_2": average,
    }


def _create_raw_run(directory: Path) -> Path:
    """Maak een minimale checksumgeldige raw run voor selectietests."""
    directory.mkdir(parents=True)
    files = {
        "table_info.json": {"value": [{"Title": "Fixture"}]},
        "regions.json": {"value": []},
        "periods.json": {"value": []},
        "population_records.json": {"value": []},
        "quality_report.json": {"period_statistics": {}},
    }
    for filename, payload in files.items():
        write_json_atomically(payload, directory / filename)
    checksums = {filename: sha256_file(directory / filename) for filename in files}
    manifest = {
        "schema_version": "2.0",
        "dataset_code": "03759ned",
        "dataset_title": "Fixture",
        "retrieved_at_utc": "2026-09-04T00:00:00Z",
        "base_url": "https://example.test",
        "endpoints": {},
        "query_parameters": {},
        "selected_dimensions": {},
        "selected_periods": [],
        "api_page_count": 1,
        "record_count": 0,
        "files": {},
        "checksums_sha256": checksums,
        "validation_status": {},
        "quality": files["quality_report.json"],
    }
    write_json_atomically(manifest, directory / "manifest.json")
    return directory
