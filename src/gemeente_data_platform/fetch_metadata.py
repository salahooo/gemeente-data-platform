"""Haal CBS-tabelmetadata op naar dezelfde raw landing zone als extractieruns."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from gemeente_data_platform.cbs_client import CbsClient
from gemeente_data_platform.config import settings
from gemeente_data_platform.raw_storage import (
    create_run_directory,
    write_json_atomically,
)

logger = logging.getLogger(__name__)


def save_json(data: Any, output_path: Path) -> Path:
    """Behoud de bestaande helpernaam met atomaire UTF-8 JSON-opslag."""
    return write_json_atomically(data, output_path)


def fetch_and_save_table_info(output_path: Path | None = None) -> Path:
    """Haal TableInfos op en schrijf het in een unieke raw runmap."""
    if output_path is None:
        output_path = (
            create_run_directory(settings.cbs_dataset_code) / "table_info.json"
        )
    client = CbsClient.from_settings(settings)
    return save_json(client.get_table_info(), output_path)


def main() -> None:
    """Voer de metadata-ophaling uit met compacte logging."""
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    output_path = fetch_and_save_table_info()
    logger.info("CBS-tabelmetadata opgeslagen | uitvoer=%s", output_path.as_posix())


if __name__ == "__main__":
    main()
