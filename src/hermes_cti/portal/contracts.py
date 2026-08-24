"""Versioned public portal contracts and bounded query parameters."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from hermes_cti.correlation.contracts import CorrelationRelationship
from hermes_cti.models.contracts import (
    AttackTechniqueMapping,
    ContractModel,
    DetectionArtifact,
    Remediation,
    ReportState,
    Severity,
    ThreatHunt,
    UTCDateTime,
)
from hermes_cti.reporting.contracts import (
    ReportEvidence,
    ReportIOC,
    ReportTimelineEvent,
    ReportVulnerability,
)


class ReportChangeState(StrEnum):
    """Public change label shown on report lines."""

    NEW = "new"
    UPDATED = "updated"
    RESURFACED = "resurfaced"


class ReportSort(StrEnum):
    """Stable, bounded list sort choices."""

    PRIORITY = "priority"
    NEWEST = "newest"
    CHANGED = "changed"
    CONFIDENCE = "confidence"
    SOURCES = "sources"


class PortalQuery(ContractModel):
    """Validated public report-list query; public state is always published."""

    search: str | None = Field(default=None, max_length=200)
    severities: tuple[Severity, ...] = ()
    confidence_min: float | None = Field(default=None, ge=0, le=1)
    date_from: date | None = None
    date_to: date | None = None
    change_states: tuple[ReportChangeState, ...] = ()
    sort: ReportSort = ReportSort.PRIORITY
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_dates(self) -> PortalQuery:
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValueError("date_from must not be after date_to")
        return self


class PublicReportSummary(ContractModel):
    """Compact public report line item with no private identifiers."""

    public_id: str
    slug: str
    headline: str
    report_type: str
    severity: Severity
    confidence: float = Field(..., ge=0, le=1)
    state: ReportState = ReportState.PUBLISHED
    change_state: ReportChangeState
    first_published_at: UTCDateTime | None = None
    last_updated_at: UTCDateTime
    primary_cves: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    malware: tuple[str, ...] = ()
    attack_techniques: tuple[str, ...] = ()
    source_count: int = Field(default=0, ge=0)
    hunt_available: bool = False
    remediation_available: bool = False
    detection_available: bool = False
    canonical_url: str


class PublicReportDetail(ContractModel):
    """Complete public projection of one published report version."""

    summary: PublicReportSummary
    version: int
    executive_summary: str
    technical_analysis: str
    evidence_summary: str
    evidence: tuple[ReportEvidence, ...]
    iocs: tuple[ReportIOC, ...] = ()
    vulnerabilities: tuple[ReportVulnerability, ...] = ()
    attack_mappings: tuple[AttackTechniqueMapping, ...] = ()
    detections: tuple[DetectionArtifact, ...] = ()
    hunt: ThreatHunt | None = None
    remediation: Remediation | None = None
    historical_relationships: tuple[CorrelationRelationship, ...] = ()
    timeline: tuple[ReportTimelineEvent, ...] = ()
    confidence: float = Field(..., ge=0, le=1)
    severity: Severity
    caveats: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()


class PublicReportPage(ContractModel):
    """Paginated public report response."""

    items: tuple[PublicReportSummary, ...]
    page: int
    page_size: int
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    query: PortalQuery


class PublicRelatedReports(ContractModel):
    """Related-report pivot response."""

    entity_type: str
    entity_id: str
    reports: tuple[PublicReportSummary, ...]


class PublicDetectionPage(ContractModel):
    """Dedicated detection response."""

    report: PublicReportSummary
    detections: tuple[DetectionArtifact, ...]


class PublicAdminDraft(ContractModel):
    """Private draft projection; deliberately not reusable by public routes."""

    report_id: UUID
    public_id: str
    slug: str
    headline: str
    state: ReportState
    last_updated_at: UTCDateTime


class PrivateDraftPage(ContractModel):
    items: tuple[PublicAdminDraft, ...]
    total: int
