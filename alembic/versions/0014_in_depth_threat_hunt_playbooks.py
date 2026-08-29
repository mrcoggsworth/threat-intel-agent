"""Add in-depth threat hunt playbook fields to hunt table."""

from __future__ import annotations

from alembic import op

revision = "0014_hunt_playbooks"
down_revision = "0013_op_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "typed_queries JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "execution_phases JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "pivot_guidance JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE hunt ADD COLUMN IF NOT EXISTS "
        "forensic_artifacts JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS forensic_artifacts")
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS pivot_guidance")
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS execution_phases")
    op.execute("ALTER TABLE hunt DROP COLUMN IF EXISTS typed_queries")
