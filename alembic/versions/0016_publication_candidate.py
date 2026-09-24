"""Durable publication-candidate ledger for independently gated daily runs."""

from __future__ import annotations

from alembic import op

revision = "0016_publication_candidate"
down_revision = "0015_contradiction_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS publication_candidate (
            candidate_id UUID PRIMARY KEY,
            run_id UUID NOT NULL REFERENCES ingestion_run(id),
            event_identity VARCHAR(255) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            rank INTEGER NOT NULL,
            lifecycle VARCHAR(32) NOT NULL,
            evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_urls JSONB NOT NULL DEFAULT '[]'::jsonb,
            enrichment_state VARCHAR(64) NOT NULL DEFAULT 'unknown',
            validation_state VARCHAR(64) NOT NULL DEFAULT 'not_run',
            publication_state VARCHAR(64) NOT NULL DEFAULT 'not_published',
            failure_reason VARCHAR(1024),
            published_public_id VARCHAR(64),
            retry_eligible BOOLEAN NOT NULL DEFAULT true,
            attempts INTEGER NOT NULL DEFAULT 0,
            report_id UUID REFERENCES report(id),
            report_version_id UUID REFERENCES report_version(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            record_status VARCHAR(32) NOT NULL DEFAULT 'active',
            created_by_origin VARCHAR(64) NOT NULL DEFAULT 'deterministic_service',
            CONSTRAINT uq_publication_candidate_run_event
                UNIQUE (run_id, event_identity),
            CONSTRAINT ck_publication_candidate_lifecycle CHECK (
                lifecycle IN (
                    'identified', 'researching', 'blocked', 'validated',
                    'submitted', 'published', 'failed')
            ),
            CONSTRAINT ck_publication_candidate_attempts
                CHECK (attempts >= 0)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_publication_candidate_run_lifecycle "
        "ON publication_candidate (run_id, lifecycle)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS publication_candidate")
