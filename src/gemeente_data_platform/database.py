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
