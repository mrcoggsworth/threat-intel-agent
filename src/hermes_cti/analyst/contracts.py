"""Contracts for the authenticated Hermes analyst API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from hermes_cti.db.lifecycle import RecordStatus
from hermes_cti.models.contracts import (
    ContractModel,
    EntityType,
    ReportState,
    ReviewState,
    RunHealthSummary,
    RunStatus,
)
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
    latest_attempt: RunHealthSummary | None = None
    latest_full_success: RunHealthSummary | None = None
    latest_usable: RunHealthSummary | None = None
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


class CorpusResource(StrEnum):
    """Private corpus resource names exposed by the analyst API."""

    CVES = "cves"
    IOCS = "iocs"
    PRODUCTS = "products"
    ACTORS = "actors"
    MALWARE = "malware"
    TOOLS = "tools"
    CAMPAIGNS = "campaigns"
    TECHNIQUES = "techniques"
    URLS = "urls"
    EVIDENCE = "evidence"
    RELATIONSHIPS = "relationships"
    CONTRADICTIONS = "contradictions"


class CorpusSort(StrEnum):
    """The only supported corpus order; clients cannot supply SQL expressions."""

    UPDATED_DESC = "updated_desc"


class CorpusQuery(ContractModel):
    """Strict, bounded filters shared by every historical corpus query."""

    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=512)
    search: str | None = Field(default=None, min_length=1, max_length=200)
    record_status: RecordStatus | None = None
    review_state: ReviewState | None = None
    published: bool | None = None
    entity_type: EntityType | None = None
    entity_id: UUID | None = None
    source_id: str | None = Field(default=None, min_length=1, max_length=128)
    cve_id: str | None = Field(default=None, min_length=1, max_length=32)
    indicator_type: str | None = Field(default=None, min_length=1, max_length=64)
    value: str | None = Field(default=None, min_length=1, max_length=1024)
    vendor: str | None = Field(default=None, min_length=1, max_length=255)
    product: str | None = Field(default=None, min_length=1, max_length=255)
    ecosystem: str | None = Field(default=None, min_length=1, max_length=128)
    attack_id: str | None = Field(default=None, min_length=1, max_length=32)
    framework_version: str | None = Field(default=None, min_length=1, max_length=32)
    relationship_type: str | None = Field(default=None, min_length=1, max_length=128)
    sort: CorpusSort = CorpusSort.UPDATED_DESC

    @field_validator(
        "search",
        "source_id",
        "cve_id",
        "indicator_type",
        "value",
        "vendor",
        "product",
        "ecosystem",
        "attack_id",
        "framework_version",
        "relationship_type",
        mode="before",
    )
    @classmethod
    def _clean_text(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    @field_validator("cve_id", "attack_id", mode="after")
    @classmethod
    def _uppercase_identifiers(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_filter_pair(self) -> CorpusQuery:
        if (self.entity_type is None) != (self.entity_id is None):
            raise ValueError("entity_type and entity_id must be supplied together")
        return self

    def validate_for(self, resource: CorpusResource) -> None:
        """Reject filters that have no indexed meaning for this resource."""
        allowed: dict[CorpusResource, set[str]] = {
            CorpusResource.CVES: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "cve_id",
            },
            CorpusResource.IOCS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "indicator_type",
                "value",
            },
            CorpusResource.PRODUCTS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "vendor",
                "product",
                "ecosystem",
            },
            CorpusResource.ACTORS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
            },
            CorpusResource.MALWARE: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
            },
            CorpusResource.TOOLS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
            },
            CorpusResource.CAMPAIGNS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
            },
            CorpusResource.TECHNIQUES: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "attack_id",
                "framework_version",
            },
            CorpusResource.URLS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "source_id",
            },
            CorpusResource.EVIDENCE: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "entity_type",
                "entity_id",
                "source_id",
            },
            CorpusResource.RELATIONSHIPS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "published",
                "review_state",
                "entity_type",
                "entity_id",
                "relationship_type",
            },
            CorpusResource.CONTRADICTIONS: {
                "limit",
                "cursor",
                "search",
                "record_status",
                "review_state",
                "entity_type",
                "entity_id",
            },
        }
        values = self.model_dump(exclude_none=True, exclude={"schema_version", "sort"})
        unsupported = set(values) - allowed[resource]
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(f"filters are not supported for {resource.value}: {names}")


class CorpusProvenance(ContractModel):
    """Secret-free provenance references attached to every corpus record."""

    source_document_ids: tuple[UUID, ...] = ()
    evidence_claim_ids: tuple[UUID, ...] = ()
    provider_result_ids: tuple[UUID, ...] = ()
    source_urls: tuple[str, ...] = ()
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class AnalystCorpusRecord(ContractModel):
    """Common audit metadata for private corpus records."""

    id: UUID
    record_status: RecordStatus
    created_at: datetime
    updated_at: datetime
    provenance: CorpusProvenance = Field(default_factory=CorpusProvenance)


class AnalystCVE(AnalystCorpusRecord):
    cve_id: str
    description: str | None = None
    published_at: datetime | None = None
    modified_at: datetime | None = None
    cvss_score: float | None = None
    epss_score: float | None = None
    known_exploited: bool | None = None
    exploitation_state: str


class AnalystIOC(AnalystCorpusRecord):
    indicator_type: str
    value: str
    validation_state: str
    public_visibility: bool
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class AnalystProductVersion(ContractModel):
    version_range: str | None = None
    cpe: str | None = None
    vulnerability_id: UUID
    affected_status: str
    confidence: float = Field(ge=0, le=1)
    remediation_available: bool | None = None


class AnalystProduct(AnalystCorpusRecord):
    vendor: str
    product: str
    ecosystem: str
    product_type: str | None = None
    canonical_identifiers: dict[str, Any] = Field(default_factory=dict)
    versions: tuple[AnalystProductVersion, ...] = ()


class AnalystActor(AnalystCorpusRecord):
    canonical_name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    attribution_state: str
    description: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    source_count: int = Field(ge=0)


class AnalystMalware(AnalystCorpusRecord):
    canonical_name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    malware_type: str | None = None
    platforms: tuple[str, ...] = ()
    description: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class AnalystTool(AnalystCorpusRecord):
    name: str
    normalized_name: str
    aliases: tuple[str, ...] = ()
    legitimate_use: bool | None = None
    description: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class AnalystCampaign(AnalystCorpusRecord):
    stable_key: str
    name: str | None = None
    description: str | None = None
    targeting: dict[str, Any] = Field(default_factory=dict)
    state: str
    confidence: float = Field(ge=0, le=1)
    start_at: datetime | None = None
    end_at: datetime | None = None


class AnalystTechnique(AnalystCorpusRecord):
    attack_id: str
    framework_version: str
    name: str
    tactic: str | None = None
    platform: str | None = None
    description_reference: str | None = None


class AnalystURL(AnalystCorpusRecord):
    source_id: str
    canonical_url: str
    title: str
    published_at: datetime | None = None
    retrieved_at: datetime
    content_type: str
    document_type: str
    normalized_content_hash: str
    supersedes_id: UUID | None = None


class AnalystEvidence(AnalystCorpusRecord):
    source_document_id: UUID
    source_id: str
    canonical_url: str
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


class AnalystRelationship(AnalystCorpusRecord):
    source_entity_type: str
    source_entity_id: UUID
    relationship_type: str
    target_entity_type: str
    target_entity_id: UUID
    direction: str
    origin: str
    confidence: float = Field(ge=0, le=1)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    active: bool
    review_state: ReviewState
    supersedes_id: UUID | None = None
    origin_rule: str
    justification: str | None = None
    prompt_version: str | None = None
    model_identifier: str | None = None
    analyst_run_id: UUID | None = None
    evidence_ids: tuple[UUID, ...] = ()


class AnalystContradiction(AnalystCorpusRecord):
    subject_entity_type: str
    subject_entity_id: UUID
    claim_key: str
    observed_values: tuple[str, ...]
    evidence_ids: tuple[UUID, ...]
    justification: str
    review_state: ReviewState = ReviewState.PROPOSED
    confidence: float | None = Field(default=None, ge=0, le=1)
    supersedes_id: UUID | None = None


CorpusRecordT = TypeVar("CorpusRecordT", bound=AnalystCorpusRecord)


class AnalystCorpusPage[CorpusRecordT](ContractModel):
    """Bounded keyset page with explicit count and continuation semantics."""

    resource: CorpusResource
    items: tuple[CorpusRecordT, ...]
    limit: int = Field(ge=1, le=100)
    returned: int = Field(ge=0, le=100)
    has_more: bool
    next_cursor: str | None = None
    query_timeout_ms: int = Field(ge=1, le=10_000)
    query: CorpusQuery
