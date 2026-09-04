"""Command-line-opdracht voor gecontroleerde CBS-bevolkingsextractie."""

from __future__ import annotations

import logging
from time import perf_counter

from gemeente_data_platform.cbs_client import CbsApiError, CbsClient
from gemeente_data_platform.config import settings
from gemeente_data_platform.data_contracts import DataContractError
from gemeente_data_platform.population_extraction import extract_population

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configureer compacte consolelogging voor command-line-runs."""
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(message)s")


def main() -> None:
    """Voer één gevalideerde raw extractierun uit."""
    configure_logging()
    started_at = perf_counter()
    try:
        summary = extract_population(CbsClient.from_settings(settings), settings)
    except (CbsApiError, DataContractError, OSError) as exc:
        logger.error(
            "Extractie mislukt | dataset=%s | fout=%s",
            settings.cbs_dataset_code,
            exc,
        )
        raise

    years = ",".join(period[:4] for period in summary.period_codes)
    active_per_period = ",".join(
        f"{period[:4]}={count}"
        for period, count in summary.active_municipality_counts.items()
    )
    duration_seconds = perf_counter() - started_at
    logger.info(
        "Extractie geslaagd | dataset=%s | jaren=%s | unieke gemeentecodes=%s "
        "| actieve gemeenten per periode=%s | raw records=%s "
        "| actieve gemeentewaarnemingen=%s | ontbrekend januari=%s "
        "| ontbrekend gemiddelde=%s | waarschuwingen=%s | API-pagina's=%s "
        "| uitvoermap=%s | duur=%.2fs",
        summary.dataset_code,
        years,
        summary.municipal_code_count,
        active_per_period,
        summary.record_count,
        summary.active_observation_count,
        summary.missing_january_population_count,
        summary.missing_average_population_count,
        len(summary.warnings),
        summary.api_page_count,
        summary.output_directory.as_posix(),
        duration_seconds,
    )


if __name__ == "__main__":
    main()
