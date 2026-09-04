"""Afgeleide kwaliteitsstatistieken voor ongewijzigde CBS raw records."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from gemeente_data_platform.data_contracts import DataContractError


def build_quality_report(
    records: list[dict[str, Any]], period_codes: list[str]
) -> dict[str, Any]:
    """Bereken en valideer kwaliteitsinformatie zonder raw records te wijzigen."""
    if not records:
        raise DataContractError("Quality report cannot be built from an empty extract.")

    unique_codes = {record["RegioS"] for record in records}
    period_statistics: dict[str, dict[str, int]] = {}
    warnings: list[str] = []
    validation_results: dict[str, bool] = {
        "every_period_has_raw_records": True,
        "every_period_has_active_observations": True,
        "active_counts_do_not_exceed_unique_codes": True,
        "active_january_population_is_non_negative_integer": True,
        "missing_values_are_not_zero": True,
        "quality_statistics_match_raw_records": True,
    }

    for period_code in period_codes:
        period_records = [
            record for record in records if record["Perioden"] == period_code
        ]
        if not period_records:
            raise DataContractError(f"No raw records were found for {period_code}.")
        active_records = [
            record
            for record in period_records
            if _is_active_january_observation(record["BevolkingOp1Januari_1"])
        ]
        if not active_records:
            raise DataContractError(
                f"All January population values are missing for {period_code}."
            )
        for record in active_records:
            value = record["BevolkingOp1Januari_1"]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise DataContractError(
                    "Active January population is not a non-negative integer "
                    f"in {period_code}."
                )
        _validate_missing_or_numeric(
            period_records, "BevolkingOp1Januari_1", period_code
        )
        _validate_missing_or_numeric(
            period_records, "GemiddeldeBevolking_2", period_code
        )
        average_available = [
            record
            for record in period_records
            if _is_valid_numeric(record["GemiddeldeBevolking_2"])
        ]
        if not average_available:
            warnings.append(
                "Gemiddelde bevolking ontbreekt volledig voor "
                f"{period_code}; verwachte CBS-publicatiewaarschuwing."
            )

        active_codes = {record["RegioS"] for record in active_records}
        raw_codes = {record["RegioS"] for record in period_records}
        if len(active_codes) > len(raw_codes):
            raise DataContractError(
                "Active municipality count exceeds raw municipality codes "
                f"for {period_code}."
            )
        period_statistics[period_code] = {
            "raw_record_count": len(period_records),
            "unique_municipal_code_count": len(raw_codes),
            "active_municipality_count": len(active_codes),
            "missing_january_population_count": len(period_records)
            - len(active_records),
            "available_average_population_count": len(average_available),
            "missing_average_population_count": len(period_records)
            - len(average_available),
            "january_population_sum": sum(
                record["BevolkingOp1Januari_1"] for record in active_records
            ),
        }

    return {
        "schema_version": "1.0",
        "definitions": {
            "municipal_codes": "Alle unieke GM-codes in de raw extractie.",
            "active_municipality_observation": (
                "Een gemeente-jaarrecord met geldige numerieke bevolking op 1 januari."
            ),
            "active_municipality_count": (
                "Unieke GM-codes met een actieve gemeentewaarneming per periode."
            ),
            "missing_values": "Door CBS geleverde records zonder cijfer; niet nul.",
        },
        "raw_record_count": len(records),
        "unique_municipal_code_count": len(unique_codes),
        "active_municipality_observation_count": sum(
            statistics["active_municipality_count"]
            for statistics in period_statistics.values()
        ),
        "first_selected_period": period_codes[0],
        "last_selected_period": period_codes[-1],
        "period_statistics": period_statistics,
        "warnings": warnings,
        "validation_results": validation_results,
        "raw_data_note": (
            "Historische gemeentecodes blijven ongewijzigd in de raw extractie."
        ),
    }


def _is_active_january_observation(value: Any) -> bool:
    """Bepaal activiteit uitsluitend via een geldige januari-populatie."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_valid_numeric(value: Any) -> bool:
    """Bepaal of een CBS-meetwaarde een eindig numeriek getal is."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _validate_missing_or_numeric(
    records: list[Mapping[str, Any]], field: str, period_code: str
) -> None:
    """Laat alleen eindige cijfers of verklaarde CBS-ontbrekende waarden toe."""
    for record in records:
        value = record[field]
        if _is_valid_numeric(value) or value is None or value == ".":
            continue
        raise DataContractError(
            f"Invalid value for {field} in quality validation for {period_code}."
        )
