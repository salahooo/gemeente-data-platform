"""Initial PostgreSQL schemas, tables and analytical views."""

from alembic import op

revision = "20260904_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the physical model owned by gemeente_app."""
    op.execute("CREATE SCHEMA core")
    op.execute("CREATE SCHEMA mart")
    op.execute("CREATE SCHEMA ops")
    op.execute("DO $$ BEGIN EXECUTE format('REVOKE CREATE ON DATABASE %I FROM gemeente_app', current_database()); END $$")
    op.execute("REVOKE CREATE ON SCHEMA public FROM gemeente_app")
    op.execute(
        "CREATE TABLE core.dim_municipality (municipality_code VARCHAR(6) PRIMARY KEY, municipality_name TEXT NOT NULL, first_observed_year INTEGER NOT NULL CHECK (first_observed_year BETWEEN 1800 AND 2200), last_observed_year INTEGER NOT NULL CHECK (last_observed_year BETWEEN 1800 AND 2200), is_active_latest_period BOOLEAN NOT NULL, CHECK (municipality_code ~ '^GM[0-9]{4}$'), CHECK (first_observed_year <= last_observed_year))"
    )
    op.execute(
        "CREATE TABLE core.dim_period (period_code VARCHAR(8) PRIMARY KEY, year INTEGER NOT NULL UNIQUE CHECK (year BETWEEN 1800 AND 2200), period_label TEXT NOT NULL, has_january_population BOOLEAN NOT NULL, has_average_population BOOLEAN NOT NULL, CHECK (period_code ~ '^[0-9]{4}JJ00$'))"
    )
    op.execute(
        "CREATE TABLE core.fact_population (municipality_code VARCHAR(6) NOT NULL REFERENCES core.dim_municipality(municipality_code) ON UPDATE RESTRICT ON DELETE RESTRICT, period_code VARCHAR(8) NOT NULL REFERENCES core.dim_period(period_code) ON UPDATE RESTRICT ON DELETE RESTRICT, population_january_1 INTEGER NOT NULL CHECK (population_january_1 >= 0), average_population NUMERIC(18,3), PRIMARY KEY (municipality_code, period_code))"
    )
    op.execute(
        "CREATE INDEX ix_fact_population_period_code ON core.fact_population (period_code)"
    )
    op.execute(
        "CREATE TABLE ops.etl_run (run_id UUID PRIMARY KEY, processed_run_id TEXT NOT NULL UNIQUE, raw_run_id TEXT NOT NULL, raw_manifest_checksum CHAR(64) NOT NULL, processed_manifest_checksum CHAR(64) NOT NULL, started_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ, status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'skipped')), dim_municipality_count INTEGER, dim_period_count INTEGER, fact_population_count INTEGER, error_category TEXT, error_message TEXT, application_version TEXT NOT NULL, loaded_at TIMESTAMPTZ)"
    )
    op.execute(
        "CREATE OR REPLACE VIEW mart.v_population_by_municipality_year AS SELECT m.municipality_code, m.municipality_name, p.year, f.population_january_1, f.average_population, (f.average_population IS NOT NULL) AS has_average_population FROM core.fact_population f JOIN core.dim_municipality m USING (municipality_code) JOIN core.dim_period p USING (period_code)"
    )
    op.execute(
        "CREATE OR REPLACE VIEW mart.v_national_population_by_year AS SELECT p.year, COUNT(f.municipality_code) AS municipality_count, SUM(f.population_january_1) AS population_january_1_sum, SUM(f.average_population) AS average_population_sum, COUNT(*) FILTER (WHERE f.average_population IS NULL) AS missing_average_population_count FROM core.dim_period p LEFT JOIN core.fact_population f USING (period_code) GROUP BY p.year"
    )
    op.execute(
        "CREATE OR REPLACE VIEW mart.v_municipality_year_over_year AS WITH values_with_previous AS (SELECT f.municipality_code, p.year, f.population_january_1, LAG(p.year) OVER (PARTITION BY f.municipality_code ORDER BY p.year) AS previous_year, LAG(f.population_january_1) OVER (PARTITION BY f.municipality_code ORDER BY p.year) AS previous_population_january_1 FROM core.fact_population f JOIN core.dim_period p USING (period_code)) SELECT municipality_code, year, previous_year, population_january_1, previous_population_january_1, CASE WHEN previous_year = year - 1 THEN population_january_1 - previous_population_january_1 END AS population_change_absolute, CASE WHEN previous_year = year - 1 AND previous_population_january_1 > 0 THEN ROUND((population_january_1 - previous_population_january_1)::NUMERIC / previous_population_january_1 * 100, 3) END AS population_change_percent, TRUE AS same_municipality_code_only FROM values_with_previous"
    )
    op.execute("GRANT USAGE ON SCHEMA mart TO gemeente_reader")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA mart TO gemeente_reader")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA mart GRANT SELECT ON TABLES TO gemeente_reader"
    )


def downgrade() -> None:
    """Remove objects created by this revision."""
    op.execute("DROP SCHEMA ops CASCADE")
    op.execute("DROP SCHEMA mart CASCADE")
    op.execute("DROP SCHEMA core CASCADE")
