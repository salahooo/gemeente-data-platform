"""CLI voor de reproduceerbare raw-naar-processed bevolkingstransformatie."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from time import perf_counter

from gemeente_data_platform.config import settings
from gemeente_data_platform.data_contracts import DataContractError
from gemeente_data_platform.processed_contracts import ProcessedContractError
from gemeente_data_platform.processed_pipeline import transform_raw_run
from gemeente_data_platform.processed_storage import PROCESSED_ROOT, PROJECT_ROOT

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parseer de optionele raw-run en processed outputlocatie."""
    parser = argparse.ArgumentParser(
        description="Transformeer een gevalideerde raw CBS-run naar processed tabellen."
    )
    parser.add_argument(
        "--raw-run",
        help="Raw run-id of draagbaar pad; standaard de nieuwste geldige raw run.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Optionele root voor processed output, relatief aan de projectroot.",
    )
    return parser.parse_args()


def main() -> None:
    """Voer de transformatie uit en log een compacte uitvoersamenvatting."""
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")
    args = parse_args()
    started_at = perf_counter()
    try:
        output_root = (
            (PROJECT_ROOT / args.output_root)
            if args.output_root is not None and not args.output_root.is_absolute()
            else args.output_root or PROCESSED_ROOT
        )
        summary = transform_raw_run(
            settings.cbs_dataset_code,
            raw_run_selector=args.raw_run,
            output_root=output_root,
        )
    except (DataContractError, ProcessedContractError, OSError, ValueError) as exc:
        logger.error(
            "Transformatie mislukt | dataset=%s | fout=%s",
            settings.cbs_dataset_code,
            exc,
        )
        raise
    logger.info(
        "Transformatie geslaagd | raw run=%s | processed run=%s | rijen=%s "
        "| uitvoermap=%s | duur=%.2fs",
        summary.raw_run.run_id,
        summary.output_directory.name,
        summary.table_rows,
        _display_output_path(summary.output_directory),
        perf_counter() - started_at,
    )


def _display_output_path(output_directory: Path) -> str:
    """Gebruik een projectrelatief pad wanneer de uitvoer binnen het project staat."""
    try:
        return output_directory.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return output_directory.as_posix()


if __name__ == "__main__":
    main()
