"""Add the entity-membership index used by public projections."""

from alembic import op

revision = "0010_query_plan_indexes"
down_revision = "0009_lifecycle_checks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_entity_entity "
        "ON report_entity (entity_type, entity_id, report_version_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_entity_entity")
