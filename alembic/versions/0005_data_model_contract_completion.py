"""Complete the minimum historical CTI data-model contracts.

The upgrade is intentionally additive for existing installations.  Fresh
databases already receive the same columns and constraints from metadata in
the baseline migration; IF NOT EXISTS keeps upgrades idempotent across both
paths.
"""

from alembic import op

from hermes_cti.db.models import (
    Campaign,
    EntityEvidence,
    Infrastructure,
    Malware,
    ThreatActor,
    Tool,
)

revision = "0005_data_model_contracts"
down_revision = "0004_phase7_reporting"
branch_labels = None
depends_on = None


AUDIT_TABLES = (
    "ingestion_run",
    "source_run",
    "operational_event",
    "source",
    "raw_artifact",
    "source_document",
    "evidence_claim",
    "indicator",
    "indicator_observation",
    "vulnerability",
    "product",
    "affected_product",
    "attack_technique",
    "enrichment_result",
    "risk_assessment",
    "relationship",
    "relationship_evidence",
    "correlation_candidate",
    "correlation_contradiction",
    "resurfacing_event",
    "report",
    "report_version",
    "report_entity",
    "hunt",
    "remediation",
    "detection",
    "publication",
    "model_run",
)


def _constraint(name: str, statement: str) -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '"
        + name
        + "') THEN "
        + statement
        + "; END IF; END $$"
    )


def _index(name: str, table: str, columns: str) -> None:
    op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")


def upgrade() -> None:
    for table in AUDIT_TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "record_status VARCHAR(32) NOT NULL DEFAULT 'active'"
        )
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "
            "created_by_origin VARCHAR(64) NOT NULL DEFAULT 'deterministic_service'"
        )

    bind = op.get_bind()
    for model in (ThreatActor, Malware, Tool, Campaign, Infrastructure, EntityEvidence):
        model.__table__.create(bind=bind, checkfirst=True)

    _constraint(
        "fk_source_run_source",
        "ALTER TABLE source_run ADD CONSTRAINT fk_source_run_source "
        "FOREIGN KEY (source_id) REFERENCES source(source_id)",
    )
    _constraint(
        "fk_operational_event_run",
        "ALTER TABLE operational_event ADD CONSTRAINT fk_operational_event_run "
        "FOREIGN KEY (run_id) REFERENCES ingestion_run(id)",
    )
    _constraint(
        "fk_source_document_supersedes",
        "ALTER TABLE source_document ADD CONSTRAINT fk_source_document_supersedes "
        "FOREIGN KEY (supersedes_id) REFERENCES source_document(id)",
    )
    _constraint(
        "fk_affected_product_claim",
        "ALTER TABLE affected_product ADD CONSTRAINT fk_affected_product_claim "
        "FOREIGN KEY (source_claim_id) REFERENCES evidence_claim(id)",
    )
    _constraint(
        "fk_relationship_evidence_document",
        "ALTER TABLE relationship_evidence ADD CONSTRAINT "
        "fk_relationship_evidence_document "
        "FOREIGN KEY (source_document_id) REFERENCES source_document(id)",
    )
    _constraint(
        "fk_relationship_evidence_claim",
        "ALTER TABLE relationship_evidence ADD CONSTRAINT "
        "fk_relationship_evidence_claim "
        "FOREIGN KEY (evidence_claim_id) REFERENCES evidence_claim(id)",
    )
    _constraint(
        "fk_relationship_evidence_provider",
        "ALTER TABLE relationship_evidence ADD CONSTRAINT "
        "fk_relationship_evidence_provider "
        "FOREIGN KEY (provider_result_id) REFERENCES enrichment_result(id)",
    )

    _constraint(
        "ck_ingestion_run_status",
        "ALTER TABLE ingestion_run ADD CONSTRAINT ck_ingestion_run_status "
        "CHECK (status IN ('scheduled', 'running', 'completed', 'failed', 'skipped'))",
    )
    _constraint(
        "ck_ingestion_run_terminal_completion",
        "ALTER TABLE ingestion_run ADD CONSTRAINT ck_ingestion_run_terminal_completion "
        "CHECK ((status IN ('completed', 'failed', 'skipped')) = "
        "(completed_at IS NOT NULL))",
    )
    _constraint(
        "ck_evidence_claim_offsets",
        "ALTER TABLE evidence_claim ADD CONSTRAINT ck_evidence_claim_offsets "
        "CHECK (start_offset >= 0 AND end_offset >= start_offset)",
    )
    _constraint(
        "ck_evidence_claim_confidence",
        "ALTER TABLE evidence_claim ADD CONSTRAINT ck_evidence_claim_confidence "
        "CHECK (confidence >= 0 AND confidence <= 1)",
    )
    _constraint(
        "ck_relationship_evidence_source",
        "ALTER TABLE relationship_evidence ADD CONSTRAINT "
        "ck_relationship_evidence_source "
        "CHECK (source_document_id IS NOT NULL OR evidence_claim_id IS NOT NULL "
        "OR provider_result_id IS NOT NULL)",
    )

    _index("ix_report_state_updated", "report", "state, last_updated_at")
    _index(
        "ix_source_document_canonical_hash",
        "source_document",
        "canonical_url, normalized_content_hash",
    )
    _index("ix_vulnerability_cve", "vulnerability", "cve_id")
    _index("ix_product_vendor_name", "product", "normalized_vendor, normalized_product")
    _index("ix_attack_technique_id", "attack_technique", "attack_id, framework_version")
    _index("ix_entity_evidence_entity", "entity_evidence", "entity_type, entity_id")
    _index("ix_entity_evidence_seen", "entity_evidence", "first_seen_at, last_seen_at")


def downgrade() -> None:
    for table, constraint in (
        ("relationship_evidence", "fk_relationship_evidence_provider"),
        ("relationship_evidence", "fk_relationship_evidence_claim"),
        ("relationship_evidence", "fk_relationship_evidence_document"),
        ("affected_product", "fk_affected_product_claim"),
        ("source_document", "fk_source_document_supersedes"),
        ("operational_event", "fk_operational_event_run"),
        ("source_run", "fk_source_run_source"),
        ("relationship_evidence", "ck_relationship_evidence_source"),
        ("evidence_claim", "ck_evidence_claim_confidence"),
        ("evidence_claim", "ck_evidence_claim_offsets"),
        ("ingestion_run", "ck_ingestion_run_terminal_completion"),
        ("ingestion_run", "ck_ingestion_run_status"),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
    for table in (
        "entity_evidence",
        "infrastructure",
        "campaign",
        "tool",
        "malware",
        "threat_actor",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    for table in reversed(AUDIT_TABLES):
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS created_by_origin")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS record_status")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS updated_at")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS created_at")
