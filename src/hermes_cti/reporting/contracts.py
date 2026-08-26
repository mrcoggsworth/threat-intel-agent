"""Typed Phase 7 report, evidence, and publication contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from hermes_cti.correlation.contracts import CorrelationRelationship
from hermes_cti.models.contracts import (
    AffectedProduct,
    AttackTechniqueMapping,
    ContractModel,
    DetectionArtifact,
    EntityReference,
    HttpURL,
    JSONValue,
    PublicSourceReference,
    Remediation,
    ReportState,
    Severity,
    ThreatHunt,
    UTCDateTime,
)


class ReportEvidenceType(StrEnum):
    """Evidence roles used by report coverage checks."""

    SOURCE_TEXT = "source_text"
    IOC_OBSERVATION = "ioc_observation"
    VULNERABILITY = "vulnerability"
    PRODUCT = "product"
    ATTACK_MAPPING = "attack_mapping"
    RELATIONSHIP = "relationship"
    TIMELINE = "timeline"
    FILE = "file"


class ReportEvidence(ContractModel):
    """Public-source evidence fragment retained with explicit provenance."""

    evidence_id: UUID
    evidence_type: ReportEvidenceType
    statement: str = Field(..., min_length=1)
    source_document_id: UUID | None = None
    source_reference: PublicSourceReference | None = None
    source_url: HttpURL | None = None
    confidence: float = Field(..., ge=0, le=1)
    public_safe: bool = True


class ReportIOC(ContractModel):
    """Safe-display IOC reference for a report; raw values remain evidence-bound."""

    indicator: EntityReference
    display_value: str = Field(..., min_length=1)
    indicator_type: str = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)


class ReportVulnerability(ContractModel):
    """Vulnerability and affected-product section item."""

    vulnerability_id: UUID
    cve_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    cvss_version: str | None = None
    cvss_vector: str | None = None
    epss_score: float | None = Field(default=None, ge=0, le=1)
    epss_percentile: float | None = Field(default=None, ge=0, le=1)
    cwe_ids: tuple[str, ...] = ()
    known_exploited: bool | None = None
    exploitation_state: str = "unknown"
    kev_date_added: date | None = None
    kev_due_date: date | None = None
    kev_required_action: str | None = None
    affected_products: tuple[AffectedProduct, ...] = ()
    product_references: tuple[EntityReference, ...] = ()
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)


class ReportTimelineEvent(ContractModel):
    """UTC event in the public intelligence timeline."""

    occurred_at: UTCDateTime
    label: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)


class ReportRelationship(ContractModel):
    """Report-safe relationship projection retaining evidence and origin."""

    relationship: CorrelationRelationship
    evidence_ids: tuple[UUID, ...] = ()


class ReportBundle(ContractModel):
    """Complete versioned report input to validation, rendering, and persistence."""

    report_id: UUID
    report_version_id: UUID
    public_id: str = Field(..., min_length=1)
    slug: str = Field(..., min_length=1)
    version: int = Field(..., ge=1)
    report_type: str = Field(..., min_length=1)
    headline: str = Field(..., min_length=1)
    headline_evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)
    executive_summary: str = Field(..., min_length=1)
    technical_analysis: str = Field(..., min_length=1)
    evidence_summary: str = Field(..., min_length=1)
    evidence: tuple[ReportEvidence, ...] = Field(..., min_length=1)
    iocs: tuple[ReportIOC, ...] = ()
    vulnerabilities: tuple[ReportVulnerability, ...] = ()
    attack_mappings: tuple[AttackTechniqueMapping, ...] = ()
    detections: tuple[DetectionArtifact, ...] = ()
    hunt: ThreatHunt | None = None
    remediation: Remediation | None = None
    historical_relationships: tuple[ReportRelationship, ...] = ()
    timeline: tuple[ReportTimelineEvent, ...] = ()
    confidence: float = Field(..., ge=0, le=1)
    severity: Severity
    caveats: tuple[str, ...] = ()
    source_references: tuple[PublicSourceReference, ...] = ()
    state: ReportState = ReportState.DRAFT
    resurfaced: bool = False
    generated_by: str = Field(..., min_length=1)
    application_version: str = Field(..., min_length=1)
    model_identifier: str | None = None
    prompt_version: str | None = None
    skill_versions: tuple[str, ...] = ()
    system_prompt_hash: str | None = None
    skill_version_hashes: tuple[str, ...] = ()
    triggering_run_id: UUID | None = None
    token_metadata: dict[str, JSONValue] | None = None
    cost_metadata: dict[str, JSONValue] | None = None
    supersedes_id: UUID | None = None

    @model_validator(mode="after")
    def validate_identity(self) -> ReportBundle:
        evidence_ids = {item.evidence_id for item in self.evidence}
        if not set(self.headline_evidence_ids).issubset(evidence_ids):
            raise ValueError("headline evidence IDs must reference report evidence")
        if any(not item.public_safe for item in self.evidence):
            raise ValueError("report evidence must be public-safe")
        if (
            self.hunt is not None
            and self.hunt.report_version_id != self.report_version_id
        ):
            raise ValueError("hunt must belong to report_version_id")
        if (
            self.remediation is not None
            and self.remediation.report_version_id != self.report_version_id
        ):
            raise ValueError("remediation must belong to report_version_id")
        return self


class ReportSection(StrEnum):
    """Required report sections checked before validation or publication."""

    HEADLINE = "headline"
    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL_ANALYSIS = "technical_analysis"
    EVIDENCE = "evidence"
    IOCS = "iocs"
    VULNERABILITIES_PRODUCTS = "vulnerabilities_products"
    ATTACK_MAPPING = "attack_mapping"
    DETECTION_CONTENT = "detection_content"
    THREAT_HUNTING = "threat_hunting"
    REMEDIATION = "remediation"
    HISTORICAL_RELATIONSHIPS = "historical_relationships"
    TIMELINE = "timeline"
    CONFIDENCE = "confidence"
    CAVEATS = "caveats"


class EvidenceCoverage(ContractModel):
    """Deterministic report coverage result."""

    valid: bool
    missing_sections: tuple[ReportSection, ...] = ()
    unsupported_claims: tuple[str, ...] = ()
    unsupported_remediation: tuple[str, ...] = ()
    covered_evidence_ids: tuple[UUID, ...] = ()
    coverage_version: str = "phase7-v1"


class ValidationManifest(ContractModel):
    """Persisted validation and provenance manifest for a report version."""

    valid: bool
    coverage: EvidenceCoverage
    renderer_version: str
    application_version: str
    model_identifier: str | None = None
    prompt_version: str | None = None
    skill_versions: tuple[str, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    artifact_hashes: tuple[str, ...] = ()


class RenderedArtifact(ContractModel):
    """Safe rendered report or detection download payload."""

    artifact_name: str = Field(..., min_length=1)
    media_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    artifact_hash: str = Field(..., min_length=64, max_length=64)


class RenderedReport(ContractModel):
    """All report projections generated before publication mutation."""

    markdown: RenderedArtifact
    json_artifact: RenderedArtifact = Field(alias="json")
    portal: RenderedArtifact
    downloads: tuple[RenderedArtifact, ...] = ()
    renderer_version: str = "phase7-renderer-v1"


def utc_now() -> datetime:
    """Return an aware UTC time for publication records."""

    return datetime.now(UTC)
