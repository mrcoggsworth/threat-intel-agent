"""Complete normalized provenance for provider and publication artifacts."""

from alembic import op

revision = "0008_provenance_completion"
down_revision = "0007_report_current_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE entity_evidence DROP CONSTRAINT IF EXISTS "
        "entity_evidence_provider_result_id_fkey"
    )
    op.execute(
        "ALTER TABLE entity_evidence ADD COLUMN IF NOT EXISTS provider_result_id UUID"
    )
    op.execute(
        "ALTER TABLE entity_evidence DROP CONSTRAINT IF EXISTS "
        "ck_entity_evidence_source"
    )
    op.execute(
        "ALTER TABLE entity_evidence ADD CONSTRAINT ck_entity_evidence_source "
        "CHECK (source_document_id IS NOT NULL OR raw_artifact_id IS NOT NULL "
        "OR evidence_claim_id IS NOT NULL OR supporting_urls IS NOT NULL "
        "OR content_hash IS NOT NULL OR provider_result_id IS NOT NULL)"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
        "'fk_entity_evidence_provider_result') THEN "
        "ALTER TABLE entity_evidence ADD CONSTRAINT "
        "fk_entity_evidence_provider_result FOREIGN KEY (provider_result_id) "
        "REFERENCES enrichment_result(id); "
        "END IF; END $$"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entity_evidence_provider_result "
        "ON entity_evidence (provider_result_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_entity_evidence_provider_result")
    op.execute(
        "ALTER TABLE entity_evidence DROP CONSTRAINT IF EXISTS "
        "fk_entity_evidence_provider_result"
    )
    op.execute(
        "ALTER TABLE entity_evidence DROP CONSTRAINT IF EXISTS "
        "ck_entity_evidence_source"
    )
    op.execute(
        "ALTER TABLE entity_evidence ADD CONSTRAINT ck_entity_evidence_source "
        "CHECK (source_document_id IS NOT NULL OR raw_artifact_id IS NOT NULL "
        "OR evidence_claim_id IS NOT NULL OR supporting_urls IS NOT NULL "
        "OR content_hash IS NOT NULL)"
    )
    op.execute("ALTER TABLE entity_evidence DROP COLUMN IF EXISTS provider_result_id")
