"""CLI-healthcheck voor de projectdatabase."""

from sqlalchemy import text

from gemeente_data_platform.database import create_database_engine


def main() -> None:
    """Controleer verbinding, serverversie, database en toepassingsgebruiker."""
    engine = create_database_engine()
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT version(), current_database(), current_user, 1")
        ).one()
    print(
        f"Database healthcheck geslaagd | server={result[0]} | database={result[1]} | gebruiker={result[2]}"
    )


if __name__ == "__main__":
    main()
