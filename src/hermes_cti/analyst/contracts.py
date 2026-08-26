"""Contracts for the authenticated Hermes analyst API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from hermes_cti.models.contracts import ContractModel, ReportState, RunStatus
from hermes_cti.reporting.contracts import ReportBundle, ValidationManifest


class AnalystSourceRun(ContractModel):
    source_id: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None = None
    http_status: int | None = None
    item_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    cache_state: str
    error_classification: str | None = None


class AnalystRun(ContractModel):
    ingestion_run_id: UUID
    run_type: str
    status: RunStatus
    scheduled_for: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    triggering_origin: str
    application_version: str
    total_sources: int = Field(ge=0)
    successful_sources: int = Field(ge=0)
    failed_sources: int = Field(ge=0)
    new_documents: int = Field(ge=0)
    changed_documents: int = Field(ge=0)
    unchanged_documents: int = Field(ge=0)
    new_findings: int = Field(ge=0)
    error_summary: str | None = None
    source_runs: tuple[AnalystSourceRun, ...] = ()


class AnalystStatus(ContractModel):
    status: str
    application_version: str
    database: str
    scheduler_heartbeat: str | None = None
    latest_completed_run_id: UUID | None = None
    latest_completed_at: datetime | None = None


class AnalystRunResponse(ContractModel):
    run: AnalystRun | None = None


class AnalystDocument(ContractModel):
    source_document_id: UUID
    source_id: str
    external_source_id: str | None = None
    canonical_url: str
    title: str
    published_at: datetime | None = None
    updated_at_source: datetime | None = None
    retrieved_at: datetime
    content_type: str
    document_type: str
    normalized_content_hash: str
    sanitized_summary: str | None = None
    normalized_text: str
    text_truncated: bool = False


class AnalystClaim(ContractModel):
    evidence_id: UUID
    source_document_id: UUID
    claim_type: str
    subject_entity_type: str
    subject_entity_id: UUID | None = None
    predicate: str
    object_entity_type: str | None = None
    object_entity_id: UUID | None = None
    object_literal: str | None = None
    evidence_text: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    extraction_origin: str
    confidence: float = Field(ge=0, le=1)


class AnalystIndicator(ContractModel):
    observation_id: UUID
    source_document_id: UUID
    indicator_type: str
    value: str
    validation_state: str
    evidence_text: str
    context: str | None = None
    confidence: float = Field(ge=0, le=1)


class AnalystEvidenceResponse(ContractModel):
    ingestion_run_id: UUID | None = None
    documents: tuple[AnalystDocument, ...] = ()
    claims: tuple[AnalystClaim, ...] = ()
    indicators: tuple[AnalystIndicator, ...] = ()


class AnalystReportSubmission(ContractModel):
    bundle: ReportBundle
    publish: bool = False


class AnalystSubmissionResponse(ContractModel):
    report_id: UUID
    report_version_id: UUID
    state: ReportState
    public_url: str | None = None
    validation: ValidationManifest | None = None


class AnalystProposalResponse(ContractModel):
    proposal_id: UUID
    relationship_id: UUID
    review_state: str
    published: bool = False
