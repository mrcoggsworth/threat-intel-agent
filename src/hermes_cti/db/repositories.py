"""Typed PostgreSQL repositories and idempotent persistence operations."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid5

from sqlalchemy import desc, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti import __version__
from hermes_cti.db.entity_models import EntityEvidence
from hermes_cti.db.models import (
    EnrichmentResult as EnrichmentResultRecord,
)
from hermes_cti.db.models import (
    EvidenceClaim,
    Indicator,
    IndicatorObservation,
    IngestionRun,
    RawArtifact,
    Report,
    RiskAssessment,
    Source,
    SourceConfigurationHistory,
    SourceRun,
    Vulnerability,
)
from hermes_cti.db.models import (
    SourceDocument as SourceDocumentRecord,
)
from hermes_cti.db.vulnerability_repository import VulnerabilityRepository
from hermes_cti.extraction.contracts import ExtractionResult
from hermes_cti.ingestion.service import CollectionResult
from hermes_cti.models.contracts import (
    IngestionRunManifest,
    PriorityScore,
    ProviderResponse,
    RawArtifactMetadata,
    RunStatus,
    SourceConfig,
    SourceDocument,
    SourceRegistry,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("database timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _source_configuration_snapshot(
    source: SourceConfig,
) -> tuple[dict[str, Any], str]:
    payload = source.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _document_identity(document: SourceDocument) -> str:
    return document.external_source_id or str(document.canonical_url)


class RunRepository:
    """Run state, advisory lock, stale-run, and public publication queries."""

    async def try_daily_lock(self, session: AsyncSession, lock_key: int) -> bool:
        result = await session.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"), {"lock_key": lock_key}
        )
        return bool(result.scalar_one())

    async def release_daily_lock(self, session: AsyncSession, lock_key: int) -> None:
        await session.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": lock_key}
        )

    async def by_idempotency_key(
        self, session: AsyncSession, idempotency_key: str
    ) -> IngestionRun | None:
        result = await session.execute(
            select(IngestionRun).where(IngestionRun.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def last_successful(self, session: AsyncSession) -> IngestionRun | None:
        result = await session.execute(
            select(IngestionRun)
            .where(
                (
                    (IngestionRun.status == RunStatus.COMPLETED.value)
                    | (
                        (IngestionRun.status == RunStatus.FAILED.value)
                        & (IngestionRun.successful_sources > 0)
                    )
                ),
                IngestionRun.completed_at.is_not(None),
            )
            .order_by(desc(IngestionRun.completed_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def stale_runs(
        self, session: AsyncSession, *, older_than: datetime
    ) -> tuple[IngestionRun, ...]:
        cutoff = _utc(older_than)
        result = await session.execute(
            select(IngestionRun)
            .where(
                IngestionRun.status.in_(
                    (RunStatus.SCHEDULED.value, RunStatus.RUNNING.value)
                ),
                IngestionRun.started_at < cutoff,
            )
            .order_by(IngestionRun.started_at, IngestionRun.id)
        )
        return tuple(result.scalars().all())

    async def public_reports(self, session: AsyncSession) -> tuple[Report, ...]:
        """Return only published reports for the public read-only surface."""

        result = await session.execute(
            select(Report)
            .where(Report.state == "published")
            .order_by(desc(Report.last_updated_at), Report.id)
        )
        return tuple(result.scalars().all())

    async def vulnerability_ids_for_run(
        self, session: AsyncSession, ingestion_run_id: UUID
    ) -> tuple[tuple[UUID, str], ...]:
        """Return CVEs evidenced by documents retained in one ingestion run."""
        result = await session.execute(
            select(Vulnerability.id, Vulnerability.cve_id)
            .join(
                EvidenceClaim,
                EvidenceClaim.subject_entity_id == Vulnerability.id,
            )
            .join(
                SourceDocumentRecord,
                SourceDocumentRecord.id == EvidenceClaim.source_document_id,
            )
            .join(
                RawArtifact,
                RawArtifact.id == SourceDocumentRecord.raw_artifact_id,
            )
            .where(RawArtifact.ingestion_run_id == ingestion_run_id)
            .order_by(Vulnerability.cve_id, Vulnerability.id)
        )
        return tuple((cast(UUID, row[0]), cast(str, row[1])) for row in result.all())

    async def failed_source_ids(
        self, session: AsyncSession, ingestion_run_id: UUID
    ) -> tuple[str, ...]:
        result = await session.execute(
            select(SourceRun.source_id)
            .where(
                SourceRun.ingestion_run_id == ingestion_run_id,
                SourceRun.status == RunStatus.FAILED.value,
            )
            .order_by(SourceRun.source_id)
        )
        return tuple(result.scalars().all())


class PersistenceRepository:
    """Repository for the Phase 4 evidence and deterministic observation slice."""

    def __init__(self, runs: RunRepository | None = None) -> None:
        self.runs = runs or RunRepository()

    async def upsert_source(
        self, session: AsyncSession, source: SourceConfig
    ) -> Source:
        configuration, configuration_hash = _source_configuration_snapshot(source)
        existing = await session.scalar(
            select(Source).where(Source.source_id == source.source_id)
        )
        history = await session.scalar(
            select(SourceConfigurationHistory).where(
                SourceConfigurationHistory.source_id == source.source_id,
                SourceConfigurationHistory.configuration_hash == configuration_hash,
            )
        )
        configuration_version = (
            history.configuration_version
            if history is not None
            else (existing.configuration_version + 1 if existing is not None else 1)
        )
        values = {
            "source_id": source.source_id,
            "name": source.name,
            "source_type": source.source_type.value,
            "canonical_base_url": str(source.url),
            "category": source.category.value,
            "enabled": source.enabled,
            "reliability": source.reliability.value,
            "polling_interval_seconds": source.polling_interval_seconds,
            "timeout_seconds": source.timeout_seconds,
            "max_response_bytes": source.max_response_bytes,
            "tags": list(source.tags),
            "configuration_version": configuration_version,
        }
        statement = insert(Source).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in values.items() if key != "source_id"},
        )
        await session.execute(statement)
        if history is None:
            history_id = uuid5(
                UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8"),
                f"source-config:{source.source_id}:{configuration_hash}",
            )
            await session.execute(
                insert(SourceConfigurationHistory)
                .values(
                    id=history_id,
                    source_id=source.source_id,
                    configuration_version=configuration_version,
                    configuration_hash=configuration_hash,
                    configuration=configuration,
                    recorded_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        SourceConfigurationHistory.source_id,
                        SourceConfigurationHistory.configuration_hash,
                    ]
                )
            )
        result = await session.execute(
            select(Source).where(Source.source_id == source.source_id)
        )
        return result.scalar_one()

    async def create_or_get_run(
        self, session: AsyncSession, manifest: IngestionRunManifest
    ) -> IngestionRun:
        existing = await self.runs.by_idempotency_key(session, manifest.idempotency_key)
        if existing is not None:
            return existing
        values: dict[str, Any] = {
            "id": manifest.ingestion_run_id,
            "run_type": manifest.run_type,
            "idempotency_key": manifest.idempotency_key,
            "scheduled_for": manifest.scheduled_for,
            "started_at": manifest.started_at,
            "completed_at": None,
            "status": RunStatus.RUNNING.value,
            "triggering_origin": manifest.triggering_origin,
            "application_version": manifest.application_version or __version__,
            "configuration_hash": manifest.configuration_hash,
            "total_sources": manifest.total_sources,
        }
        statement = (
            insert(IngestionRun)
            .values(values)
            .on_conflict_do_nothing(index_elements=[IngestionRun.idempotency_key])
        )
        await session.execute(statement)
        record = await self.runs.by_idempotency_key(session, manifest.idempotency_key)
        if record is None:
            raise RuntimeError("ingestion run was not created or found")
        return record

    async def persist_collection(
        self,
        session: AsyncSession,
        registry: SourceRegistry,
        collection: CollectionResult,
    ) -> IngestionRun:
        """Persist one complete collection atomically, including partial outcomes."""

        manifest = collection.manifest
        run = await self.create_or_get_run(session, manifest)
        if (
            run.status == RunStatus.COMPLETED.value
            and run.completed_at is not None
        ):
            return run
        for source_config in registry.sources:
            await self.upsert_source(session, source_config)
        for result in manifest.source_results:
            await session.merge(
                SourceRun(
                    ingestion_run_id=run.id,
                    source_id=result.source_id,
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                    status=result.status.value,
                    http_status=result.http_status,
                    item_count=result.item_count,
                    retry_count=result.retry_count,
                    cache_state=result.cache_state.value,
                    error_classification=result.error_classification,
                    error_detail=result.error_detail,
                )
            )
        for artifact in collection.raw_artifacts:
            await self.persist_raw_artifact(session, artifact)
        for document in collection.source_documents:
            await self.persist_source_document(session, document)
        run.status = manifest.status.value
        run.started_at = manifest.started_at
        run.completed_at = manifest.completed_at
        run.successful_sources = manifest.successful_sources
        run.failed_sources = manifest.failed_sources
        run.new_documents = manifest.new_documents
        run.changed_documents = manifest.changed_documents
        run.unchanged_documents = manifest.unchanged_documents
        run.error_summary = manifest.error_summary
        return run

    async def persist_raw_artifact(
        self,
        session: AsyncSession,
        artifact: RawArtifactMetadata,
        payload: bytes | None = None,
    ) -> RawArtifact:
        values = {
            "id": artifact.raw_artifact_id,
            "source_id": artifact.source_id,
            "retrieval_url": str(artifact.retrieval_url),
            "canonical_url": str(artifact.canonical_url),
            "retrieved_at": artifact.retrieved_at,
            "response_status": artifact.response_status,
            "content_type": artifact.content_type,
            "encoding": artifact.encoding,
            "etag": artifact.etag,
            "last_modified": artifact.last_modified,
            "content_hash": artifact.content_hash,
            "byte_length": artifact.byte_length,
            "storage_locator": artifact.storage_locator,
            "retention_policy": artifact.retention_policy,
            "retention_expires_at": artifact.retention_expires_at,
            "storage_state": artifact.storage_state,
            "payload": payload,
            "ingestion_run_id": artifact.ingestion_run_id,
        }
        await session.execute(
            insert(RawArtifact)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    RawArtifact.source_id,
                    RawArtifact.canonical_url,
                    RawArtifact.content_hash,
                ]
            )
        )
        result = await session.execute(
            select(RawArtifact).where(
                RawArtifact.source_id == artifact.source_id,
                RawArtifact.canonical_url == str(artifact.canonical_url),
                RawArtifact.content_hash == artifact.content_hash,
            )
        )
        return result.scalar_one()

    async def persist_source_document(
        self, session: AsyncSession, document: SourceDocument
    ) -> SourceDocumentRecord:
        identity_key = _document_identity(document)
        existing = await session.scalar(
            select(SourceDocumentRecord).where(
                SourceDocumentRecord.source_id == document.source_id,
                SourceDocumentRecord.identity_key == identity_key,
                SourceDocumentRecord.normalized_content_hash
                == document.normalized_content_hash,
            )
        )
        if existing is not None:
            return existing
        latest = await session.scalar(
            select(SourceDocumentRecord)
            .where(
                SourceDocumentRecord.source_id == document.source_id,
                SourceDocumentRecord.identity_key == identity_key,
            )
            .order_by(desc(SourceDocumentRecord.document_version))
            .limit(1)
        )
        record = SourceDocumentRecord(
            id=document.source_document_id,
            source_id=document.source_id,
            raw_artifact_id=document.raw_artifact_id,
            external_source_id=document.external_source_id,
            identity_key=identity_key,
            canonical_url=str(document.canonical_url),
            title=document.title,
            authors=list(document.authors),
            published_at=document.published_at,
            updated_at_source=document.updated_at_source,
            retrieved_at=document.retrieved_at,
            content_type=document.content_type,
            normalized_text=document.normalized_text,
            sanitized_summary=document.sanitized_summary,
            language=document.language,
            document_type=document.document_type.value,
            normalized_content_hash=document.normalized_content_hash,
            supersedes_id=latest.id if latest else document.supersedes_id,
            document_version=(latest.document_version + 1) if latest else 1,
            parse_version=document.parse_version,
        )
        session.add(record)
        await session.flush()
        return record

    async def persist_provider_response(
        self, session: AsyncSession, response: ProviderResponse
    ) -> EnrichmentResultRecord:
        values: dict[str, Any] = {
            "id": uuid5(
                UUID("6ba7b812-9dad-11d1-80b4-00c04fd430c8"),
                f"enrichment:{response.provider}:{response.request.query_key}:"
                f"{response.payload_hash or response.retrieved_at.isoformat()}",
            ),
            "entity_type": response.request.entity.entity_type.value,
            "entity_id": response.request.entity.entity_id,
            "provider": response.provider,
            "provider_query_key": response.request.query_key,
            "retrieved_at": response.retrieved_at,
            "expires_at": response.expires_at,
            "status": response.status.value,
            "normalized_result": response.normalized_result,
            "raw_metadata": response.raw_metadata.model_dump(
                mode="json", exclude_none=True
            ),
            "raw_payload_hash": response.payload_hash,
            "cache_hit": response.cache_hit,
            "error_classification": (
                response.error_classification.value
                if response.error_classification
                else None
            ),
            "quota_metadata": response.raw_metadata.model_dump(
                mode="json",
                exclude_none=True,
                include={"quota_remaining", "quota_reset_at"},
            ),
        }
        statement = (
            insert(EnrichmentResultRecord)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    EnrichmentResultRecord.provider,
                    EnrichmentResultRecord.provider_query_key,
                    EnrichmentResultRecord.raw_payload_hash,
                ]
            )
        )
        await session.execute(statement)
        result = await session.execute(
            select(EnrichmentResultRecord).where(
                EnrichmentResultRecord.id == values["id"]
            )
        )
        record = result.scalar_one_or_none()
        if record is not None:
            await session.execute(
                insert(EntityEvidence)
                .values(
                    id=uuid5(record.id, "provider-evidence"),
                    entity_type=response.request.entity.entity_type.value,
                    entity_id=response.request.entity.entity_id,
                    provider_result_id=record.id,
                    confidence=1.0,
                    origin_type="provider_enrichment",
                    content_hash=response.payload_hash,
                )
                .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
            )
            return record
        record = await session.scalar(
            select(EnrichmentResultRecord)
            .where(
                EnrichmentResultRecord.provider == response.provider,
                EnrichmentResultRecord.provider_query_key == response.request.query_key,
                EnrichmentResultRecord.raw_payload_hash == response.payload_hash,
            )
            .order_by(desc(EnrichmentResultRecord.retrieved_at))
            .limit(1)
        )
        if record is None:
            raise RuntimeError("enrichment result was not persisted")
        await session.execute(
            insert(EntityEvidence)
            .values(
                id=uuid5(record.id, "provider-evidence"),
                entity_type=response.request.entity.entity_type.value,
                entity_id=response.request.entity.entity_id,
                provider_result_id=record.id,
                confidence=1.0,
                origin_type="provider_enrichment",
                content_hash=response.payload_hash,
            )
            .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
        )
        return cast(EnrichmentResultRecord, record)

    async def persist_risk_assessment(
        self,
        session: AsyncSession,
        *,
        entity_type: str,
        entity_id: UUID,
        priority: PriorityScore,
        evidence_ids: tuple[UUID, ...] = (),
        origin: str = "deterministic_enrichment",
    ) -> RiskAssessment:
        latest = await session.scalar(
            select(RiskAssessment)
            .where(
                RiskAssessment.entity_type == entity_type,
                RiskAssessment.entity_id == entity_id,
            )
            .order_by(desc(RiskAssessment.assessment_version))
            .limit(1)
        )
        version = (latest.assessment_version + 1) if latest else 1
        breakdown = {
            "score": priority.score,
            "score_version": priority.score_version,
            "severity": priority.severity.value,
            "confidence": priority.confidence,
            "components": [
                component.model_dump(exclude_none=True)
                for component in priority.components
            ],
        }
        record = RiskAssessment(
            id=uuid5(
                UUID("6ba7b813-9dad-11d1-80b4-00c04fd430c8"),
                f"risk:{entity_type}:{entity_id}:{priority.score_version}:{version}",
            ),
            entity_type=entity_type,
            entity_id=entity_id,
            assessment_version=version,
            score=priority.score,
            score_version=priority.score_version,
            severity=priority.severity.value,
            component_breakdown=breakdown,
            evidence_ids=[
                str(value) for value in evidence_ids or priority.evidence_ids
            ],
            origin=origin,
            priority_explanation="; ".join(
                f"{component.name}: {component.rationale}"
                for component in priority.components
            ),
            review_state="proposed",
            supersedes_id=latest.id if latest else None,
        )
        session.add(record)
        await session.flush()
        for evidence_id in set(evidence_ids or priority.evidence_ids):
            claim_exists = await session.scalar(
                select(EvidenceClaim.id).where(EvidenceClaim.id == evidence_id)
            )
            if claim_exists is None:
                continue
            await session.execute(
                insert(EntityEvidence)
                .values(
                    id=uuid5(record.id, f"evidence:{evidence_id}"),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    evidence_claim_id=evidence_id,
                    confidence=priority.confidence,
                    origin_type=origin,
                )
                .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
            )
        return record

    async def persist_enrichment_run(
        self,
        session: AsyncSession,
        *,
        provider_responses: tuple[ProviderResponse, ...],
        entity_type: str,
        entity_id: UUID,
        priority: PriorityScore | None = None,
        evidence_ids: tuple[UUID, ...] = (),
    ) -> tuple[tuple[EnrichmentResultRecord, ...], RiskAssessment | None]:
        records = tuple(
            [
                await self.persist_provider_response(session, response)
                for response in provider_responses
            ]
        )
        if entity_type == "vulnerability":
            await VulnerabilityRepository().persist_enrichment(
                session,
                entity_id=entity_id,
                provider_responses=provider_responses,
                provider_records=records,
            )
        assessment = (
            await self.persist_risk_assessment(
                session,
                entity_type=entity_type,
                entity_id=entity_id,
                priority=priority,
                evidence_ids=evidence_ids,
            )
            if priority is not None
            else None
        )
        return records, assessment

    async def persist_extraction(
        self,
        session: AsyncSession,
        result: ExtractionResult,
        ingestion_run_id: UUID,
        observed_at: datetime,
    ) -> None:
        observed = _utc(observed_at)
        for observation in result.observations:
            indicator_id = uuid5(
                UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),
                f"indicator:{observation.indicator_type.value}:{observation.normalized_value}",
            )
            await session.execute(
                insert(Indicator)
                .values(
                    id=indicator_id,
                    indicator_type=observation.indicator_type.value,
                    normalized_value=observation.normalized_value,
                    safe_display_value=observation.normalized_value,
                    first_seen_at=observed,
                    last_seen_at=observed,
                    validation_state=observation.validation_state.value,
                    public_visibility=False,
                )
                .on_conflict_do_update(
                    index_elements=[
                        Indicator.indicator_type,
                        Indicator.normalized_value,
                    ],
                    set_={"last_seen_at": observed},
                )
            )
            await session.execute(
                insert(IndicatorObservation)
                .values(
                    id=observation.observation_id,
                    indicator_id=indicator_id,
                    source_document_id=observation.source_document_id,
                    ingestion_run_id=ingestion_run_id,
                    observed_at=observed,
                    start_offset=observation.start_offset,
                    end_offset=observation.end_offset,
                    evidence_text=observation.original_display_value,
                    context=observation.context,
                    confidence=1.0,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        IndicatorObservation.indicator_id,
                        IndicatorObservation.source_document_id,
                        IndicatorObservation.start_offset,
                        IndicatorObservation.end_offset,
                    ]
                )
            )
            await session.execute(
                insert(EntityEvidence)
                .values(
                    id=uuid5(
                        UUID("6ba7b814-9dad-11d1-80b4-00c04fd430c8"),
                        f"indicator-evidence:{observation.observation_id}",
                    ),
                    entity_type="indicator",
                    entity_id=indicator_id,
                    source_document_id=observation.source_document_id,
                    evidence_span={
                        "start_offset": observation.start_offset,
                        "end_offset": observation.end_offset,
                        "text": observation.original_display_value,
                    },
                    first_seen_at=observed,
                    last_seen_at=observed,
                    confidence=1.0,
                    origin_type="deterministic_extraction",
                )
                .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
            )
        for candidate in result.cve_candidates:
            vulnerability_id = uuid5(
                UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"),
                f"vulnerability:{candidate.normalized_value}",
            )
            await session.execute(
                insert(Vulnerability)
                .values(id=vulnerability_id, cve_id=candidate.normalized_value)
                .on_conflict_do_nothing(index_elements=[Vulnerability.cve_id])
            )
            await session.execute(
                insert(EvidenceClaim)
                .values(
                    id=candidate.candidate_id,
                    source_document_id=candidate.source_document_id,
                    claim_type="cve_candidate",
                    subject_entity_type="vulnerability",
                    subject_entity_id=vulnerability_id,
                    predicate="mentioned_in",
                    object_literal=candidate.normalized_value,
                    evidence_text=candidate.original_display_value,
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                    extraction_origin=candidate.extraction_rule,
                    confidence=1.0,
                )
                .on_conflict_do_nothing(index_elements=[EvidenceClaim.id])
            )
            await session.execute(
                insert(EntityEvidence)
                .values(
                    id=uuid5(
                        UUID("6ba7b815-9dad-11d1-80b4-00c04fd430c8"),
                        f"vulnerability-evidence:{candidate.candidate_id}",
                    ),
                    entity_type="vulnerability",
                    entity_id=vulnerability_id,
                    source_document_id=candidate.source_document_id,
                    evidence_claim_id=candidate.candidate_id,
                    evidence_span={
                        "start_offset": candidate.start_offset,
                        "end_offset": candidate.end_offset,
                        "text": candidate.original_display_value,
                    },
                    first_seen_at=observed,
                    last_seen_at=observed,
                    confidence=1.0,
                    origin_type="deterministic_extraction",
                )
                .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
            )


async def stale_run_cutoff(
    session: AsyncSession, *, now: datetime, max_age: timedelta
) -> tuple[IngestionRun, ...]:
    """Typed convenience query for operational stale-run checks."""

    return await RunRepository().stale_runs(session, older_than=_utc(now) - max_age)
