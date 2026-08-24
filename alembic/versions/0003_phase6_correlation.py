"""Add Phase 6 candidate and historical resurfacing persistence."""

from alembic import op

from hermes_cti.db.models import (
    CorrelationCandidateRecord,
    CorrelationContradictionRecord,
    ResurfacingEventRecord,
)

revision = "0003_phase6_correlation"
down_revision = "0002_phase5_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The baseline creates current metadata in fresh databases. create_all is
    # additive here so Phase 4/5 databases receive only the new tables.
    bind = op.get_bind()
    CorrelationCandidateRecord.__table__.create(bind=bind, checkfirst=True)
    ResurfacingEventRecord.__table__.create(bind=bind, checkfirst=True)
    CorrelationContradictionRecord.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    CorrelationContradictionRecord.__table__.drop(bind=op.get_bind(), checkfirst=True)
    ResurfacingEventRecord.__table__.drop(bind=op.get_bind(), checkfirst=True)
    CorrelationCandidateRecord.__table__.drop(bind=op.get_bind(), checkfirst=True)
