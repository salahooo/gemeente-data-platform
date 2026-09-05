"""Expose last successful dataset lineage through a read-only mart view."""

from alembic import op

revision = "20260905_01"
down_revision = "20260904_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Keep operational details private while publishing safe load provenance."""
    op.execute(
        "CREATE VIEW mart.v_dataset_lineage AS "
        "SELECT processed_run_id, pipeline_run_id, finished_at AS completed_at "
        "FROM ops.etl_run WHERE status = 'success' AND finished_at IS NOT NULL "
        "ORDER BY finished_at DESC LIMIT 1"
    )
    op.execute("GRANT SELECT ON mart.v_dataset_lineage TO gemeente_api")
    op.execute("GRANT SELECT ON mart.v_dataset_lineage TO gemeente_reader")


def downgrade() -> None:
    """Remove the public-safe lineage projection."""
    op.execute("DROP VIEW mart.v_dataset_lineage")
