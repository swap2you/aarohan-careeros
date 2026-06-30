"""Backfill data_provenance using defensible legacy classification rules."""

from alembic import op

revision = "0011_provenance_backfill"
down_revision = "0010_data_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fixture feed canonical record
    op.execute(
        """
        UPDATE jobs SET data_provenance = 'fixture'
        WHERE external_id = 'fixture-remote-qe-001'
           OR lower(external_id) LIKE 'fixture-%'
        """
    )
    # Playwright / E2E ingest markers
    op.execute(
        """
        UPDATE jobs SET data_provenance = 'test'
        WHERE lower(external_id) LIKE 'e2e-%'
           OR lower(external_id) LIKE 'e2e_%'
           OR url ILIKE '%example.com/e2e/%'
           OR requisition_id LIKE 'REQ-E2E-%'
        """
    )
    # Applications inherit job provenance
    op.execute(
        """
        UPDATE applications AS a
        SET data_provenance = j.data_provenance
        FROM jobs AS j
        WHERE a.job_id = j.id
          AND j.data_provenance IN ('fixture', 'test')
          AND a.data_provenance NOT IN ('fixture', 'test')
        """
    )
    # Companies linked only to fixture/test jobs
    op.execute(
        """
        UPDATE companies AS c
        SET data_provenance = sub.prov
        FROM (
            SELECT j.company_id,
                   CASE WHEN bool_or(j.data_provenance = 'test') THEN 'test' ELSE 'fixture' END AS prov
            FROM jobs j
            WHERE j.company_id IS NOT NULL
            GROUP BY j.company_id
            HAVING bool_and(j.data_provenance IN ('fixture', 'test'))
        ) AS sub
        WHERE c.id = sub.company_id
          AND c.data_provenance NOT IN ('fixture', 'test')
        """
    )


def downgrade() -> None:
    pass
