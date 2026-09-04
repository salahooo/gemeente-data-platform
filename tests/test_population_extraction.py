"""Offline tests voor dimensieontdekking, raw opslag en bevolkings-extractie."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gemeente_data_platform.cbs_client import CollectionResult
from gemeente_data_platform.config import Settings
from gemeente_data_platform.data_contracts import (
    DataContractError,
    Manifest,
    validate_manifest,
)
from gemeente_data_platform.population_extraction import (
    POPULATION_ENDPOINT,
    build_population_query,
    discover_municipal_regions,
    discover_period_codes,
    discover_selected_dimensions,
    extract_population,
    validate_population_records,
)
from gemeente_data_platform.quality import build_quality_report
from gemeente_data_platform.raw_storage import (
    sha256_file,
    verify_checksums,
    write_json_atomically,
)


@pytest.fixture
def dimensions() -> dict[str, list[dict[str, Any]]]:
    """Kleine CBS-dimensiefixtures met één totaal per relevante dimensie."""
    return {
        "data_properties": [
            {"Key": "BevolkingOp1Januari_1", "Title": "Bevolking op 1 januari"},
            {"Key": "GemiddeldeBevolking_2", "Title": "Gemiddelde bevolking "},
        ],
        "gender": [
            {"Key": "T001038", "Title": "Totaal mannen en vrouwen"},
            {"Key": "3000   ", "Title": "Mannen"},
        ],
        "age": [{"Key": "10000", "Title": "Totaal"}],
        "marital_status": [{"Key": "T001019", "Title": "Totaal burgerlijke staat"}],
        "regions": [
            {"Key": "GM0001", "Title": "Voorbeeldgemeente"},
            {"Key": "GM0002", "Title": "Tweede gemeente"},
            {"Key": "PV20  ", "Title": "Voorbeeldprovincie"},
            {"Key": "NL01  ", "Title": "Nederland"},
        ],
        "periods": [
            {"Key": "2019JJ00", "Title": "2019"},
            {"Key": "2020JJ00", "Title": "2020"},
            {"Key": "2021JJ00", "Title": "2021"},
        ],
    }


@pytest.fixture
def population_records() -> list[dict[str, Any]]:
    """Ongetransformeerde fixture-records voor twee gemeenten en twee jaren."""
    return [
        {
            "Geslacht": "T001038",
            "Leeftijd": "10000",
            "BurgerlijkeStaat": "T001019",
            "RegioS": "GM0001",
            "Perioden": "2020JJ00",
            "BevolkingOp1Januari_1": 100,
            "GemiddeldeBevolking_2": 101.5,
        },
        {
            "Geslacht": "T001038",
            "Leeftijd": "10000",
            "BurgerlijkeStaat": "T001019",
            "RegioS": "GM0001",
            "Perioden": "2021JJ00",
            "BevolkingOp1Januari_1": 102,
            "GemiddeldeBevolking_2": None,
        },
        {
            "Geslacht": "T001038",
            "Leeftijd": "10000",
            "BurgerlijkeStaat": "T001019",
            "RegioS": "GM0002",
            "Perioden": "2020JJ00",
            "BevolkingOp1Januari_1": 200,
            "GemiddeldeBevolking_2": 200.5,
        },
        {
            "Geslacht": "T001038",
            "Leeftijd": "10000",
            "BurgerlijkeStaat": "T001019",
            "RegioS": "GM0002",
            "Perioden": "2021JJ00",
            "BevolkingOp1Januari_1": 201,
            "GemiddeldeBevolking_2": 201.5,
        },
    ]


class StubCbsClient:
    """CBS-clientstub voor een volledige extractierun zonder netwerk."""

    def __init__(
        self,
        dimensions: dict[str, list[dict[str, Any]]],
        population_records: list[dict[str, Any]],
    ) -> None:
        self.dimensions = dimensions
        self.population_records = population_records
        self.population_params: dict[str, str] | None = None

    def get_table_info(self) -> dict[str, Any]:
        """Geef één TableInfos-record terug."""
        return {"value": [{"Title": "Voorbeeld bevolkingstabel"}]}

    def get_collection(
        self, endpoint: str, params: dict[str, str] | None = None
    ) -> CollectionResult:
        """Geef de gevraagde kleine collectiefixture terug."""
        if endpoint == POPULATION_ENDPOINT:
            self.population_params = params
            payload = {"value": self.population_records}
        else:
            payload = {"value": self.dimensions[_dimension_name(endpoint)]}
        return CollectionResult(pages=[payload], records=payload["value"])


def test_discovers_validated_total_codes_and_measure_fields(
    dimensions: dict[str, list[dict[str, Any]]],
) -> None:
    """Totaalcodes worden uit dimensietitels ontdekt in plaats van verzonnen."""
    selected = discover_selected_dimensions(dimensions)

    assert selected.gender.code == "T001038"
    assert selected.age.code == "10000"
    assert selected.marital_status.code == "T001019"
    assert selected.population_on_january_1.code == "BevolkingOp1Januari_1"
    assert selected.average_population.code == "GemiddeldeBevolking_2"


def test_municipal_discovery_excludes_non_municipal_regions(
    dimensions: dict[str, list[dict[str, Any]]],
) -> None:
    """Alleen officiële GM-codes worden als gemeenten behandeld."""
    municipalities = discover_municipal_regions(dimensions["regions"])

    assert set(municipalities) == {"GM0001", "GM0002"}


def test_period_filter_selects_annual_codes_from_2020(
    dimensions: dict[str, list[dict[str, Any]]],
) -> None:
    """Alleen geldige jaarlijkse periodecodes vanaf 2020 worden geselecteerd."""
    assert discover_period_codes(dimensions["periods"]) == ["2020JJ00", "2021JJ00"]


def test_population_query_uses_discovered_codes(
    dimensions: dict[str, list[dict[str, Any]]],
) -> None:
    """De server-side-filter gebruikt uitsluitend gevalideerde dimensiecodes."""
    query = build_population_query(discover_selected_dimensions(dimensions))

    assert "Geslacht eq 'T001038'" in query["$filter"]
    assert "Perioden ge '2020JJ00'" in query["$filter"]
    assert "startswith(RegioS, 'GM')" in query["$filter"]
    assert "BevolkingOp1Januari_1" in query["$select"]


def test_population_validation_rejects_duplicate_municipality_period(
    dimensions: dict[str, list[dict[str, Any]]],
    population_records: list[dict[str, Any]],
) -> None:
    """Een gemeente-periodecombinatie mag binnen één extract niet dubbel zijn."""
    selected = discover_selected_dimensions(dimensions)
    duplicated = [*population_records, population_records[0].copy()]

    with pytest.raises(DataContractError, match="duplicate"):
        validate_population_records(
            duplicated,
            selected,
            discover_period_codes(dimensions["periods"]),
            discover_municipal_regions(dimensions["regions"]),
        )


def test_atomic_json_write_and_checksum(tmp_path: Path) -> None:
    """JSON wordt atomair geschreven en de checksum is opnieuw te bevestigen."""
    output_path = tmp_path / "raw" / "records.json"

    write_json_atomically({"Titel": "Gemeenten"}, output_path)

    checksum = sha256_file(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"Titel": "Gemeenten"}
    assert not list(output_path.parent.glob("*.tmp"))
    assert verify_checksums(output_path.parent, {output_path.name: checksum})


def test_manifest_validation_rejects_missing_required_fields() -> None:
    """Een incompleet manifest breekt het expliciete manifestcontract."""
    with pytest.raises(DataContractError, match="missing required fields"):
        validate_manifest({})


def test_manifest_model_accepts_valid_checksum() -> None:
    """Een volledig manifest met geldige checksum voldoet aan het contract."""
    manifest = Manifest(
        schema_version="1.0",
        dataset_code="03759ned",
        dataset_title="Voorbeeld",
        retrieved_at_utc="2026-09-04T00:00:00Z",
        base_url="https://example.test/OData",
        endpoints={"population": "TypedDataSet"},
        query_parameters={"population": {}},
        selected_dimensions={},
        selected_periods=["2020JJ00"],
        api_page_count=1,
        record_count=1,
        files={"population": "population_records.json"},
        checksums_sha256={"population_records.json": "a" * 64},
        validation_status={"checksums_reverified": True},
        quality={"period_statistics": {}},
    )

    assert manifest.as_dict()["dataset_code"] == "03759ned"


def test_full_extract_run_writes_manifest_and_unmodified_records(
    tmp_path: Path,
    dimensions: dict[str, list[dict[str, Any]]],
    population_records: list[dict[str, Any]],
) -> None:
    """De volledige run schrijft alle raw bestanden met gevalideerde metadata."""
    client = StubCbsClient(dimensions, population_records)
    app_settings = Settings()

    summary = extract_population(
        client,  # type: ignore[arg-type]
        app_settings,
        raw_root=tmp_path / "raw",
        run_id="20260904T120000000000Z",
    )

    expected_files = {
        "table_info.json",
        "data_properties.json",
        "gender.json",
        "age.json",
        "marital_status.json",
        "regions.json",
        "periods.json",
        "population_records.json",
        "quality_report.json",
        "manifest.json",
    }
    assert {path.name for path in summary.output_directory.iterdir()} == expected_files
    assert summary.municipal_code_count == 2
    assert summary.record_count == 4
    assert summary.active_observation_count == 4
    assert client.population_params is not None
    assert "startswith(RegioS, 'GM')" in client.population_params["$filter"]

    stored_records = json.loads(
        (summary.output_directory / "population_records.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (summary.output_directory / "manifest.json").read_text(encoding="utf-8")
    )
    quality_report = json.loads(
        (summary.output_directory / "quality_report.json").read_text(encoding="utf-8")
    )
    assert stored_records["value"] == population_records
    assert manifest["validation_status"]["checksums_reverified"] is True
    assert manifest["schema_version"] == "2.0"
    assert (
        manifest["quality"]["period_statistics"]["2020JJ00"][
            "active_municipality_count"
        ]
        == 2
    )
    assert manifest["quality"] == quality_report
    assert "quality_report.json" in manifest["checksums_sha256"]
    assert verify_checksums(summary.output_directory, manifest["checksums_sha256"])


def test_historical_municipal_code_without_population_is_not_active(
    population_records: list[dict[str, Any]],
) -> None:
    """Een GM-code met CBS-null telt niet als actieve gemeentewaarneming."""
    historical_record = population_records[1].copy()
    historical_record["Perioden"] = "2020JJ00"
    historical_record["RegioS"] = "GM0999"
    historical_record["BevolkingOp1Januari_1"] = None
    records = [population_records[0].copy(), historical_record]

    report = build_quality_report(records, ["2020JJ00"])

    assert report["period_statistics"]["2020JJ00"]["active_municipality_count"] == 1


def test_quality_report_keeps_null_out_of_january_sum(
    population_records: list[dict[str, Any]],
) -> None:
    """Een CBS-null is geen nul en wordt niet in de populatiesom opgenomen."""
    records = [population_records[0].copy(), population_records[1].copy()]
    records[1]["Perioden"] = "2020JJ00"
    records[1]["RegioS"] = "GM0003"
    records[1]["BevolkingOp1Januari_1"] = None

    report = build_quality_report(records, ["2020JJ00"])
    statistics = report["period_statistics"]["2020JJ00"]

    assert statistics["active_municipality_count"] == 1
    assert statistics["missing_january_population_count"] == 1
    assert statistics["january_population_sum"] == 100


def test_quality_report_warns_when_average_population_is_fully_missing(
    population_records: list[dict[str, Any]],
) -> None:
    """Volledig ontbrekende gemiddelde bevolking blijft een zichtbare waarschuwing."""
    records = [population_records[0].copy(), population_records[2].copy()]
    for record in records:
        record["GemiddeldeBevolking_2"] = None

    report = build_quality_report(records, ["2020JJ00"])

    assert (
        report["period_statistics"]["2020JJ00"]["available_average_population_count"]
        == 0
    )
    assert report["warnings"]


def test_quality_report_rejects_period_with_only_missing_january_values(
    population_records: list[dict[str, Any]],
) -> None:
    """Een periode zonder actieve waarneming is een inhoudelijke fout."""
    record = population_records[0].copy()
    record["BevolkingOp1Januari_1"] = None

    with pytest.raises(DataContractError, match="All January population values"):
        build_quality_report([record], ["2020JJ00"])


def _dimension_name(endpoint: str) -> str:
    """Vertaal endpointnamen uit de clientcall naar fixture-keys."""
    return {
        "DataProperties": "data_properties",
        "Geslacht": "gender",
        "Leeftijd": "age",
        "BurgerlijkeStaat": "marital_status",
        "RegioS": "regions",
        "Perioden": "periods",
    }[endpoint]
