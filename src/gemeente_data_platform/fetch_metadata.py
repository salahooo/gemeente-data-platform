"""Haal CBS-tabelmetadata op en sla die lokaal op."""

import json
from pathlib import Path
from typing import Any

from gemeente_data_platform.cbs_client import CbsClient
from gemeente_data_platform.config import settings

DEFAULT_OUTPUT_PATH = Path("data/raw/03759ned_table_info.json")


def save_json(data: Any, output_path: Path) -> Path:
    """Sla JSON leesbaar op met UTF-8 en behoud Nederlandse tekens."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def fetch_and_save_table_info(output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Haal TableInfos op en schrijf de response naar het lokale raw-data-pad."""
    client = CbsClient.from_settings(settings)
    return save_json(client.get_table_info(), output_path)


def main() -> None:
    """Voer de metadata-ophaling uit."""
    output_path = fetch_and_save_table_info()
    print(f"CBS-tabelmetadata opgeslagen in {output_path}")


if __name__ == "__main__":
    main()
