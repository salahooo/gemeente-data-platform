"""Database-free contract tests for the read-only FastAPI application."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from gemeente_data_platform.api import create_app


class FakeRepository:
    def ready(self):
        return True

    def years(self):
        return [
            {"year": 2025, "has_average_population": True},
            {"year": 2026, "has_average_population": False},
        ]

    def municipalities(self, search, active, page, page_size):
        items = [
            {
                "municipality_code": "GM0484",
                "municipality_name": "Alphen aan den Rijn",
                "first_observed_year": 2020,
                "last_observed_year": 2026,
                "active_in_latest_period": True,
            }
        ]
        return items, 1

    def municipality(self, code):
        if code != "GM0484":
            return None
        return {
            "municipality_code": code,
            "municipality_name": "Alphen aan den Rijn",
            "first_observed_year": 2020,
            "last_observed_year": 2026,
            "active_in_latest_period": True,
        }

    def population(self, code):
        return [
            {
                "year": 2020,
                "population_january_1": 100,
                "average_population": Decimal("100"),
                "previous_population_january_1": None,
                "population_change_absolute": None,
                "population_change_percent": None,
            },
            {
                "year": 2026,
                "population_january_1": 110,
                "average_population": None,
                "previous_population_january_1": 100,
                "population_change_absolute": 10,
                "population_change_percent": Decimal("10.0"),
            },
        ]

    def national_population(self):
        return [
            {
                "year": 2026,
                "municipality_count": 1,
                "population_january_1": 110,
                "average_population": None,
                "missing_average_population_count": 1,
            }
        ]

    def rankings(self, year, limit):
        return [
            {
                "rank": 1,
                "municipality_code": "GM0484",
                "municipality_name": "Alphen aan den Rijn",
                "population_january_1": 110,
            }
        ]

    def latest_lineage(self):
        return {
            "processed_run_id": "processed-public-safe",
            "pipeline_run_id": "pipeline-public-safe",
            "completed_at": datetime(2026, 9, 5, tzinfo=timezone.utc),
        }


def client(repository=None):
    return TestClient(create_app(repository=repository or FakeRepository()))


def test_health_and_request_id_are_database_free():
    response = client().get("/health", headers={"X-Request-ID": "test-correlation"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-correlation"


def test_readiness_years_municipalities_and_pagination_contract():
    with client() as api:
        assert api.get("/ready").status_code == 200
        assert api.get("/api/v1/years").json()[1] == {
            "year": 2026,
            "has_average_population": False,
        }
        result = api.get(
            "/api/v1/municipalities",
            params={
                "search": "Alphen",
                "active_in_latest_period": "true",
                "page": 1,
                "page_size": 1,
            },
        )
    assert result.status_code == 200
    assert result.json()["total"] == 1
    assert result.json()["items"][0]["municipality_code"] == "GM0484"


def test_detail_series_national_ranking_and_null_semantics():
    with client() as api:
        assert api.get("/api/v1/municipalities/GM0484").status_code == 200
        series = api.get("/api/v1/municipalities/gm0484/population").json()
        national = api.get("/api/v1/national/population").json()
        ranking = api.get(
            "/api/v1/rankings/population", params={"year": 2026, "limit": 1}
        ).json()
        lineage = api.get("/api/v1/lineage/latest").json()
    assert series["observations"][0]["population_change_absolute"] is None
    assert series["observations"][1]["average_population"] is None
    assert national[0]["average_population"] is None
    assert ranking[0]["rank"] == 1
    assert lineage == {
        "processed_run_id": "processed-public-safe",
        "pipeline_run_id": "pipeline-public-safe",
        "completed_at": "2026-09-05T00:00:00Z",
    }


def test_not_found_and_validation_errors():
    with client() as api:
        assert api.get("/api/v1/municipalities/GM0000").status_code == 404
        assert (
            api.get("/api/v1/municipalities", params={"page_size": 101}).status_code
            == 422
        )
        assert api.get("/api/v1/rankings/population").status_code == 422


def test_database_error_is_safe_503_without_credentials():
    class BrokenRepository(FakeRepository):
        def years(self):
            raise OperationalError(
                "SELECT", {}, Exception("postgresql://user:secret@host")
            )

    with client(BrokenRepository()) as api:
        response = api.get("/api/v1/years", headers={"X-Request-ID": "safe-id"})
    assert response.status_code == 503
    assert response.json() == {"error": "database_unavailable", "request_id": "safe-id"}
    assert "secret" not in response.text
