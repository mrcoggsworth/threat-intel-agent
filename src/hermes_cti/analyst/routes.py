"""Authenticated analyst read and controlled submission routes."""
# ruff: noqa: B008

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert

from hermes_cti.analyst.contracts import (
    AnalystClaim,
    AnalystDocument,
    AnalystEvidenceResponse,
    AnalystIndicator,
    AnalystProposalResponse,
    AnalystReportSubmission,
    AnalystRun,
    AnalystRunResponse,
    AnalystSourceRun,
    AnalystStatus,
    AnalystSubmissionResponse,
)
from hermes_cti.api.dependencies import (
    get_database,
    require_analyst_token,
)
from hermes_cti.correlation import CorrelationService
from hermes_cti.correlation.repository import CorrelationRepository
from hermes_cti.db.models import (
    EvidenceClaim,
    Indicator,
    IndicatorObservation,
    IngestionRun,
    OperationalEvent,
    RawArtifact,
    Report,
    ReportVersion,
    SourceDocument,
    SourceRun,
)
from hermes_cti.db.session import Database
from hermes_cti.models.contracts import RelationshipProposal, ReportState, RunStatus
from hermes_cti.reporting.contracts import ReportBundle, ValidationManifest
from hermes_cti.reporting.service import ReportPipeline

router = APIRouter(
    prefix="/api/v1/analyst",
    tags=["analyst"],
    dependencies=[Depends(require_analyst_token)],
)


async def _record_event(
    session: Any,
    *,
    event_id: UUID,
    event_type: str,
    run_id: UUID | None,
    payload: dict[str, object],
) -> None:
    """Write a secret-free, retry-safe audit record in the same transaction."""

    await session.execute(
        insert(OperationalEvent)
        .values(
            id=event_id,
            event_type=event_type,
            severity="info",
            component="analyst_api",
            run_id=run_id,
            occurred_at=datetime.now(UTC),
            payload=payload,
            public_safe=False,
        )
        .on_conflict_do_nothing(index_elements=[OperationalEvent.id])
    )


def _run_model(run: IngestionRun, source_runs: tuple[SourceRun, ...]) -> AnalystRun:
    return AnalystRun(
        ingestion_run_id=run.id,
        run_type=run.run_type,
        status=RunStatus(run.status),
        scheduled_for=run.scheduled_for,
        started_at=run.started_at,
        completed_at=run.completed_at,
        triggering_origin=run.triggering_origin,
        application_version=run.application_version,
        total_sources=run.total_sources,
        successful_sources=run.successful_sources,
        failed_sources=run.failed_sources,
        new_documents=run.new_documents,
        changed_documents=run.changed_documents,
        unchanged_documents=run.unchanged_documents,
        new_findings=run.new_findings,
        error_summary=run.error_summary,
        source_runs=tuple(
            AnalystSourceRun(
                source_id=item.source_id,
                status=RunStatus(item.status),
                started_at=item.started_at,
                completed_at=item.completed_at,
                http_status=item.http_status,
                item_count=item.item_count,
                retry_count=item.retry_count,
                cache_state=item.cache_state,
                error_classification=item.error_classification,
            )
            for item in source_runs
        ),
    )


async def _latest_run(database: Database) -> IngestionRun | None:
    async with database.session() as session:
        return cast(
            IngestionRun | None,
            await session.scalar(
                select(IngestionRun)
                .where(
                    (IngestionRun.status == RunStatus.COMPLETED.value)
                    | (
                        (IngestionRun.status == RunStatus.FAILED.value)
                        & (IngestionRun.successful_sources > 0)
                    )
                )
                .order_by(desc(IngestionRun.completed_at), desc(IngestionRun.id))
                .limit(1)
            ),
        )


async def _run_with_sources(database: Database, run: IngestionRun) -> AnalystRun:
    async with database.session() as session:
        result = await session.execute(
            select(SourceRun)
            .where(SourceRun.ingestion_run_id == run.id)
            .order_by(SourceRun.source_id)
        )
        return _run_model(run, tuple(result.scalars().all()))


@router.get("/status", response_model=AnalystStatus)
async def analyst_status(
    request: Request, database: Database = Depends(get_database)
) -> AnalystStatus:
    readiness = await request.app.state.readiness_checker.check()
    run = await _latest_run(database) if readiness.database == "ok" else None
    heartbeat_file = request.app.state.settings.scheduler_heartbeat_file
    heartbeat: str | None = None
    if heartbeat_file:
        try:
            heartbeat = Path(heartbeat_file).read_text(encoding="utf-8").strip() or None
        except OSError:
            heartbeat = None
    return AnalystStatus(
        status="ready" if readiness.healthy else "unhealthy",
        application_version=request.app.state.settings.app_version,
        database=readiness.database,
        scheduler_heartbeat=heartbeat,
        latest_completed_run_id=run.id if run else None,
        latest_completed_at=run.completed_at if run else None,
    )


@router.get("/runs/latest", response_model=AnalystRunResponse)
async def latest_run(database: Database = Depends(get_database)) -> AnalystRunResponse:
    run = await _latest_run(database)
    return AnalystRunResponse(
        run=await _run_with_sources(database, run) if run is not None else None
    )


@router.get("/runs/{run_id}", response_model=AnalystRunResponse)
async def run_detail(
    run_id: UUID, database: Database = Depends(get_database)
) -> AnalystRunResponse:
    async with database.session() as session:
        run = await session.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ingestion run not found")
    return AnalystRunResponse(run=await _run_with_sources(database, run))


@router.get("/evidence", response_model=AnalystEvidenceResponse)
async def evidence(
    run_id: UUID | None = None,
    source_id: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=2000),
    max_chars: int = Query(default=20000, ge=1000, le=100000),
    database: Database = Depends(get_database),
) -> AnalystEvidenceResponse:
    selected_run = run_id
    if selected_run is None:
        latest = await _latest_run(database)
        selected_run = latest.id if latest is not None else None
    if selected_run is None:
        return AnalystEvidenceResponse()

    async with database.session() as session:
        doc_query = select(SourceDocument).join(
            RawArtifact, RawArtifact.id == SourceDocument.raw_artifact_id
        )
        if selected_run is not None:
            active_sources = select(SourceRun.source_id).where(
                SourceRun.ingestion_run_id == selected_run,
                SourceRun.status == "completed",
            )
            doc_query = doc_query.where(
                (RawArtifact.ingestion_run_id == selected_run)
                | (SourceDocument.source_id.in_(active_sources))
            )
        if source_id is not None:
            doc_query = doc_query.where(SourceDocument.source_id == source_id)
        document_result = await session.execute(
            doc_query.order_by(desc(SourceDocument.retrieved_at), SourceDocument.id)
            .offset(offset)
            .limit(limit)
        )
        documents = tuple(document_result.scalars().all())
        document_ids = tuple(item.id for item in documents)
        if not document_ids:
            return AnalystEvidenceResponse(ingestion_run_id=selected_run)

        claim_result = await session.execute(
            select(EvidenceClaim)
            .where(EvidenceClaim.source_document_id.in_(document_ids))
            .order_by(EvidenceClaim.source_document_id, EvidenceClaim.id)
            .limit(limit * 20)
        )
        ind_query = select(IndicatorObservation, Indicator).join(
            Indicator, Indicator.id == IndicatorObservation.indicator_id
        )
        if selected_run is not None:
            active_sources = select(SourceRun.source_id).where(
                SourceRun.ingestion_run_id == selected_run,
                SourceRun.status == "completed",
            )
            ind_query = ind_query.where(
                (IndicatorObservation.ingestion_run_id == selected_run)
                | (
                    IndicatorObservation.source_document_id.in_(
                        select(SourceDocument.id).where(
                            SourceDocument.source_id.in_(active_sources)
                        )
                    )
                )
            )
        if source_id is not None:
            ind_query = ind_query.where(
                IndicatorObservation.source_document_id.in_(
                    select(SourceDocument.id).where(
                        SourceDocument.source_id == source_id
                    )
                )
            )
        indicator_result = await session.execute(
            ind_query.order_by(
                IndicatorObservation.source_document_id,
                IndicatorObservation.id,
            ).limit(limit * 20)
        )

    document_payload = tuple(
        AnalystDocument(
            source_document_id=item.id,
            source_id=item.source_id,
            external_source_id=item.external_source_id,
            canonical_url=item.canonical_url,
            title=item.title,
            published_at=item.published_at,
            updated_at_source=item.updated_at_source,
            retrieved_at=item.retrieved_at,
            content_type=item.content_type,
            document_type=item.document_type,
            normalized_content_hash=item.normalized_content_hash,
            sanitized_summary=item.sanitized_summary,
            normalized_text=item.normalized_text[:max_chars],
            text_truncated=len(item.normalized_text) > max_chars,
        )
        for item in documents
    )
    claim_payload = tuple(
        AnalystClaim(
            evidence_id=item.id,
            source_document_id=item.source_document_id,
            claim_type=item.claim_type,
            subject_entity_type=item.subject_entity_type,
            subject_entity_id=item.subject_entity_id,
            predicate=item.predicate,
            object_entity_type=item.object_entity_type,
            object_entity_id=item.object_entity_id,
            object_literal=item.object_literal,
            evidence_text=item.evidence_text,
            start_offset=item.start_offset,
            end_offset=item.end_offset,
            extraction_origin=item.extraction_origin,
            confidence=item.confidence,
        )
        for item in claim_result.scalars().all()
    )
    indicator_payload = tuple(
        AnalystIndicator(
            observation_id=observation.id,
            source_document_id=observation.source_document_id,
            indicator_type=indicator.indicator_type,
            value=indicator.safe_display_value,
            validation_state=indicator.validation_state,
            evidence_text=observation.evidence_text,
            context=observation.context,
            confidence=observation.confidence,
        )
        for observation, indicator in indicator_result.all()
    )
    return AnalystEvidenceResponse(
        ingestion_run_id=selected_run,
        documents=document_payload,
        claims=claim_payload,
        indicators=indicator_payload,
    )


@router.post(
    "/proposals",
    response_model=AnalystProposalResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_proposal(
    proposal: RelationshipProposal, database: Database = Depends(get_database)
) -> AnalystProposalResponse:
    try:
        validated = CorrelationService().submit_model_proposal(proposal)
        async with database.transaction() as session:
            relationship = await CorrelationRepository().persist_model_proposal(
                session, validated
            )
            await _record_event(
                session,
                event_id=uuid5(validated.proposal_id, "analyst-proposal-submission"),
                event_type="analyst_proposal_submitted",
                run_id=validated.triggering_run_id,
                payload={
                    "proposal_id": str(validated.proposal_id),
                    "relationship_id": str(relationship.id),
                    "review_state": validated.review_state.value,
                },
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnalystProposalResponse(
        proposal_id=validated.proposal_id,
        relationship_id=relationship.id,
        review_state=validated.review_state.value,
    )


@router.post("/reports/validate", response_model=ValidationManifest)
async def validate_report(bundle: ReportBundle) -> ValidationManifest:
    try:
        return ReportPipeline().validate(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/reports", response_model=AnalystSubmissionResponse)
async def submit_report(
    submission: AnalystReportSubmission,
    database: Database = Depends(get_database),
) -> AnalystSubmissionResponse:
    bundle = submission.bundle
    if submission.publish:
        if bundle.state is ReportState.PUBLISHED:
            raise HTTPException(
                status_code=422, detail="published state is server-owned"
            )
        bundle = bundle.model_copy(update={"state": ReportState.APPROVED})
    elif bundle.state is not ReportState.DRAFT:
        raise HTTPException(
            status_code=422, detail="draft submissions must use state=draft"
        )

    pipeline = ReportPipeline()
    manifest: ValidationManifest | None = None
    if submission.publish:
        try:
            manifest = pipeline.validate(bundle)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    structured = json.loads(bundle.stable_json())
    async with database.transaction() as session:
        existing = await session.get(ReportVersion, bundle.report_version_id)
        if existing is not None and existing.structured_content != structured:
            raise HTTPException(
                status_code=409,
                detail="report version ID already contains different content",
            )
        if submission.publish:
            report = cast(Report, await pipeline.publish(session, bundle))
        else:
            report = cast(Report, await pipeline.save_draft(session, bundle))

    state = ReportState(report.state)
    return AnalystSubmissionResponse(
        report_id=report.id,
        report_version_id=bundle.report_version_id,
        state=state,
        public_url=f"/reports/{report.slug}"
        if state is ReportState.PUBLISHED
        else None,
        validation=manifest,
    )
