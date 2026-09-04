"""CLI voor laden van de nieuwste gevalideerde processed snapshot."""

from __future__ import annotations

import argparse

from gemeente_data_platform.config import settings
from gemeente_data_platform.database import create_database_engine
from gemeente_data_platform.database_loader import load_snapshot, select_processed_run


def main() -> None:
    """Valideer en laad de geselecteerde processed run."""
    parser = argparse.ArgumentParser(
        description="Laad een processed CBS-run in PostgreSQL."
    )
    parser.add_argument(
        "--processed-run", help="Processed run-id; standaard de nieuwste geldige run."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Valideer zonder data te wijzigen."
    )
    args = parser.parse_args()
    run = select_processed_run(settings.cbs_dataset_code, args.processed_run)
    result = load_snapshot(create_database_engine(), run, args.dry_run)
    print(f"Database load {result} | processed run={run.manifest['processed_run_id']}")


if __name__ == "__main__":
    main()
