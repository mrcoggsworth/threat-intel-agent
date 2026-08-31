"""Versioned public portal contracts and bounded query parameters."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

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

    @field_validator("search", mode="before")
    @classmethod
    def _clean_search(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("confidence_min", mode="before")
    @classmethod
    def _clean_confidence_min(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _clean_dates(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("severities", mode="before")
    @classmethod
    def _clean_severities(cls, v: Any) -> Any:
        if v is None or v == "":
            return ()
        if isinstance(v, (list, tuple)):
            return tuple(item for item in v if item != "" and item is not None)
        return v

    @field_validator("change_states", mode="before")
    @classmethod
    def _clean_change_states(cls, v: Any) -> Any:
        if v is None or v == "":
            return ()
        if isinstance(v, (list, tuple)):
            return tuple(item for item in v if item != "" and item is not None)
        return v

    @field_validator("sort", mode="before")
    @classmethod
    def _clean_sort(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return ReportSort.PRIORITY
        return v

    @field_validator("page", mode="before")
    @classmethod
    def _clean_page(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 1
        return v

    @field_validator("page_size", mode="before")
    @classmethod
    def _clean_page_size(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 20
        return v

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


class EvidenceAnalystSummary(ContractModel):
    """Structured CTI analyst interpretation and takeaway for an evidence claim."""

    core_finding: str = Field(
        ...,
        min_length=1,
        description="Analytical interpretation of what this evidence proves.",
    )
    hunt_relevance: str = Field(
        ...,
        min_length=1,
        description="Tactical hunting strategy and query application.",
    )
    triage_caveats: str = Field(
        ...,
        min_length=1,
        description="False-positive cautions and verification checklist.",
    )
    recommended_pivots: tuple[str, ...] = Field(
        default=(), description="Telemetry sources and pivot points for verification."
    )


class PublicEvidenceDetail(ContractModel):
    """Detailed evidence modal payload with source citation and analyst synthesis."""

    evidence_id: UUID
    evidence_type: str
    statement: str
    source_reference: Any | None = None
    source_url: str | None = None
    confidence: float
    report_slug: str
    report_headline: str
    analyst_summary: EvidenceAnalystSummary


class CVESort(StrEnum):
    """Stable, bounded CVE sort options."""

    PRIORITY = "priority"
    CVSS = "cvss"
    EPSS = "epss"
    NEWEST = "newest"
    REPORTS = "reports"


class CVEQuery(ContractModel):
    """Validated public CVE query."""

    search: str | None = Field(default=None, max_length=200)
    severities: tuple[Severity, ...] = ()
    known_exploited_only: bool = False
    min_cvss: float | None = Field(default=None, ge=0, le=10)
    min_epss: float | None = Field(default=None, ge=0, le=1)
    sort: CVESort = CVESort.PRIORITY
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("search", mode="before")
    @classmethod
    def _clean_search(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("severities", mode="before")
    @classmethod
    def _clean_severities(cls, v: Any) -> Any:
        if v is None or v == "":
            return ()
        if isinstance(v, (list, tuple)):
            return tuple(item for item in v if item != "" and item is not None)
        return v

    @field_validator("min_cvss", "min_epss", mode="before")
    @classmethod
    def _clean_floats(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("known_exploited_only", mode="before")
    @classmethod
    def _clean_bool(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.lower() in {"true", "1", "yes", "on"}
        return bool(v)

    @field_validator("sort", mode="before")
    @classmethod
    def _clean_sort(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return CVESort.PRIORITY
        return v

    @field_validator("page", mode="before")
    @classmethod
    def _clean_page(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 1
        return v

    @field_validator("page_size", mode="before")
    @classmethod
    def _clean_page_size(cls, v: Any) -> Any:
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 20
        return v


class PublicCVESummary(ContractModel):
    """Compact public summary of an indexed CVE."""

    cve_id: str
    summary: str
    cvss_score: float | None = None
    cvss_version: str | None = None
    cvss_vector: str | None = None
    epss_score: float | None = None
    epss_percentile: float | None = None
    known_exploited: bool = False
    severity: Severity = Severity.MEDIUM
    badge_label: str = "Telemetry Pending"
    badge_style: str = "slate"
    cwe_ids: tuple[str, ...] = ()
    affected_products: tuple[str, ...] = ()
    report_count: int = 0
    report_slugs: tuple[str, ...] = ()
    canonical_url: str

    @field_validator("known_exploited", mode="before")
    @classmethod
    def _clean_known_exploited(cls, v: Any) -> bool:
        if v is None:
            return False
        if isinstance(v, str):
            return v.lower() in {"true", "1", "yes", "on"}
        return bool(v)


class PublicCVEPage(ContractModel):
    """Paginated public CVE response."""

    items: tuple[PublicCVESummary, ...]
    page: int
    page_size: int
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    query: CVEQuery
