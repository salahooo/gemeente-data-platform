"""Veilige verbinding en metadata voor de lokale PostgreSQL-database."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from gemeente_data_platform.config import settings


def create_database_engine() -> Engine:
    """Maak een engine die parameters, waaronder wachtwoorden, niet logt."""
    return create_engine(
        settings.database_url(), hide_parameters=True, pool_pre_ping=True
    )


def create_api_database_engine(api_settings=None) -> Engine:
    """Maak uitsluitend op aanvraag een engine voor de read-only API-rol."""
    active_settings = api_settings or settings
    return create_engine(
        active_settings.api_database_url(), hide_parameters=True, pool_pre_ping=True
    )
