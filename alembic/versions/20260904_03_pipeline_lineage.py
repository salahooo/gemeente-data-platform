"""Add nullable pipeline lineage to ETL runs."""

from alembic import op

revision = "20260904_03"
down_revision = "20260904_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve compatibility for direct loader runs."""
    op.execute("ALTER TABLE ops.etl_run ADD COLUMN pipeline_run_id TEXT")
    op.execute("CREATE INDEX ix_etl_run_pipeline_run_id ON ops.etl_run (pipeline_run_id)")


def downgrade() -> None:
    """Remove pipeline lineage."""
    op.execute("DROP INDEX ops.ix_etl_run_pipeline_run_id")
    op.execute("ALTER TABLE ops.etl_run DROP COLUMN pipeline_run_id")
