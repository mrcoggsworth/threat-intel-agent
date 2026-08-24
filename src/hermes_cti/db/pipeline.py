"""Deterministic daily collection and persistence transaction."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.core.settings import Settings
from hermes_cti.db.repositories import PersistenceRepository
from hermes_cti.db.session import Database
from hermes_cti.extraction import ExtractionConfig, extract_document
from hermes_cti.ingestion.service import CollectionResult, IngestionService
from hermes_cti.models.contracts import SourceRegistry

DAILY_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"hermes-cti:daily-pipeline").digest()[:8], "big", signed=True
)
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class DailyRunResult:
    """Outcome of one lock-protected daily attempt."""

    acquired_lock: bool
    ingestion_run_id: UUID | None = None
    collection: CollectionResult | None = None


class DailyPipeline:
    """Run collection, extraction, and persistence as one durable unit."""

    def __init__(
        self,
        settings: Settings,
        database: Database,
        *,
        ingestion_service: IngestionService | None = None,
        repository: PersistenceRepository | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.ingestion_service = ingestion_service or IngestionService(settings)
        self.repository = repository or PersistenceRepository()
        self.runs = self.repository.runs
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pipeline clock must return an aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def idempotency_key(scheduled_for: datetime) -> str:
        """Return the stable daily key for a UTC schedule instant."""

        if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
            raise ValueError("scheduled_for must be timezone-aware")
        instant = scheduled_for.astimezone(UTC)
        return f"daily:{instant.date().isoformat()}"

    @staticmethod
    def run_id(idempotency_key: str) -> UUID:
        return uuid5(NAMESPACE_URL, f"hermes-cti:ingestion-run:{idempotency_key}")

    async def run_once(
        self,
        registry: SourceRegistry,
        *,
        scheduled_for: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> DailyRunResult:
        scheduled = (scheduled_for or self._now()).astimezone(UTC)
        key = idempotency_key or self.idempotency_key(scheduled)
        run_id = self.run_id(key)

        # Keep the advisory lock connection checked out until unlock completes.
        async with (
            self.database.engine.connect() as connection,
            AsyncSession(
                bind=connection, expire_on_commit=False, autoflush=False
            ) as session,
        ):
            acquired = await self.runs.try_daily_lock(session, DAILY_LOCK_KEY)
            await session.commit()
            if not acquired:
                return DailyRunResult(acquired_lock=False)
            try:
                collection = await self.ingestion_service.collect_once(
                    registry,
                    ingestion_run_id=run_id,
                    idempotency_key=key,
                    scheduled_for=scheduled,
                )
                async with session.begin():
                    await self.repository.persist_collection(
                        session, registry, collection
                    )
                    for document in collection.source_documents:
                        extraction = extract_document(document, ExtractionConfig())
                        observed_at = (
                            collection.manifest.completed_at
                            or collection.manifest.started_at
                        )
                        if observed_at is None:
                            raise ValueError(
                                "completed collection requires a run timestamp"
                            )
                        await self.repository.persist_extraction(
                            session,
                            extraction,
                            collection.manifest.ingestion_run_id,
                            observed_at,
                        )
                return DailyRunResult(
                    acquired_lock=True,
                    ingestion_run_id=collection.manifest.ingestion_run_id,
                    collection=collection,
                )
            finally:
                await self.runs.release_daily_lock(session, DAILY_LOCK_KEY)
                await session.commit()
