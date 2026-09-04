"""Atomaire opslag en checksumcontrole voor de raw landing zone."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAW_ROOT = Path("data/raw/cbs")


def utc_run_id(now: datetime | None = None) -> str:
    """Maak een unieke, bestandssysteemveilige UTC-identificatie voor een run."""
    current_time = now or datetime.now(UTC)
    return current_time.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def create_run_directory(
    dataset_code: str, run_id: str | None = None, root: Path = RAW_ROOT
) -> Path:
    """Maak de unieke raw uitvoermap voor een datasetextractie."""
    directory = root / dataset_code / (run_id or utc_run_id())
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def write_json_atomically(data: Any, output_path: Path) -> Path:
    """Schrijf UTF-8 JSON atomair, zodat incomplete bestanden niet zichtbaar zijn."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path


def sha256_file(path: Path) -> str:
    """Bereken de SHA-256-checksum van één opgeslagen bestand."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(directory: Path, checksums: dict[str, str]) -> bool:
    """Bevestig dat alle opgeslagen bestanden overeenkomen met hun checksum."""
    return all(
        (directory / filename).is_file()
        and sha256_file(directory / filename) == expected_checksum
        for filename, expected_checksum in checksums.items()
    )
