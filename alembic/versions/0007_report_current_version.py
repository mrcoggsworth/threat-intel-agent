"""Enforce report-to-current-version integrity after write-ordering fix."""

from alembic import op

revision = "0007_report_current_version"
down_revision = "0006_audit_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE report DROP CONSTRAINT IF EXISTS report_current_version_id_fkey"
    )
    op.execute("ALTER TABLE report DROP CONSTRAINT IF EXISTS fk_report_current_version")
    op.execute(
        "ALTER TABLE report ADD CONSTRAINT fk_report_current_version "
        "FOREIGN KEY (current_version_id) REFERENCES report_version(id) "
        "DEFERRABLE INITIALLY DEFERRED"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE report DROP CONSTRAINT IF EXISTS fk_report_current_version")
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
        "'report_current_version_id_fkey') THEN "
        "ALTER TABLE report ADD CONSTRAINT report_current_version_id_fkey "
        "FOREIGN KEY (current_version_id) REFERENCES report_version(id); "
        "END IF; END $$"
    )
