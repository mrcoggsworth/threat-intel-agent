"""Add Phase 5 enrichment metadata and score versioning.

The baseline migration creates current metadata in fresh databases. IF NOT EXISTS
keeps this revision safe for databases upgraded from the Phase 4 schema.
"""

from alembic import op

revision = "0002_phase5_enrichment"
down_revision = "0001_phase4_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE enrichment_result ADD COLUMN IF NOT EXISTS "
        "raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE risk_assessment ADD COLUMN IF NOT EXISTS "
        "score_version VARCHAR(64) NOT NULL DEFAULT 'phase5-v1'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE risk_assessment DROP COLUMN IF EXISTS score_version")
    op.execute("ALTER TABLE enrichment_result DROP COLUMN IF EXISTS raw_metadata")
