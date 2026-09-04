"""Expose analytical mart views to the least-privilege API role."""

from alembic import op

revision = "20260904_04"
down_revision = "20260904_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the API catalog view and grant only mart read access."""
    op.execute(
        "CREATE OR REPLACE VIEW mart.v_municipality_catalog AS "
        "SELECT municipality_code, municipality_name, first_observed_year, "
        "last_observed_year, is_active_latest_period FROM core.dim_municipality"
    )
    op.execute("GRANT USAGE ON SCHEMA mart TO gemeente_api")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA mart TO gemeente_api")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO gemeente_api"
    )


def downgrade() -> None:
    """Remove API grants and the API-only mart catalog view."""
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA mart FROM gemeente_api")
    op.execute("REVOKE USAGE ON SCHEMA mart FROM gemeente_api")
    op.execute("DROP VIEW mart.v_municipality_catalog")
