"""Bouw processed bevolkingsdimensies en feiten uit gevalideerde raw records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from gemeente_data_platform.processed_contracts import (
    FACT_COLUMNS,
    MUNICIPALITY_COLUMNS,
    PERIOD_COLUMNS,
    ProcessedContractError,
    reconcile_with_raw_quality,
    validate_processed_tables,
)


@dataclass(frozen=True)
class ProcessedTables:
    """De drie analyseklare tabellen en afgeleide kwaliteitsinformatie."""

    dim_municipality: pd.DataFrame
    dim_period: pd.DataFrame
    fact_population: pd.DataFrame
    quality_report: dict[str, Any]


def build_processed_tables(
    raw_records: list[dict[str, Any]],
    regions: list[dict[str, Any]],
    periods: list[dict[str, Any]],
    raw_quality: dict[str, Any],
) -> ProcessedTables:
    """Selecteer actieve waarnemingen en bouw de processed stertabellen."""
    selected_periods = list(raw_quality["period_statistics"])
    region_names = {
        str(region["Key"]).strip(): str(region["Title"]).strip()
        for region in regions
        if isinstance(region.get("Key"), str) and isinstance(region.get("Title"), str)
    }
    period_labels = {
        str(period["Key"]): str(period["Title"])
        for period in periods
        if isinstance(period.get("Key"), str) and isinstance(period.get("Title"), str)
    }
    active_records = [
        record
        for record in raw_records
        if record.get("Perioden") in selected_periods
        and isinstance(record.get("BevolkingOp1Januari_1"), int)
        and not isinstance(record.get("BevolkingOp1Januari_1"), bool)
        and record["BevolkingOp1Januari_1"] >= 0
    ]
    if not active_records:
        raise ProcessedContractError(
            "No active municipality observations are available."
        )
    fact_population = pd.DataFrame(
        [
            {
                "municipality_code": str(record["RegioS"]).strip(),
                "period_code": str(record["Perioden"]),
                "population_january_1": record["BevolkingOp1Januari_1"],
                "average_population": record.get("GemiddeldeBevolking_2"),
            }
            for record in active_records
        ],
        columns=FACT_COLUMNS,
    )
    fact_population = fact_population.astype(
        {
            "municipality_code": "string",
            "period_code": "string",
            "population_january_1": "int64",
            "average_population": "Float64",
        }
    ).sort_values(["municipality_code", "period_code"], ignore_index=True)
    dim_period = _build_dim_period(fact_population, selected_periods, period_labels)
    dim_municipality = _build_dim_municipality(
        fact_population, dim_period, region_names
    )
    validate_processed_tables(dim_municipality, dim_period, fact_population)
    reconciliation = reconcile_with_raw_quality(
        fact_population, raw_quality, active_records
    )
    quality_report = _build_processed_quality(
        dim_municipality,
        dim_period,
        fact_population,
        reconciliation,
        raw_quality.get("warnings", []),
    )
    return ProcessedTables(
        dim_municipality=dim_municipality,
        dim_period=dim_period,
        fact_population=fact_population,
        quality_report=quality_report,
    )


def _build_dim_period(
    fact_population: pd.DataFrame,
    selected_periods: list[str],
    period_labels: dict[str, str],
) -> pd.DataFrame:
    """Bouw één rij per geselecteerde CBS-jaarperiode."""
    rows = []
    for code in selected_periods:
        if code not in period_labels:
            raise ProcessedContractError(f"Raw period dimension lacks {code}.")
        records = fact_population.loc[fact_population["period_code"] == code]
        rows.append(
            {
                "period_code": code,
                "year": int(code[:4]),
                "period_label": period_labels[code],
                "has_january_population": not records.empty,
                "has_average_population": records["average_population"].notna().any(),
            }
        )
    return (
        pd.DataFrame(rows, columns=PERIOD_COLUMNS)
        .astype(
            {
                "period_code": "string",
                "year": "int64",
                "period_label": "string",
                "has_january_population": "bool",
                "has_average_population": "bool",
            }
        )
        .sort_values("year", ignore_index=True)
    )


def _build_dim_municipality(
    fact_population: pd.DataFrame,
    dim_period: pd.DataFrame,
    region_names: dict[str, str],
) -> pd.DataFrame:
    """Bouw dimensierijen voor codes met minimaal één actieve waarneming."""
    years = dict(zip(dim_period["period_code"], dim_period["year"], strict=True))
    latest_period = dim_period.iloc[-1]["period_code"]
    rows = []
    for code, records in fact_population.groupby("municipality_code", sort=True):
        name = region_names.get(str(code))
        if not name:
            raise ProcessedContractError(
                f"Raw region dimension lacks a name for {code}."
            )
        observed_years = [years[period] for period in records["period_code"]]
        rows.append(
            {
                "municipality_code": code,
                "municipality_name": name,
                "first_observed_year": min(observed_years),
                "last_observed_year": max(observed_years),
                "is_active_latest_period": latest_period in set(records["period_code"]),
            }
        )
    return pd.DataFrame(rows, columns=MUNICIPALITY_COLUMNS).astype(
        {
            "municipality_code": "string",
            "municipality_name": "string",
            "first_observed_year": "int64",
            "last_observed_year": "int64",
            "is_active_latest_period": "bool",
        }
    )


def _build_processed_quality(
    dim_municipality: pd.DataFrame,
    dim_period: pd.DataFrame,
    fact_population: pd.DataFrame,
    reconciliation: dict[str, dict[str, int]],
    raw_warnings: object,
) -> dict[str, Any]:
    """Maak afgeleide kwaliteitsinformatie voor portfolio- en controledoeleinden."""
    first_year = int(dim_period.iloc[0]["year"])
    last_year = int(dim_period.iloc[-1]["year"])
    by_year: dict[str, dict[str, int]] = {}
    for period in dim_period.itertuples(index=False):
        records = fact_population.loc[
            fact_population["period_code"] == period.period_code
        ]
        by_year[str(period.year)] = {
            "active_municipality_count": len(records),
            "january_population_sum": int(records["population_january_1"].sum()),
            "missing_average_population_count": int(
                records["average_population"].isna().sum()
            ),
        }
    appearing = dim_municipality.loc[
        dim_municipality["first_observed_year"] > first_year, "municipality_code"
    ].tolist()
    disappearing = dim_municipality.loc[
        dim_municipality["last_observed_year"] < last_year, "municipality_code"
    ].tolist()
    warnings = (
        [warning for warning in raw_warnings if isinstance(warning, str)]
        if isinstance(raw_warnings, list)
        else []
    )
    warnings.extend(
        [
            "Verschijnen en verdwijnen zijn geen automatische oprichting of opheffing.",
            "Geografische harmonisatie valt buiten deze fase.",
        ]
    )
    return {
        "schema_version": "1.0",
        "definitions": {
            "appearing": (
                "Code wordt voor het eerst actief binnen het observatievenster."
            ),
            "disappearing": (
                "Code is niet actief in de laatste periode van het observatievenster."
            ),
        },
        "statistics_by_year": by_year,
        "appearing_municipality_codes": appearing,
        "disappearing_municipality_codes": disappearing,
        "raw_reconciliation": reconciliation,
        "warnings": warnings,
    }
