"""Create the Phase 4 PostgreSQL persistence baseline."""

from alembic import op

from hermes_cti.db.models import Base

revision = "0001_phase4_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION hermes_raw_artifact_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'raw_artifact rows are immutable';
            END IF;
            RETURN OLD;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER raw_artifact_immutable
        BEFORE UPDATE OR DELETE ON raw_artifact
        FOR EACH ROW EXECUTE FUNCTION hermes_raw_artifact_immutable()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS raw_artifact_immutable ON raw_artifact")
    op.execute("DROP FUNCTION IF EXISTS hermes_raw_artifact_immutable()")
    Base.metadata.drop_all(bind=op.get_bind())
