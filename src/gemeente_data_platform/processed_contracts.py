"""Contracten en validaties voor de analyseklare processed tabellen."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


class ProcessedContractError(ValueError):
    """Een processed tabel, manifest of reconciliatie voldoet niet."""


MUNICIPALITY_COLUMNS = [
    "municipality_code",
    "municipality_name",
    "first_observed_year",
    "last_observed_year",
    "is_active_latest_period",
]
PERIOD_COLUMNS = [
    "period_code",
    "year",
    "period_label",
    "has_january_population",
    "has_average_population",
]
FACT_COLUMNS = [
    "municipality_code",
    "period_code",
    "population_january_1",
    "average_population",
]
GM_CODE_PATTERN = re.compile(r"GM\d{4}")
PERIOD_CODE_PATTERN = re.compile(r"\d{4}JJ00")


def validate_processed_tables(
    dim_municipality: pd.DataFrame,
    dim_period: pd.DataFrame,
    fact_population: pd.DataFrame,
) -> None:
    """Valideer schema, sleutels, waarden en referentiële integriteit."""
    _require_columns(dim_municipality, MUNICIPALITY_COLUMNS, "dim_municipality")
    _require_columns(dim_period, PERIOD_COLUMNS, "dim_period")
    _require_columns(fact_population, FACT_COLUMNS, "fact_population")
    if dim_municipality["municipality_code"].duplicated().any():
        raise ProcessedContractError(
            "dim_municipality has duplicate municipality codes."
        )
    if dim_period["period_code"].duplicated().any():
        raise ProcessedContractError("dim_period has duplicate period codes.")
    if fact_population.duplicated(["municipality_code", "period_code"]).any():
        raise ProcessedContractError("fact_population has duplicate composite keys.")
    if (
        not dim_municipality["municipality_code"]
        .map(
            lambda code: (
                isinstance(code, str) and GM_CODE_PATTERN.fullmatch(code) is not None
            )
        )
        .all()
    ):
        raise ProcessedContractError(
            "dim_municipality contains an invalid municipality code."
        )
    if (
        not dim_period["period_code"]
        .map(
            lambda code: (
                isinstance(code, str)
                and PERIOD_CODE_PATTERN.fullmatch(code) is not None
            )
        )
        .all()
    ):
        raise ProcessedContractError("dim_period contains an invalid period code.")
    if (
        dim_municipality["municipality_name"].isna().any()
        or (dim_municipality["municipality_name"].astype(str).str.strip() == "").any()
    ):
        raise ProcessedContractError(
            "dim_municipality contains an empty municipality name."
        )
    if (
        dim_municipality["first_observed_year"] > dim_municipality["last_observed_year"]
    ).any():
        raise ProcessedContractError("A municipality has an invalid observation range.")
    if (fact_population["population_january_1"] < 0).any():
        raise ProcessedContractError(
            "fact_population contains a negative January population."
        )
    if not pd.api.types.is_integer_dtype(fact_population["population_january_1"]):
        raise ProcessedContractError("population_january_1 must use an integer dtype.")
    if not pd.api.types.is_numeric_dtype(fact_population["average_population"]):
        raise ProcessedContractError("average_population must use a numeric dtype.")
    if not pd.api.types.is_integer_dtype(dim_period["year"]):
        raise ProcessedContractError("dim_period.year must use an integer dtype.")
    if not set(fact_population["municipality_code"]).issubset(
        set(dim_municipality["municipality_code"])
    ):
        raise ProcessedContractError(
            "fact_population has an unknown municipality code."
        )
    if not set(fact_population["period_code"]).issubset(set(dim_period["period_code"])):
        raise ProcessedContractError("fact_population has an unknown period code.")
    latest_period = dim_period.sort_values("year").iloc[-1]["period_code"]
    actual_latest = set(
        fact_population.loc[
            fact_population["period_code"] == latest_period, "municipality_code"
        ]
    )
    flagged_latest = set(
        dim_municipality.loc[
            dim_municipality["is_active_latest_period"], "municipality_code"
        ]
    )
    if actual_latest != flagged_latest:
        raise ProcessedContractError(
            "The latest-active municipality flag is inconsistent."
        )


def reconcile_with_raw_quality(
    fact_population: pd.DataFrame,
    raw_quality: dict[str, Any],
    active_raw_records: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    """Vergelijk actieve records en januari-totalen per periode met raw kwaliteit."""
    reconciliation: dict[str, dict[str, int]] = {}
    for period_code, statistics in raw_quality["period_statistics"].items():
        fact_rows = fact_population.loc[fact_population["period_code"] == period_code]
        expected_count = statistics["active_municipality_count"]
        expected_sum = statistics["january_population_sum"]
        if len(fact_rows) != expected_count:
            raise ProcessedContractError(
                f"Raw reconciliation count failed for {period_code}."
            )
        actual_sum = int(fact_rows["population_january_1"].sum())
        if actual_sum != expected_sum:
            raise ProcessedContractError(
                f"Raw reconciliation January population sum failed for {period_code}."
            )
        expected_missing_averages = sum(
            record.get("Perioden") == period_code
            and record.get("GemiddeldeBevolking_2") is None
            for record in active_raw_records
        )
        actual_missing_averages = int(fact_rows["average_population"].isna().sum())
        if actual_missing_averages != expected_missing_averages:
            raise ProcessedContractError(
                f"Raw reconciliation average population nulls failed for {period_code}."
            )
        reconciliation[period_code] = {
            "fact_record_count": len(fact_rows),
            "january_population_sum": actual_sum,
            "missing_average_population_count": actual_missing_averages,
        }
    return reconciliation


def _require_columns(dataframe: pd.DataFrame, expected: list[str], table: str) -> None:
    """Controleer kolomnamen en hun volgorde voor één processed tabel."""
    if list(dataframe.columns) != expected:
        raise ProcessedContractError(f"{table} does not match its expected schema.")
