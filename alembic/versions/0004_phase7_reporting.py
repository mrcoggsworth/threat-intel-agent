"""Add Phase 7 structured report and artifact metadata."""

from alembic import op

revision = "0004_phase7_reporting"
down_revision = "0003_phase6_correlation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE report_version ADD COLUMN IF NOT EXISTS "
        "structured_content JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE report_version ADD COLUMN IF NOT EXISTS "
        "evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE report_version ADD COLUMN IF NOT EXISTS "
        "artifact_manifest JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE report_version ADD COLUMN IF NOT EXISTS "
        "skill_versions JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE report_version ADD COLUMN IF NOT EXISTS "
        "application_version VARCHAR(128) NOT NULL DEFAULT 'unknown'"
    )
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "queries JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE remediation ADD COLUMN IF NOT EXISTS "
        "evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE detection ADD COLUMN IF NOT EXISTS "
        "evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE detection DROP COLUMN IF EXISTS evidence_ids")
    op.execute("ALTER TABLE remediation DROP COLUMN IF EXISTS evidence_ids")
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS evidence_ids")
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS queries")
    op.execute("ALTER TABLE report_version DROP COLUMN IF EXISTS application_version")
    op.execute("ALTER TABLE report_version DROP COLUMN IF EXISTS skill_versions")
    op.execute("ALTER TABLE report_version DROP COLUMN IF EXISTS artifact_manifest")
    op.execute("ALTER TABLE report_version DROP COLUMN IF EXISTS evidence_ids")
    op.execute("ALTER TABLE report_version DROP COLUMN IF EXISTS structured_content")
