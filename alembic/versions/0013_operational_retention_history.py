"""Operationalize raw-artifact retention metadata and source config history."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from alembic import op
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from hermes_cti.db.models import Source, SourceConfigurationHistory

revision = "0013_op_retention"
down_revision = "0012_vuln_observation_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE raw_artifact ADD COLUMN IF NOT EXISTS "
        "retention_policy VARCHAR(64) NOT NULL DEFAULT immutable_evidence"
    )
    op.execute(
        "ALTER TABLE raw_artifact ADD COLUMN IF NOT EXISTS "
        "retention_expires_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE raw_artifact ADD COLUMN IF NOT EXISTS "
        "storage_state VARCHAR(32) NOT NULL DEFAULT retained"
    )

    bind = op.get_bind()
    SourceConfigurationHistory.__table__.create(bind=bind, checkfirst=True)
    for source in bind.execute(select(Source)).scalars():
        payload = {
            "source_id": source.source_id,
            "name": source.name,
            "source_type": source.source_type,
            "url": source.canonical_base_url,
            "category": source.category,
            "enabled": source.enabled,
            "polling_interval_seconds": source.polling_interval_seconds,
            "timeout_seconds": source.timeout_seconds,
            "max_response_bytes": source.max_response_bytes,
            "reliability": source.reliability,
            "tags": source.tags,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        configuration_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        statement = pg_insert(SourceConfigurationHistory).values(
            id=uuid5(
                NAMESPACE_URL, f"source-config:{source.source_id}:{configuration_hash}"
            ),
            source_id=source.source_id,
            configuration_version=source.configuration_version,
            configuration_hash=configuration_hash,
            configuration=payload,
            recorded_at=source.updated_at,
            created_at=source.created_at,
            updated_at=source.updated_at,
            created_by_origin="migration:0013",
        )
        bind.execute(
            statement.on_conflict_do_nothing(
                index_elements=[
                    SourceConfigurationHistory.source_id,
                    SourceConfigurationHistory.configuration_hash,
                ]
            )
        )


def downgrade() -> None:
    SourceConfigurationHistory.__table__.drop(bind=op.get_bind(), checkfirst=True)
    op.execute("ALTER TABLE raw_artifact DROP COLUMN IF EXISTS storage_state")
    op.execute("ALTER TABLE raw_artifact DROP COLUMN IF EXISTS retention_expires_at")
    op.execute("ALTER TABLE raw_artifact DROP COLUMN IF EXISTS retention_policy")
