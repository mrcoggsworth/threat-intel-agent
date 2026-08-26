"""Complete model-run audit metadata and safe supersession links."""

from alembic import op

revision = "0006_audit_projection"
down_revision = "0005_data_model_contracts"
branch_labels = None
depends_on = None


def _foreign_key(
    name: str,
    table: str,
    column: str,
    referenced_table: str,
    referenced_column: str = "id",
) -> None:
    op.execute(
        "DO $$ DECLARE local_attnum smallint; BEGIN "
        f"SELECT attnum INTO local_attnum FROM pg_attribute WHERE attrelid = "
        f"'{table}'::regclass AND attname = '{column}' AND NOT attisdropped; "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE contype = 'f' "
        f"AND conrelid = '{table}'::regclass "
        f"AND confrelid = '{referenced_table}'::regclass "
        "AND conkey = ARRAY[local_attnum]::smallint[]) THEN "
        f"ALTER TABLE {table} ADD CONSTRAINT {name} "
        f"FOREIGN KEY ({column}) REFERENCES {referenced_table}({referenced_column}); "
        "END IF; END $$"
    )


def upgrade() -> None:
    op.execute(
        "ALTER TABLE model_run ADD COLUMN IF NOT EXISTS system_prompt_hash VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE model_run ADD COLUMN IF NOT EXISTS "
        "skill_version_hashes JSONB NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute("ALTER TABLE model_run ADD COLUMN IF NOT EXISTS cost_metadata JSONB")

    _foreign_key(
        "fk_model_run_triggering_run",
        "model_run",
        "triggering_run_id",
        "ingestion_run",
    )
    _foreign_key(
        "fk_risk_assessment_supersedes",
        "risk_assessment",
        "supersedes_id",
        "risk_assessment",
    )
    _foreign_key(
        "fk_relationship_supersedes",
        "relationship",
        "supersedes_id",
        "relationship",
    )
    _foreign_key(
        "fk_report_version_supersedes",
        "report_version",
        "supersedes_id",
        "report_version",
    )
    _foreign_key(
        "fk_publication_rollback_target",
        "publication",
        "rollback_target",
        "report_version",
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entity_seen "
        "ON entity_evidence (first_seen_at, last_seen_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_report_version_public_fts "
        "ON report_version USING GIN (to_tsvector('simple', "
        "coalesce(executive_summary, '') || ' ' || "
        "coalesce(technical_analysis, '') || ' ' || "
        "coalesce(evidence_summary, '')))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_report_version_public_fts")
    op.execute("DROP INDEX IF EXISTS ix_entity_seen")
    for table, constraint in (
        ("publication", "fk_publication_rollback_target"),
        ("report_version", "fk_report_version_supersedes"),
        ("relationship", "fk_relationship_supersedes"),
        ("risk_assessment", "fk_risk_assessment_supersedes"),
        ("model_run", "fk_model_run_triggering_run"),
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")
    op.execute("ALTER TABLE model_run DROP COLUMN IF EXISTS cost_metadata")
    op.execute("ALTER TABLE model_run DROP COLUMN IF EXISTS skill_version_hashes")
    op.execute("ALTER TABLE model_run DROP COLUMN IF EXISTS system_prompt_hash")
