"""Ontdek CBS-dimensies en extraheer ongetransformeerde gemeenterecords."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gemeente_data_platform.cbs_client import CbsClient, CollectionResult
from gemeente_data_platform.config import Settings
from gemeente_data_platform.data_contracts import (
    DataContractError,
    Manifest,
    SelectedDimension,
    SelectedDimensions,
    validate_collection_response,
    validate_population_record,
)
from gemeente_data_platform.quality import build_quality_report
from gemeente_data_platform.raw_storage import (
    RAW_ROOT,
    create_run_directory,
    sha256_file,
    verify_checksums,
    write_json_atomically,
)

DIMENSION_ENDPOINTS = {
    "data_properties": "DataProperties",
    "gender": "Geslacht",
    "age": "Leeftijd",
    "marital_status": "BurgerlijkeStaat",
    "regions": "RegioS",
    "periods": "Perioden",
}
DIMENSION_FILES = {
    "data_properties": "data_properties.json",
    "gender": "gender.json",
    "age": "age.json",
    "marital_status": "marital_status.json",
    "regions": "regions.json",
    "periods": "periods.json",
}
POPULATION_ENDPOINT = "TypedDataSet"
POPULATION_FILE = "population_records.json"
TABLE_INFO_FILE = "table_info.json"
MANIFEST_FILE = "manifest.json"
QUALITY_REPORT_FILE = "quality_report.json"
MUNICIPAL_CODE_PATTERN = re.compile(r"GM\d{4}")
PERIOD_CODE_PATTERN = re.compile(r"(\d{4})JJ00")


@dataclass(frozen=True)
class ExtractionSummary:
    """Compact resultaat van één succesvolle extractierun."""

    dataset_code: str
    dataset_title: str
    period_codes: list[str]
    municipal_code_count: int
    record_count: int
    active_observation_count: int
    active_municipality_counts: dict[str, int]
    missing_january_population_count: int
    missing_average_population_count: int
    warnings: list[str]
    api_page_count: int
    output_directory: Path
    selected_dimensions: SelectedDimensions


def extract_population(
    client: CbsClient,
    settings: Settings,
    raw_root: Path = RAW_ROOT,
    run_id: str | None = None,
) -> ExtractionSummary:
    """Ontdek dimensies, valideer records en schrijf één raw extractierun."""
    retrieved_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    table_info = client.get_table_info()
    table_info_records = validate_collection_response(table_info)
    dataset_title = _dataset_title(table_info_records)

    dimension_results = {
        name: client.get_collection(endpoint)
        for name, endpoint in DIMENSION_ENDPOINTS.items()
    }
    dimensions = {name: result.records for name, result in dimension_results.items()}
    selected_dimensions = discover_selected_dimensions(dimensions)
    period_codes = discover_period_codes(dimensions["periods"])
    municipal_regions = discover_municipal_regions(dimensions["regions"])
    population_params = build_population_query(selected_dimensions)
    population_result = client.get_collection(
        POPULATION_ENDPOINT, params=population_params
    )
    population_records = validate_population_records(
        population_result.records,
        selected_dimensions,
        period_codes,
        municipal_regions,
    )
    quality_report = build_quality_report(population_records, period_codes)
    quality_report["dataset_code"] = settings.cbs_dataset_code
    quality_report["dataset_title"] = dataset_title

    output_directory = create_run_directory(
        settings.cbs_dataset_code, run_id=run_id, root=raw_root
    )
    data_files = _write_raw_files(
        output_directory,
        table_info,
        dimension_results,
        population_result,
        quality_report,
    )
    checksums = {
        filename: sha256_file(output_directory / filename)
        for filename in data_files.values()
    }
    validation_status = {
        "collection_responses_contain_lists": True,
        "selected_dimension_codes_exist": True,
        "municipal_codes_are_unique_and_valid": True,
        "period_codes_are_valid_from_2020": True,
        "population_records_are_valid": True,
        "municipality_period_combinations_are_unique": True,
        "non_empty_extract": True,
        "quality_statistics_are_valid": True,
        "checksums_reverified": verify_checksums(output_directory, checksums),
    }
    if not validation_status["checksums_reverified"]:
        raise DataContractError("Raw file checksums could not be revalidated.")

    manifest = Manifest(
        schema_version="2.0",
        dataset_code=settings.cbs_dataset_code,
        dataset_title=dataset_title,
        retrieved_at_utc=retrieved_at,
        base_url=settings.cbs_base_url,
        endpoints={
            "table_info": "TableInfos",
            **DIMENSION_ENDPOINTS,
            "population": POPULATION_ENDPOINT,
        },
        query_parameters={"population": population_params},
        selected_dimensions=selected_dimensions.as_dict(),
        selected_periods=period_codes,
        api_page_count=1
        + sum(result.page_count for result in dimension_results.values())
        + population_result.page_count,
        record_count=len(population_records),
        files={**data_files, "manifest": MANIFEST_FILE},
        checksums_sha256=checksums,
        validation_status=validation_status,
        quality=quality_report,
    )
    write_json_atomically(manifest.as_dict(), output_directory / MANIFEST_FILE)

    return ExtractionSummary(
        dataset_code=settings.cbs_dataset_code,
        dataset_title=dataset_title,
        period_codes=period_codes,
        municipal_code_count=quality_report["unique_municipal_code_count"],
        record_count=len(population_records),
        active_observation_count=quality_report[
            "active_municipality_observation_count"
        ],
        active_municipality_counts={
            period: statistics["active_municipality_count"]
            for period, statistics in quality_report["period_statistics"].items()
        },
        missing_january_population_count=sum(
            statistics["missing_january_population_count"]
            for statistics in quality_report["period_statistics"].values()
        ),
        missing_average_population_count=sum(
            statistics["missing_average_population_count"]
            for statistics in quality_report["period_statistics"].values()
        ),
        warnings=quality_report["warnings"],
        api_page_count=manifest.api_page_count,
        output_directory=output_directory,
        selected_dimensions=selected_dimensions,
    )


def discover_selected_dimensions(
    dimensions: Mapping[str, list[dict[str, Any]]],
) -> SelectedDimensions:
    """Vind en valideer totalen en meetvelden aan de hand van CBS-titels."""
    return SelectedDimensions(
        gender=_find_by_title(dimensions["gender"], "Totaal mannen en vrouwen"),
        age=_find_by_title(dimensions["age"], "Totaal"),
        marital_status=_find_by_title(
            dimensions["marital_status"], "Totaal burgerlijke staat"
        ),
        population_on_january_1=_find_by_title(
            dimensions["data_properties"], "Bevolking op 1 januari"
        ),
        average_population=_find_by_title(
            dimensions["data_properties"], "Gemiddelde bevolking"
        ),
    )


def discover_period_codes(periods: list[dict[str, Any]]) -> list[str]:
    """Selecteer gevalideerde jaarlijkse periodecodes vanaf 2020."""
    selected: list[str] = []
    for period in periods:
        key = period.get("Key")
        title = period.get("Title")
        match = PERIOD_CODE_PATTERN.fullmatch(key) if isinstance(key, str) else None
        if match is None or not isinstance(title, str) or not title.isdigit():
            continue
        if int(match.group(1)) != int(title):
            raise DataContractError(
                f"Period code {key} does not match its title {title}."
            )
        if int(title) >= 2020:
            selected.append(key)
    if not selected:
        raise DataContractError("No annual CBS periods from 2020 onwards were found.")
    return sorted(selected)


def discover_municipal_regions(
    regions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Herken gemeenten uitsluitend via de officiële `GMdddd`-regiostructuur."""
    municipalities: dict[str, dict[str, Any]] = {}
    for region in regions:
        key = region.get("Key")
        if not isinstance(key, str):
            continue
        normalized_key = key.strip()
        if MUNICIPAL_CODE_PATTERN.fullmatch(normalized_key):
            if normalized_key in municipalities:
                raise DataContractError(
                    f"Municipal region code {normalized_key} is duplicated."
                )
            municipalities[normalized_key] = region
    if not municipalities:
        raise DataContractError(
            "No municipal regions with an official GM code were found."
        )
    return municipalities


def build_population_query(selected: SelectedDimensions) -> dict[str, str]:
    """Bouw een gerichte OData-query op basis van ontdekte dimensiecodes."""
    filters = [
        f"Geslacht eq '{selected.gender.code}'",
        f"Leeftijd eq '{selected.age.code}'",
        f"BurgerlijkeStaat eq '{selected.marital_status.code}'",
        "Perioden ge '2020JJ00'",
        "startswith(RegioS, 'GM')",
    ]
    selected_fields = [
        "Geslacht",
        "Leeftijd",
        "BurgerlijkeStaat",
        "RegioS",
        "Perioden",
        selected.population_on_january_1.code,
        selected.average_population.code,
    ]
    return {"$filter": " and ".join(filters), "$select": ",".join(selected_fields)}


def validate_population_records(
    records: list[dict[str, Any]],
    selected: SelectedDimensions,
    period_codes: list[str],
    municipal_regions: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Valideer gemeenterecords zonder velden te hernoemen of transformeren."""
    if not records:
        raise DataContractError("Population extraction returned no records.")
    measure_fields = {
        selected.population_on_january_1.code,
        selected.average_population.code,
    }
    unique_combinations: set[tuple[str, str]] = set()
    for record in records:
        validate_population_record(record, measure_fields)
        if record["Geslacht"] != selected.gender.code:
            raise DataContractError("Population record has an unexpected gender code.")
        if record["Leeftijd"] != selected.age.code:
            raise DataContractError("Population record has an unexpected age code.")
        if record["BurgerlijkeStaat"] != selected.marital_status.code:
            raise DataContractError(
                "Population record has an unexpected marital status code."
            )
        region_code = (
            record["RegioS"].strip() if isinstance(record["RegioS"], str) else ""
        )
        if region_code not in municipal_regions:
            raise DataContractError(
                f"Population record has an invalid municipal code {region_code}."
            )
        if record["Perioden"] not in period_codes:
            raise DataContractError("Population record has an invalid period code.")
        combination = (region_code, record["Perioden"])
        if combination in unique_combinations:
            raise DataContractError(
                "Population extraction contains a duplicate "
                "municipality-period combination."
            )
        unique_combinations.add(combination)
    return records


def _find_by_title(records: list[dict[str, Any]], title: str) -> SelectedDimension:
    """Vind precies één CBS-record op titel en valideer een bruikbare sleutel."""
    normalized_title = _normalize_title(title)
    matches = [
        record
        for record in records
        if isinstance(record.get("Title"), str)
        and _normalize_title(record["Title"]) == normalized_title
    ]
    if len(matches) != 1:
        raise DataContractError(f"Expected exactly one CBS dimension title: {title}.")
    key = matches[0].get("Key")
    actual_title = matches[0].get("Title")
    if not isinstance(key, str) or not key.strip() or not isinstance(actual_title, str):
        raise DataContractError(
            f"CBS dimension title {title} does not have a valid key."
        )
    return SelectedDimension(code=key.strip(), title=actual_title.strip())


def _dataset_title(table_info_records: list[dict[str, Any]]) -> str:
    """Lees de titel uit de gevalideerde TableInfos-collectie."""
    if len(table_info_records) != 1:
        raise DataContractError("TableInfos must contain exactly one dataset record.")
    title = table_info_records[0].get("Title")
    if not isinstance(title, str) or not title.strip():
        raise DataContractError("TableInfos does not contain a dataset title.")
    return title.strip()


def _raw_collection_payload(result: CollectionResult) -> dict[str, Any]:
    """Behoud één response ongewijzigd; bundel paginering zonder recordmutaties."""
    if result.page_count == 1:
        return result.pages[0]
    return {"value": result.records}


def _write_raw_files(
    output_directory: Path,
    table_info: dict[str, Any],
    dimension_results: Mapping[str, CollectionResult],
    population_result: CollectionResult,
    quality_report: dict[str, Any],
) -> dict[str, str]:
    """Schrijf alle voorgeschreven raw databestanden atomair."""
    files = {"table_info": TABLE_INFO_FILE}
    write_json_atomically(table_info, output_directory / TABLE_INFO_FILE)
    for name, result in dimension_results.items():
        filename = DIMENSION_FILES[name]
        write_json_atomically(
            _raw_collection_payload(result), output_directory / filename
        )
        files[name] = filename
    write_json_atomically(
        _raw_collection_payload(population_result), output_directory / POPULATION_FILE
    )
    files["population_records"] = POPULATION_FILE
    write_json_atomically(quality_report, output_directory / QUALITY_REPORT_FILE)
    files["quality_report"] = QUALITY_REPORT_FILE
    return files


def _normalize_title(value: str) -> str:
    """Normaliseer CBS-titels voor exact bedoelde, spatie-ongevoelige vergelijking."""
    return " ".join(value.casefold().split())
