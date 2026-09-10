"""Authenticated manual collection trigger orchestration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from hermes_cti.core.settings import Settings
from hermes_cti.db.pipeline import DailyPipeline
from hermes_cti.db.session import Database
from hermes_cti.ingestion.service import IngestionService
from hermes_cti.models.contracts import RunStatus, SourceRegistry

logger = logging.getLogger(__name__)
TriggerStatus = Literal["queued", "running", "lock_busy", "completed", "failed"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ManualCollectionTrigger:
    """In-memory control-plane state for one manually requested collection."""

    trigger_id: UUID
    run_id: UUID
    idempotency_key: str
    total_sources: int
    status: TriggerStatus = "queued"
    queued_at: datetime = field(default_factory=_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    successful_sources: int = 0
    failed_sources: int = 0
    error_summary: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe private status projection."""

        return {
            "scope": "private",
            "trigger_id": str(self.trigger_id),
            "run_id": str(self.run_id),
            "idempotency_key": self.idempotency_key,
            "status": self.status,
            "total_sources": self.total_sources,
            "successful_sources": self.successful_sources,
            "failed_sources": self.failed_sources,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error_summary": self.error_summary,
        }


class CollectionTriggerManager:
    """Queue manual runs while the database lock remains the concurrency guard."""

    def __init__(self) -> None:
        self._triggers: dict[UUID, ManualCollectionTrigger] = {}
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    def submit(
        self,
        settings: Settings,
        database: Database,
        registry: SourceRegistry,
    ) -> ManualCollectionTrigger:
        """Queue one manual run and return its immediately usable identifiers."""

        trigger_id = uuid4()
        idempotency_key = f"manual:{trigger_id}"
        trigger = ManualCollectionTrigger(
            trigger_id=trigger_id,
            run_id=DailyPipeline.run_id(idempotency_key),
            idempotency_key=idempotency_key,
            total_sources=len(registry.sources),
        )
        self._triggers[trigger_id] = trigger
        task = asyncio.create_task(
            self._execute(trigger, settings, database, registry),
            name=f"manual-collection-{trigger_id}",
        )
        self._tasks[trigger_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(trigger_id, None))
        return trigger

    def get(self, trigger_id: UUID) -> ManualCollectionTrigger | None:
        """Return in-memory state for a trigger submitted to this web process."""

        return self._triggers.get(trigger_id)

    async def _execute(
        self,
        trigger: ManualCollectionTrigger,
        settings: Settings,
        database: Database,
        registry: SourceRegistry,
    ) -> None:
        trigger.status = "running"
        trigger.started_at = _now()
        try:
            result = await DailyPipeline(
                settings,
                database,
                ingestion_service=IngestionService(settings, origin="ops-api"),
            ).run_once(registry, idempotency_key=trigger.idempotency_key)
        except Exception:
            trigger.status = "failed"
            trigger.error_summary = "collection failed before completion"
            trigger.completed_at = _now()
            logger.exception(
                "manual collection trigger failed",
                extra={
                    "event": "manual_collection_failed",
                    "component": "ops-api",
                    "trigger_id": str(trigger.trigger_id),
                    "run_id": str(trigger.run_id),
                },
            )
            return

        trigger.completed_at = _now()
        if not result.acquired_lock:
            trigger.status = "lock_busy"
            trigger.error_summary = "another collection is already in progress"
            return

        trigger.status = (
            "completed" if result.run_status is RunStatus.COMPLETED else "failed"
        )
        trigger.successful_sources = result.successful_sources
        trigger.failed_sources = result.failed_sources
        trigger.error_summary = result.error_summary
