"""Herbruikbare reconciliatie tussen een processed manifest en PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from gemeente_data_platform.database_loader import ProcessedRun


class DatabaseValidationError(ValueError):
    """Database-inhoud of analytische views wijken af van processed data."""


def validate_database_snapshot(engine: Any, run: ProcessedRun) -> dict[str, Any]:
    """Vergelijk dynamisch alle manifesttabellen en jaarstatistieken met PostgreSQL."""
    expected_tables = run.manifest.get("tables", {})
    allowed_tables = {"dim_municipality", "dim_period", "fact_population"}
    if not isinstance(expected_tables, dict) or set(expected_tables) - allowed_tables:
        raise DatabaseValidationError("Processed manifest contains unsupported tables.")
    table_counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table, metadata in expected_tables.items():
            if not isinstance(metadata, dict) or not isinstance(
                metadata.get("rows"), int
            ):
                raise DatabaseValidationError(
                    f"Processed manifest lacks a row count for {table}."
                )
            actual = connection.execute(
                text(f"SELECT COUNT(*) FROM core.{table}")
            ).scalar_one()
            table_counts[table] = actual
            if actual != metadata["rows"]:
                raise DatabaseValidationError(
                    f"Database row count differs for {table}: "
                    f"{actual} != {metadata['rows']}."
                )

        view_rows = (
            connection.execute(
                text(
                    "SELECT year, municipality_count, population_january_1_sum, "
                    "missing_average_population_count "
                    "FROM mart.v_national_population_by_year"
                )
            )
            .mappings()
            .all()
        )
        actual_years = {str(row["year"]): dict(row) for row in view_rows}
        expected_years = run.quality.get("statistics_by_year", {})
        if not isinstance(expected_years, dict):
            raise DatabaseValidationError(
                "Processed quality report lacks yearly statistics."
            )
        if set(actual_years) != set(expected_years):
            raise DatabaseValidationError(
                "Mart national view has different years than processed quality."
            )
        for year, expected in expected_years.items():
            actual = actual_years[year]
            for key in (
                "active_municipality_count",
                "january_population_sum",
                "missing_average_population_count",
            ):
                expected_value = expected.get(key)
                view_key = {
                    "active_municipality_count": "municipality_count",
                    "january_population_sum": "population_january_1_sum",
                    "missing_average_population_count": (
                        "missing_average_population_count"
                    ),
                }[key]
                if actual[view_key] != expected_value:
                    raise DatabaseValidationError(
                        f"Mart reconciliation differs for {year} {key}."
                    )
        lineage = connection.execute(
            text(
                "SELECT status FROM ops.etl_run "
                "WHERE processed_run_id = :processed_run_id"
            ),
            {"processed_run_id": run.manifest["processed_run_id"]},
        ).scalar_one_or_none()
    if lineage != "success":
        raise DatabaseValidationError(
            "No successful ETL lineage exists for processed run."
        )
    return {
        "table_counts": table_counts,
        "years_reconciled": sorted(actual_years),
        "processed_run_id": run.manifest["processed_run_id"],
    }
