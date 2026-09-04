"""Expliciete datacontracten voor CBS-collecties en raw extractieruns."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


class DataContractError(ValueError):
    """De ontvangen of te schrijven data voldoet niet aan het contract."""


@dataclass(frozen=True)
class SelectedDimension:
    """Een vanuit CBS-metadata ontdekte dimensiewaarde."""

    code: str
    title: str


@dataclass(frozen=True)
class SelectedDimensions:
    """De gevalideerde totalen en meetvelden voor één extractierun."""

    gender: SelectedDimension
    age: SelectedDimension
    marital_status: SelectedDimension
    population_on_january_1: SelectedDimension
    average_population: SelectedDimension

    def as_dict(self) -> dict[str, dict[str, str]]:
        """Geef selectie-informatie terug voor opname in het manifest."""
        return asdict(self)


@dataclass(frozen=True)
class Manifest:
    """Minimaal contract voor een reproduceerbare raw extractierun."""

    schema_version: str
    dataset_code: str
    dataset_title: str
    retrieved_at_utc: str
    base_url: str
    endpoints: dict[str, str]
    query_parameters: dict[str, dict[str, str]]
    selected_dimensions: dict[str, dict[str, str]]
    selected_periods: list[str]
    api_page_count: int
    record_count: int
    files: dict[str, str]
    checksums_sha256: dict[str, str]
    validation_status: dict[str, bool]
    quality: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Valideer en serialiseer het manifest voor JSON-opslag."""
        manifest = asdict(self)
        validate_manifest(manifest)
        return manifest


def validate_collection_response(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Valideer dat een OData-collectie een lijst van objecten bevat."""
    value = payload.get("value")
    if not isinstance(value, list):
        raise DataContractError(
            "CBS collection response must contain a list in 'value'."
        )
    if not all(isinstance(record, dict) for record in value):
        raise DataContractError("CBS collection response contains a non-object record.")
    return value


def validate_population_record(
    record: Mapping[str, Any], measure_fields: set[str]
) -> None:
    """Valideer de minimale velden van één ongetransformeerd bevolkingsrecord."""
    required_dimensions = {
        "Geslacht",
        "Leeftijd",
        "BurgerlijkeStaat",
        "RegioS",
        "Perioden",
    }
    required_fields = required_dimensions | measure_fields
    missing = sorted(field for field in required_fields if field not in record)
    if missing:
        raise DataContractError(
            f"Population record is missing required fields: {', '.join(missing)}."
        )
    for field in measure_fields:
        value = record[field]
        if isinstance(value, bool) or not (
            value is None or isinstance(value, (int, float)) or value == "."
        ):
            raise DataContractError(
                f"Population measure {field} is not numeric or a CBS missing value."
            )


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    """Valideer de verplichte manifestvelden en SHA-256-checksums."""
    required_fields = {
        "schema_version",
        "dataset_code",
        "dataset_title",
        "retrieved_at_utc",
        "base_url",
        "endpoints",
        "query_parameters",
        "selected_dimensions",
        "selected_periods",
        "api_page_count",
        "record_count",
        "files",
        "checksums_sha256",
        "validation_status",
        "quality",
    }
    missing = sorted(required_fields - set(manifest))
    if missing:
        raise DataContractError(
            f"Manifest is missing required fields: {', '.join(missing)}."
        )
    checksums = manifest["checksums_sha256"]
    if not isinstance(checksums, dict) or not checksums:
        raise DataContractError("Manifest must contain checksums for saved data files.")
    if not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in checksums.values()
    ):
        raise DataContractError("Manifest contains an invalid SHA-256 checksum.")
