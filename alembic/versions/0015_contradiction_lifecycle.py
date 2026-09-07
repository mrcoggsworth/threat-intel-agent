"""Add analyst lifecycle metadata to contradiction records."""

from __future__ import annotations

from alembic import op

revision = "0015_contradiction_lifecycle"
down_revision = "0014_hunt_playbooks"
branch_labels = None
depends_on = None


def _constraint(name: str, statement: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '"
        + name
        + "') THEN "
        + statement
        + "; END IF; END $$"
    )


def upgrade() -> None:
    op.execute(
        "ALTER TABLE correlation_contradiction ADD COLUMN IF NOT EXISTS "
        "review_state VARCHAR(32) NOT NULL DEFAULT 'proposed'"
    )
    op.execute(
        "ALTER TABLE correlation_contradiction ADD COLUMN IF NOT EXISTS "
        "confidence DOUBLE PRECISION NOT NULL DEFAULT 0.0"
    )
    op.execute(
        "ALTER TABLE correlation_contradiction ADD COLUMN IF NOT EXISTS "
        "supersedes_id UUID"
    )
    _constraint(
        "ck_correlation_contradiction_review_state",
        "ALTER TABLE correlation_contradiction ADD CONSTRAINT "
        "ck_correlation_contradiction_review_state CHECK "
        "(review_state IN ('proposed', 'reviewed', 'rejected'))",
    )
    _constraint(
        "ck_correlation_contradiction_confidence",
        "ALTER TABLE correlation_contradiction ADD CONSTRAINT "
        "ck_correlation_contradiction_confidence CHECK "
        "(confidence >= 0 AND confidence <= 1)",
    )
    _constraint(
        "fk_correlation_contradiction_supersedes",
        "ALTER TABLE correlation_contradiction ADD CONSTRAINT "
        "fk_correlation_contradiction_supersedes FOREIGN KEY (supersedes_id) "
        "REFERENCES correlation_contradiction(id)",
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_correlation_contradiction_subject "
        "ON correlation_contradiction "
        "(subject_entity_type, subject_entity_id, updated_at, id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_correlation_contradiction_subject")
    op.execute(
        "ALTER TABLE correlation_contradiction DROP CONSTRAINT IF EXISTS "
        "fk_correlation_contradiction_supersedes"
    )
    op.execute(
        "ALTER TABLE correlation_contradiction DROP CONSTRAINT IF EXISTS "
        "ck_correlation_contradiction_confidence"
    )
    op.execute(
        "ALTER TABLE correlation_contradiction DROP CONSTRAINT IF EXISTS "
        "ck_correlation_contradiction_review_state"
    )
    op.execute(
        "ALTER TABLE correlation_contradiction DROP COLUMN IF EXISTS supersedes_id"
    )
    op.execute("ALTER TABLE correlation_contradiction DROP COLUMN IF EXISTS confidence")
    op.execute(
        "ALTER TABLE correlation_contradiction DROP COLUMN IF EXISTS review_state"
    )
