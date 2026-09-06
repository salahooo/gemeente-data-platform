"""Reproducible extraction and transactional loading of CBS 70072ned only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from gemeente_data_platform.cbs_client import CbsClient
from gemeente_data_platform.processed_storage import PROCESSED_ROOT, RAW_RUN_ROOT

DATASET = "70072ned"
GROUPS = {
    "0-14": ("k_0Tot15Jaar_4",),
    "15-24": ("k_15Tot25Jaar_5",),
    "25-44": ("k_25Tot45Jaar_6",),
    "45-64": ("k_45Tot65Jaar_7",),
    "65+": ("k_65Tot80Jaar_8", "k_80JaarOfOuder_9"),
}
COLUMNS = ("RegioS", "Perioden", "TotaleBevolking_1") + tuple(
    field for fields in GROUPS.values() for field in fields
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Population must be numeric or null.")
    if not 0 <= value <= 100_000_000 or int(value) != value:
        raise ValueError("Invalid population value.")
    return int(value)


def transform(records: list[dict], years: list[int]) -> list[dict]:
    if (
        not years
        or len(set(years)) != len(years)
        or any(not 1995 <= year <= datetime.now(UTC).year for year in years)
    ):
        raise ValueError("Invalid reporting years.")
    rows = []
    seen = set()
    for record in records:
        if not set(COLUMNS) <= record.keys():
            raise ValueError("Expected CBS columns are missing.")
        code = str(record["RegioS"]).strip()
        period = str(record["Perioden"]).strip()
        if not re.fullmatch(r"GM\d{4}|NL01", code):
            raise ValueError("Invalid region code.")
        if not re.fullmatch(r"\d{4}JJ00", period):
            raise ValueError("Invalid annual period.")
        year = int(period[:4])
        if year not in years or (code, year) in seen:
            raise ValueError("Duplicate or unexpected region/year.")
        seen.add((code, year))
        total = count(record["TotaleBevolking_1"])
        values = [count(record[field]) for field in COLUMNS[3:]]
        if all(value is not None for value in values) and total is not None:
            if sum(values) != total:
                raise ValueError("Age groups do not reconcile to source total.")
        for category, fields in GROUPS.items():
            parts = [count(record[field]) for field in fields]
            population = None if None in parts else sum(parts)
            if population is not None and total is not None and population > total:
                raise ValueError("Category exceeds total.")
            rows.append(
                dict(
                    region_code=code,
                    municipality_code=None if code == "NL01" else code,
                    year=year,
                    category=category,
                    population=population,
                    total=total,
                )
            )
    for year in years:
        regions = {code for code, row_year in seen if row_year == year}
        if "NL01" not in regions or not 251 <= len(regions) <= 1001:
            raise ValueError("Incomplete or implausible annual snapshot.")
    return sorted(
        rows, key=lambda row: (row["year"], row["region_code"], row["category"])
    )


def extract(years: list[int]) -> Path:
    client = CbsClient(
        "https://opendata.cbs.nl/ODataApi/OData", DATASET, 30, max_pages=40
    )
    properties = client.get_collection("DataProperties").records
    if not set(COLUMNS) <= {p.get("Key") for p in properties}:
        raise ValueError("CBS metadata schema changed.")
    records = []
    for year in years:
        if not 1995 <= year <= datetime.now(UTC).year:
            raise ValueError("Invalid year.")
        result = client.get_collection(
            "TypedDataSet",
            params={
                "$filter": f"Perioden eq '{year}JJ00' and "
                "(startswith(RegioS,'GM') or startswith(RegioS,'NL'))",
                "$select": ",".join(COLUMNS),
            },
        )
        records.extend(result.records)
    rows = transform(records, years)
    checksum = digest(rows)
    run = checksum[:24]
    raw = RAW_RUN_ROOT / DATASET / run
    processed = PROCESSED_ROOT / DATASET / run
    raw.mkdir(parents=True, exist_ok=True)
    processed.mkdir(parents=True, exist_ok=True)
    for path, value in (
        (raw / "source.json", {"records": records, "properties": properties}),
        (
            processed / "profile.json",
            {"dataset": DATASET, "years": years, "checksum": checksum, "rows": rows},
        ),
    ):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        temporary.replace(path)
    return processed


def read_run(directory: Path) -> dict:
    path = directory / "profile.json"
    if path.stat().st_size > 50_000_000:
        raise ValueError("Profile snapshot is too large.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("dataset") != DATASET or digest(data["rows"]) != data["checksum"]:
        raise ValueError("Profile checksum or source mismatch.")
    # Reconstruct the source contract to validate even edited processed files.
    seen = set()
    by_region = {}
    for row in data["rows"]:
        key = (row["region_code"], row["year"], row["category"])
        if key in seen or row["category"] not in GROUPS:
            raise ValueError("Duplicate or invalid category.")
        seen.add(key)
        count(row["population"])
        count(row["total"])
        code = row["region_code"]
        if not re.fullmatch(r"GM\d{4}|NL01", code):
            raise ValueError("Invalid region.")
        if row["municipality_code"] != (None if code == "NL01" else code):
            raise ValueError("Invalid municipality join.")
        if row["year"] not in data["years"]:
            raise ValueError("Unexpected year.")
        by_region.setdefault((code, row["year"]), []).append(row)
    for (code, year), rows in by_region.items():
        if len(rows) != 5 or len({row["total"] for row in rows}) != 1:
            raise ValueError("Incomplete categories or inconsistent total.")
        total = rows[0]["total"]
        if total is not None and all(row["population"] is not None for row in rows):
            if sum(row["population"] for row in rows) != total:
                raise ValueError("Profile totals do not reconcile.")
    for year in data["years"]:
        if not 1995 <= year <= datetime.now(UTC).year:
            raise ValueError("Invalid year.")
        keys = [code for code, y in by_region if y == year]
        if "NL01" not in keys or not 251 <= len(keys) <= 1001:
            raise ValueError("Incomplete annual snapshot.")
    if not data["years"] or len(set(data["years"])) != len(data["years"]):
        raise ValueError("Invalid years.")
    return data


def load_profile(engine, directory: Path) -> str:
    data = read_run(directory)
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(70072)"))
        connection.execute(text("DELETE FROM ops.stage_age_profile"))
        statement = text(
            "INSERT INTO ops.stage_age_profile "
            "(region_code,municipality_code,year,category,population,total) "
            "VALUES (:region_code,:municipality_code,:year,"
            ":category,:population,:total)"
        )
        for offset in range(0, len(data["rows"]), 1000):
            connection.execute(statement, data["rows"][offset : offset + 1000])
        missing = connection.execute(
            text(
                "SELECT count(*) FROM ops.stage_age_profile a "
                "WHERE a.municipality_code "
                "IS NOT NULL AND NOT EXISTS (SELECT 1 FROM core.fact_population f "
                "JOIN core.dim_period p USING(period_code) "
                "WHERE f.municipality_code=a.municipality_code AND p.year=a.year)"
            )
        ).scalar_one()
        if missing:
            raise ValueError("Municipality/year references are unavailable.")
        existing = dict(
            connection.execute(
                text("SELECT year, checksum FROM ops.age_snapshot")
            ).all()
        )
        if all(existing.get(year) == data["checksum"] for year in data["years"]):
            return "skipped"
        for year in data["years"]:
            connection.execute(
                text("DELETE FROM core.fact_age_profile WHERE year=:year"),
                {"year": year},
            )
            connection.execute(
                text(
                    "INSERT INTO core.fact_age_profile "
                    "SELECT * FROM ops.stage_age_profile "
                    "WHERE year=:year"
                ),
                {"year": year},
            )
            connection.execute(
                text(
                    "INSERT INTO ops.age_snapshot "
                    "SELECT :year,:checksum,now(),count(*),"
                    "count(*) FILTER(WHERE population IS NULL) + "
                    "count(*) FILTER(WHERE total IS NULL) FROM ops.stage_age_profile "
                    "WHERE year=:year AND municipality_code IS NOT NULL "
                    "ON CONFLICT(year) DO UPDATE SET checksum=excluded.checksum, "
                    "completed_at=excluded.completed_at,record_count=excluded.record_count,"
                    "missing_values=excluded.missing_values"
                ),
                {"year": year, "checksum": data["checksum"]},
            )
    return "success"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract CBS age profiles; no DB writes"
    )
    parser.add_argument("--first-year", type=int, required=True)
    parser.add_argument("--last-year", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not 1995 <= args.first_year <= args.last_year <= datetime.now(UTC).year:
        parser.error("Invalid year interval")
    if args.dry_run:
        print("Dry run: CBS 70072ned -> validated local profile snapshot; no DB writes")
        return
    directory = extract(list(range(args.first_year, args.last_year + 1)))
    print(f"Validated profile run: {directory.name}")


if __name__ == "__main__":
    main()
