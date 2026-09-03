"""Tests voor het lokaal opslaan van CBS-metadata."""

import json
from pathlib import Path

from gemeente_data_platform.fetch_metadata import save_json


def test_save_json_writes_readable_utf8_file(tmp_path: Path) -> None:
    """Metadata wordt met inspringing en Nederlandse tekens opgeslagen."""
    output_path = tmp_path / "raw" / "table_info.json"

    result = save_json({"Titel": "Gemeenten en bevolking"}, output_path)

    assert result == output_path
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "Titel": "Gemeenten en bevolking"
    }
    assert '  "Titel": "Gemeenten en bevolking"' in output_path.read_text(
        encoding="utf-8"
    )
