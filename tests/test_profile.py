"""Focused source validation and public API contracts, without network or database."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from gemeente_data_platform.api import create_app
from gemeente_data_platform.api_repository import MartRepository
from gemeente_data_platform.profile_pipeline import (
    COLUMNS,
    digest,
    read_run,
    transform,
)
from tests.test_api import FakeRepository


def source_records():
    return [
        dict(zip(COLUMNS, [code, "2026JJ00", 60, 10, 10, 10, 10, 10, 10]))
        for code in ["NL01  "] + [f"GM{i:04}" for i in range(8000, 8250)]
    ]


def profile_run(tmp_path, records=None):
    rows = transform(records or source_records(), [2026])
    (tmp_path / "profile.json").write_text(
        json.dumps(
            {
                "dataset": "70072ned",
                "years": [2026],
                "rows": rows,
                "checksum": digest(rows),
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_transform_reproducible_null_preserving_and_exact_categories(tmp_path):
    records = source_records()
    records[0][COLUMNS[-1]] = None
    rows = transform(records, [2026])
    assert len(rows) == 251 * 5
    assert {row["category"] for row in rows} == {
        "0-14",
        "15-24",
        "25-44",
        "45-64",
        "65+",
    }
    assert (
        next(
            row
            for row in rows
            if row["region_code"] == "NL01" and row["category"] == "65+"
        )["population"]
        is None
    )
    assert digest(rows) == digest(transform(list(reversed(records)), [2026]))
    assert read_run(profile_run(tmp_path, records))["rows"] == rows


@pytest.mark.parametrize(
    "change",
    ["duplicate", "negative", "missing-column", "region", "period", "total", "small"],
)
def test_invalid_source_never_becomes_a_snapshot(change):
    records = source_records()
    if change == "duplicate":
        records.append(records[0])
    elif change == "negative":
        records[0][COLUMNS[3]] = -1
    elif change == "missing-column":
        del records[0][COLUMNS[3]]
    elif change == "region":
        records[0]["RegioS"] = "BAD"
    elif change == "period":
        records[0]["Perioden"] = "2026MM01"
    elif change == "total":
        records[0]["TotaleBevolking_1"] = 10
    else:
        records = records[:2]
    with pytest.raises(ValueError):
        transform(records, [2026])


def test_checksum_and_duplicate_processed_keys_are_revalidated(tmp_path):
    profile_run(tmp_path)
    path = tmp_path / "profile.json"
    data = json.loads(path.read_text())
    data["rows"].append(data["rows"][0])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum"):
        read_run(tmp_path)
    data["checksum"] = digest(data["rows"])
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Duplicate"):
        read_run(tmp_path)


class ProfileRepository(FakeRepository):
    def age_profile(self, code, year):
        return (
            []
            if year == 2025
            else [
                {
                    "category": "65+",
                    "population": None,
                    "share_percent": None,
                    "national_share_percent": "20.5",
                    "internal": "must not escape",
                }
            ]
        )

    def data_quality(self):
        return [
            {
                "dataset_code": "70072ned",
                "dataset_name": "Leeftijdsopbouw",
                "source": "CBS Open Data",
                "first_year": 2026,
                "last_year": 2026,
                "completed_at": None,
                "record_count": 1250,
                "validation_status": "validated",
                "missing_values": 1,
                "warning": "Ontbrekende waarden zijn geen nul.",
                "internal": "must not escape",
            }
        ]


def test_optional_endpoints_are_bounded_typed_and_keep_health_independent():
    with TestClient(create_app(repository=ProfileRepository())) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        path = "/api/v1/municipalities/GM8000/profile"
        assert client.get(path, params={"year": 2025}).json()["categories"] == []
        response = client.get(path, params={"year": 2026})
        assert response.json()["categories"][0]["population"] is None
        assert "internal" not in response.text
        assert "internal" not in client.get("/api/v1/data-quality").text
        assert client.get(path, params={"year": 1000}).status_code == 422
        assert (
            client.get(
                path.replace("GM8000", "INVALID"), params={"year": 2026}
            ).status_code
            == 422
        )
        assert client.post(path, json={}).status_code == 405


def test_optional_repository_fails_closed_without_exposing_sql(monkeypatch):
    repo = MartRepository(None)

    def fail(*args, **kwargs):
        raise OperationalError("sensitive SQL", {}, Exception("private"))

    monkeypatch.setattr(repo, "_rows", fail)
    assert repo.age_profile("GM8000", 2026) == []
    assert repo.data_quality() == []
