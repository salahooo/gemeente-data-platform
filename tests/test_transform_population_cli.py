"""Tests voor de raw-naar-processed CLI zonder lokale raw afhankelijkheid."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from gemeente_data_platform.data_contracts import DataContractError
from gemeente_data_platform.transform_population import PROJECT_ROOT, main


def test_main_logs_successful_transformation(monkeypatch, caplog) -> None:
    """De CLI logt na een succesvolle transformatie een compacte samenvatting."""
    import gemeente_data_platform.transform_population as cli

    output_directory = (
        PROJECT_ROOT / "data" / "processed" / "cbs" / "03759ned" / "fixture-run"
    )
    monkeypatch.setattr(
        cli,
        "parse_args",
        lambda: argparse.Namespace(raw_run="fixture-run", output_root=None),
    )
    monkeypatch.setattr(
        cli,
        "transform_raw_run",
        lambda *args, **kwargs: SimpleNamespace(
            raw_run=SimpleNamespace(run_id="fixture-run"),
            output_directory=output_directory,
            table_rows={"fact_population": 1},
        ),
    )

    with caplog.at_level(logging.INFO):
        main()

    assert "Transformatie geslaagd" in caplog.text
    assert "fixture-run" in caplog.text


def test_main_propagates_validation_error(monkeypatch) -> None:
    """Een validatiefout blijft ongehandeld en geeft de module een non-zero exitcode."""
    import gemeente_data_platform.transform_population as cli

    monkeypatch.setattr(
        cli,
        "parse_args",
        lambda: argparse.Namespace(raw_run="bad-run", output_root=Path("output")),
    )

    def fail_transformation(*args, **kwargs) -> None:
        raise DataContractError("Raw run checksum verification failed.")

    monkeypatch.setattr(cli, "transform_raw_run", fail_transformation)

    with pytest.raises(DataContractError, match="checksum"):
        main()
