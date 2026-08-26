"""Secret-free model execution audit persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.db.lifecycle import validate_lifecycle_value
from hermes_cti.db.models import ModelRun


class ModelRunRepository:
    """Persist reproducibility metadata without prompts or secret values."""

    async def persist(
        self,
        session: AsyncSession,
        *,
        model_run_id: UUID,
        purpose: str,
        model_provider: str,
        prompt_name: str,
        prompt_version: str,
        output_hash: str | None,
        input_evidence_ids: tuple[UUID, ...] = (),
        triggering_run_id: UUID | None = None,
        system_prompt_hash: str | None = None,
        skill_version_hashes: tuple[str, ...] = (),
        token_metadata: dict[str, Any] | None = None,
        cost_metadata: dict[str, Any] | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        status: str = "completed",
        error_classification: str | None = None,
    ) -> ModelRun:
        validate_lifecycle_value("model_run", "status", status)
        started = started_at or datetime.now(UTC)
        values = {
            "id": model_run_id,
            "purpose": purpose,
            "triggering_run_id": triggering_run_id,
            "model_provider": model_provider,
            "prompt_name": prompt_name,
            "prompt_version": prompt_version,
            "system_prompt_hash": system_prompt_hash,
            "skill_version_hash": (
                skill_version_hashes[0] if skill_version_hashes else None
            ),
            "skill_version_hashes": list(skill_version_hashes),
            "input_evidence_ids": [str(item) for item in input_evidence_ids],
            "output_hash": output_hash,
            "token_metadata": token_metadata,
            "cost_metadata": cost_metadata,
            "started_at": started,
            "completed_at": completed_at or started,
            "status": status,
            "error_classification": error_classification,
        }
        await session.execute(
            insert(ModelRun)
            .values(values)
            .on_conflict_do_update(
                index_elements=[ModelRun.id],
                set_={key: value for key, value in values.items() if key != "id"}
                | {"updated_at": func.now()},
            )
        )
        record = await session.scalar(
            select(ModelRun).where(ModelRun.id == model_run_id)
        )
        if record is None:
            raise RuntimeError("model run was not persisted")
        return record
