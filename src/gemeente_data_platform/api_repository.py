"""Parameterized read-only queries against explicitly approved mart views."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

REQUIRED_MART_VIEWS = (
    "v_municipality_catalog",
    "v_population_by_municipality_year",
    "v_municipality_year_over_year",
    "v_national_population_by_year",
)


class MartRepository:
    """Repository without mutations; all queries use fixed view names."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def ready(self) -> bool:
        with self._engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.views "
                    "WHERE table_schema = 'mart' AND table_name = ANY(:views)"
                ),
                {"views": list(REQUIRED_MART_VIEWS)},
            ).scalar_one()
        return count == len(REQUIRED_MART_VIEWS)

    def years(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT year, bool_or(has_average_population) AS has_average_population "
            "FROM mart.v_population_by_municipality_year GROUP BY year ORDER BY year"
        )

    def municipalities(
        self, search: str | None, active: bool | None, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        where: list[str] = []
        values: dict[str, Any] = {}
        if search:
            where.append(
                "(municipality_name ILIKE :search OR municipality_code ILIKE :search)"
            )
            values["search"] = f"%{search}%"
        if active is not None:
            where.append("is_active_latest_period = :active")
            values["active"] = active
        predicate = f" WHERE {' AND '.join(where)}" if where else ""
        with self._engine.connect() as connection:
            total = connection.execute(
                text("SELECT count(*) FROM mart.v_municipality_catalog" + predicate),
                values,
            ).scalar_one()
            values.update({"limit": page_size, "offset": (page - 1) * page_size})
            rows = (
                connection.execute(
                    text(
                        "SELECT municipality_code, municipality_name, first_observed_year, "
                        "last_observed_year, is_active_latest_period AS active_in_latest_period "
                        "FROM mart.v_municipality_catalog"
                        + predicate
                        + " ORDER BY municipality_name, municipality_code LIMIT :limit OFFSET :offset"
                    ),
                    values,
                )
                .mappings()
                .all()
            )
        return [dict(row) for row in rows], total

    def municipality(self, code: str) -> dict[str, Any] | None:
        rows = self._rows(
            "SELECT municipality_code, municipality_name, first_observed_year, "
            "last_observed_year, is_active_latest_period AS active_in_latest_period "
            "FROM mart.v_municipality_catalog WHERE municipality_code = :code",
            {"code": code},
        )
        return rows[0] if rows else None

    def population(self, code: str) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT p.year, p.population_january_1, p.average_population, "
            "y.previous_population_january_1, y.population_change_absolute, "
            "y.population_change_percent FROM mart.v_population_by_municipality_year p "
            "LEFT JOIN mart.v_municipality_year_over_year y "
            "ON y.municipality_code = p.municipality_code AND y.year = p.year "
            "WHERE p.municipality_code = :code ORDER BY p.year",
            {"code": code},
        )

    def national_population(self) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT year, municipality_count, population_january_1_sum AS population_january_1, "
            "average_population_sum AS average_population, missing_average_population_count "
            "FROM mart.v_national_population_by_year ORDER BY year"
        )

    def rankings(self, year: int, limit: int) -> list[dict[str, Any]]:
        return self._rows(
            "SELECT row_number() OVER (ORDER BY population_january_1 DESC, municipality_code) "
            "AS rank, municipality_code, municipality_name, population_january_1 "
            "FROM mart.v_population_by_municipality_year WHERE year = :year "
            "ORDER BY population_january_1 DESC, municipality_code LIMIT :limit",
            {"year": year, "limit": limit},
        )

    def latest_lineage(self) -> dict[str, Any] | None:
        rows = self._rows(
            "SELECT processed_run_id, pipeline_run_id, completed_at "
            "FROM mart.v_dataset_lineage"
        )
        return rows[0] if rows else None

    def age_profile(self, code: str, year: int) -> list[dict[str, Any]]:
        try:
            return self._rows(
                "SELECT category, population, share_percent, national_share_percent "
                "FROM mart.v_municipality_age_profile "
                "WHERE municipality_code=:code AND year=:year ORDER BY category LIMIT 5",
                {"code": code, "year": year},
            )
        except SQLAlchemyError:
            return []

    def data_quality(self) -> list[dict[str, Any]]:
        try:
            return self._rows(
                "SELECT dataset_code,dataset_name,source,first_year,last_year,"
                "completed_at,record_count,validation_status,missing_values,warning "
                "FROM mart.v_public_data_quality ORDER BY dataset_code LIMIT 2"
            )
        except SQLAlchemyError:
            return []

    def _rows(
        self, statement: str, values: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        with self._engine.connect() as connection:
            rows = connection.execute(text(statement), values or {}).mappings().all()
        return [dict(row) for row in rows]
