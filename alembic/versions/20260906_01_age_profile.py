"""Optional age profile snapshot and explicitly public quality projections."""

from alembic import op

revision = "20260906_01"
down_revision = "20260905_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE core.fact_age_profile (
            region_code varchar(6) NOT NULL,
            municipality_code varchar(6) REFERENCES core.dim_municipality(municipality_code)
                DEFERRABLE INITIALLY DEFERRED,
            year integer NOT NULL CHECK (year BETWEEN 1995 AND 2200),
            category varchar(8) NOT NULL CHECK (category IN ('0-14','15-24','25-44','45-64','65+')),
            population integer CHECK (population >= 0),
            total integer CHECK (total >= 0),
            PRIMARY KEY (region_code, year, category),
            CHECK ((region_code = 'NL01' AND municipality_code IS NULL) OR
                   (region_code ~ '^GM[0-9]{4}$' AND municipality_code IS NOT NULL
                    AND municipality_code = region_code)),
            CHECK (population <= total)
        )
    """)
    op.execute("""
        CREATE TABLE ops.age_snapshot (
            year integer PRIMARY KEY CHECK (year BETWEEN 1995 AND 2200),
            checksum char(64) NOT NULL,
            completed_at timestamptz NOT NULL,
            record_count integer NOT NULL CHECK (record_count > 0),
            missing_values integer NOT NULL CHECK (missing_values >= 0)
        )
    """)
    op.execute("""
        CREATE VIEW mart.v_municipality_age_profile AS
        SELECT a.municipality_code, a.year, a.category, a.population,
               CASE WHEN a.total > 0 THEN round(100.0*a.population/a.total,1) END AS share_percent,
               CASE WHEN n.total > 0 THEN round(100.0*n.population/n.total,1) END AS national_share_percent
        FROM core.fact_age_profile a
        LEFT JOIN core.fact_age_profile n ON n.region_code='NL01'
            AND n.year=a.year AND n.category=a.category
        WHERE a.municipality_code IS NOT NULL
    """)
    op.execute("""
        CREATE VIEW mart.v_public_data_quality AS
        SELECT '03759ned'::text AS dataset_code, 'Bevolking'::text AS dataset_name,
            'CBS Open Data'::text AS source, min(p.year) AS first_year, max(p.year) AS last_year,
            (SELECT max(finished_at) FROM ops.etl_run WHERE status='success') AS completed_at,
            count(*) AS record_count,
            CASE WHEN count(*) > 0 AND EXISTS(SELECT 1 FROM ops.etl_run WHERE status='success')
                 THEN 'validated' ELSE 'unavailable' END AS validation_status,
            count(*) FILTER (WHERE p.average_population IS NULL) AS missing_values,
            'Ontbrekende gemiddelde bevolking is geen nulwaarde.'::text AS warning
        FROM mart.v_population_by_municipality_year p
        UNION ALL
        SELECT '70072ned', 'Leeftijdsopbouw', 'CBS Open Data', min(year), max(year),
            max(completed_at), coalesce(sum(record_count),0),
            CASE WHEN count(*) > 0 THEN 'validated' ELSE 'unavailable' END,
            coalesce(sum(missing_values),0),
            'Leeftijd op 1 januari; historische gemeentecodes worden niet omgerekend.'
        FROM ops.age_snapshot
    """)
    op.execute(
        "CREATE TABLE ops.stage_age_profile "
        "(LIKE core.fact_age_profile INCLUDING CONSTRAINTS INCLUDING INDEXES)"
    )
    for view in ("v_municipality_age_profile", "v_public_data_quality"):
        op.execute(f"GRANT SELECT ON mart.{view} TO gemeente_api, gemeente_reader")


def downgrade() -> None:
    op.execute("DROP VIEW mart.v_public_data_quality")
    op.execute("DROP VIEW mart.v_municipality_age_profile")
    op.execute("DROP TABLE core.fact_age_profile")
    op.execute("DROP TABLE ops.age_snapshot")
    op.execute("DROP TABLE ops.stage_age_profile")
