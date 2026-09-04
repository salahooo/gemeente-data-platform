"""Tests voor de compacte en semantisch correcte extractie-uitvoer."""

import logging
from pathlib import Path

from gemeente_data_platform import extract_population as cli
from gemeente_data_platform.data_contracts import SelectedDimension, SelectedDimensions
from gemeente_data_platform.population_extraction import ExtractionSummary


def test_cli_logs_quality_terminology(monkeypatch, caplog) -> None:
    """De CLI noemt unieke codes en actieve waarnemingen afzonderlijk."""
    summary = ExtractionSummary(
        dataset_code="03759ned",
        dataset_title="Voorbeeld",
        period_codes=["2020JJ00"],
        municipal_code_count=835,
        record_count=835,
        active_observation_count=355,
        active_municipality_counts={"2020JJ00": 355},
        missing_january_population_count=480,
        missing_average_population_count=480,
        warnings=["Gemiddelde bevolking ontbreekt volledig voor 2020JJ00."],
        api_page_count=8,
        output_directory=Path("data/raw/cbs/03759ned/example"),
        selected_dimensions=SelectedDimensions(
            gender=SelectedDimension("T001038", "Totaal mannen en vrouwen"),
            age=SelectedDimension("10000", "Totaal"),
            marital_status=SelectedDimension("T001019", "Totaal burgerlijke staat"),
            population_on_january_1=SelectedDimension(
                "BevolkingOp1Januari_1", "Bevolking op 1 januari"
            ),
            average_population=SelectedDimension(
                "GemiddeldeBevolking_2", "Gemiddelde bevolking"
            ),
        ),
    )
    monkeypatch.setattr(cli, "configure_logging", lambda: None)
    monkeypatch.setattr(cli, "extract_population", lambda *_: summary)

    with caplog.at_level(logging.INFO):
        cli.main()

    assert "unieke gemeentecodes=835" in caplog.text
    assert "actieve gemeentewaarnemingen=355" in caplog.text
    assert "waarschuwingen=1" in caplog.text
    assert "Gemeenten=835" not in caplog.text
