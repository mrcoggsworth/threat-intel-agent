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
from hermes_cti.enrichment import EnrichmentCache, EnrichmentService, build_providers
from hermes_cti.extraction import ExtractionConfig, extract_document
from hermes_cti.ingestion.service import CollectionResult, IngestionService
from hermes_cti.models.contracts import RunStatus, SourceRegistry

DAILY_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"hermes-cti:daily-pipeline").digest()[:8], "big", signed=True
)
Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class EnrichmentFailure:
    """One CVE whose enrichment could not be completed."""

    cve_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class EnrichmentStageResult:
    """Outcome of the post-extraction enrichment stage.

    Counts are derived from real work performed, never asserted totals.
    ``truncated`` is surfaced explicitly so a configured cap can never
    silently under-report coverage.
    """

    attempted: int = 0
    enriched: int = 0
    failures: int = 0
    truncated: bool = False
    failed: tuple[EnrichmentFailure, ...] = ()


@dataclass(frozen=True, slots=True)
class DailyRunResult:
    """Outcome of one lock-protected daily attempt."""

    acquired_lock: bool
    ingestion_run_id: UUID | None = None
    collection: CollectionResult | None = None
    run_status: RunStatus | None = None
    total_sources: int = 0
    successful_sources: int = 0
    failed_sources: int = 0
    error_summary: str | None = None
    enrichment: EnrichmentStageResult = EnrichmentStageResult()

    @property
    def is_full_success(self) -> bool:
        """Whether the persisted parent run completed with full coverage."""

        return (
            self.run_status is RunStatus.COMPLETED
            and self.total_sources > 0
            and self.failed_sources == 0
            and self.successful_sources == self.total_sources
        )

    @property
    def is_usable(self) -> bool:
        """Whether at least one source produced usable results."""

        return (
            self.run_status in (RunStatus.COMPLETED, RunStatus.FAILED)
            and self.successful_sources > 0
        )


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

    def _build_enrichment_service(self) -> EnrichmentService:
        """Construct the pipeline enrichment service from settings.

        Returns a service whose providers are built from the active settings,
        matching the construction used by the ``db enrich`` CLI command so
        automated and manual enrichment behave identically.
        """

        return EnrichmentService(
            build_providers(self.settings),
            cache=EnrichmentCache(
                stale_if_error_seconds=self.settings.enrichment_stale_if_error_seconds
            ),
        )

    async def _enrich_run_cves(
        self,
        *,
        run_id: UUID,
        runs: object | None = None,
        enrichment: EnrichmentService | None = None,
        persist: object | None = None,
    ) -> EnrichmentStageResult:
        """Enrich the CVEs evidenced by one run, bounded and degrade-and-continue.

        The stage is inert unless ``enrichment_pipeline_enabled`` is set, so
        enabling it is an explicit operational decision. Each CVE is persisted
        in its own transaction: a provider failure, a rate limit, or an
        unexpected exception records a failure for that CVE and continues with
        the rest, so one bad CVE can never abort the run or its siblings.

        The number of CVEs processed is bounded by
        ``enrichment_max_cves_per_run``. When the bound is reached the result
        reports ``truncated=True`` so the shortfall is never silent.
        """

        enabled = (
            self.settings.enrichment_enabled
            and self.settings.enrichment_pipeline_enabled
        )
        if not enabled:
            return EnrichmentStageResult()

        run_repository = runs if runs is not None else self.runs
        service = (
            enrichment if enrichment is not None else self._build_enrichment_service()
        )
        repository = persist if persist is not None else PersistenceRepository()

        async with self.database.session() as session:
            pairs = await run_repository.vulnerability_ids_for_run(session, run_id)  # type: ignore[attr-defined]

        attempted = len(pairs)
        cap = max(0, int(self.settings.enrichment_max_cves_per_run))
        selected = pairs[:cap]
        truncated = attempted > cap

        enriched = 0
        failures: list[EnrichmentFailure] = []
        try:
            for entity_id, cve_id in selected:
                try:
                    result = await service.enrich_cve(cve_id, entity_id)
                    async with self.database.transaction() as session:
                        await repository.persist_enrichment_run(  # type: ignore[attr-defined]
                            session,
                            provider_responses=result.provider_results,
                            entity_type=result.entity.entity_type.value,
                            entity_id=result.entity.entity_id,
                            priority=result.priority,
                        )
                    enriched += 1
                except Exception as exc:  # noqa: BLE001 - degrade and continue
                    failures.append(
                        EnrichmentFailure(
                            cve_id=cve_id,
                            reason=f"{type(exc).__name__}: {exc}"[:500],
                        )
                    )
        finally:
            if enrichment is None:
                for provider in service.providers:
                    await provider.aclose()

        return EnrichmentStageResult(
            attempted=attempted,
            enriched=enriched,
            failures=len(failures),
            truncated=truncated,
            failed=tuple(failures),
        )

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
                    (
                        run,
                        persisted_documents,
                    ) = await self.repository.persist_collection_with_documents(
                        session, registry, collection
                    )
                    if not persisted_documents:
                        return DailyRunResult(
                            acquired_lock=True,
                            ingestion_run_id=run.id,
                            collection=collection,
                            run_status=RunStatus(run.status),
                            total_sources=run.total_sources,
                            successful_sources=run.successful_sources,
                            failed_sources=run.failed_sources,
                            error_summary=run.error_summary,
                        )
                    new_findings = 0
                    for document, persisted_document in zip(
                        collection.source_documents, persisted_documents, strict=True
                    ):
                        extraction_document = document.model_copy(
                            update={"source_document_id": persisted_document.id}
                        )
                        extraction = extract_document(
                            extraction_document, ExtractionConfig()
                        )
                        observed_at = (
                            collection.manifest.completed_at
                            or collection.manifest.started_at
                        )
                        if observed_at is None:
                            raise ValueError(
                                "completed collection requires a run timestamp"
                            )
                        new_findings += await self.repository.persist_extraction(
                            session,
                            extraction,
                            run.id,
                            observed_at,
                        )
                    run.new_findings = new_findings
                # Enrichment runs after the collection/extraction transaction
                # commits. It performs slow, rate-limited network calls and
                # persists each CVE in its own transaction, so it must never
                # hold this transaction open or be able to roll the collection
                # back. Failures are recorded and the run still completes.
                enrichment_summary = await self._enrich_run_cves(run_id=run.id)
                return DailyRunResult(
                    acquired_lock=True,
                    ingestion_run_id=run.id,
                    collection=collection,
                    run_status=RunStatus(run.status),
                    total_sources=run.total_sources,
                    successful_sources=run.successful_sources,
                    failed_sources=run.failed_sources,
                    error_summary=run.error_summary,
                    enrichment=enrichment_summary,
                )
            finally:
                await self.runs.release_daily_lock(session, DAILY_LOCK_KEY)
                await session.commit()
