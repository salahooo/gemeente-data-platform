"""Add database constraints for processed population contracts."""

from alembic import op

revision = "20260904_02"
down_revision = "20260904_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Enforce non-empty names and non-negative average population."""
    op.execute("ALTER TABLE core.dim_municipality ADD CONSTRAINT ck_municipality_name_not_blank CHECK (btrim(municipality_name) <> '')")
    op.execute("ALTER TABLE core.fact_population ADD CONSTRAINT ck_average_population_nonnegative CHECK (average_population IS NULL OR average_population >= 0)")


def downgrade() -> None:
    """Remove the contract constraints introduced by this revision."""
    op.execute("ALTER TABLE core.fact_population DROP CONSTRAINT ck_average_population_nonnegative")
    op.execute("ALTER TABLE core.dim_municipality DROP CONSTRAINT ck_municipality_name_not_blank")
