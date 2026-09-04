"""Alembic-omgeving met de veilige applicatieverbinding."""

from alembic import context
from gemeente_data_platform.database import create_database_engine

config = context.config


def run_migrations_online() -> None:
    """Voer migrations uit als gemeente_app zonder URL in alembic.ini."""
    engine = create_database_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
