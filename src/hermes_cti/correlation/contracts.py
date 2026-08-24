"""Typed Phase 6 correlation, contradiction, and resurfacing contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from hermes_cti.models.contracts import (
    Confidence,
    ContractModel,
    EntityReference,
    RelationshipOrigin,
    ReviewState,
    Severity,
    UTCDateTime,
)


class CorrelationEntity(ContractModel):
    """Public-CTI entity snapshot used by deterministic correlation."""

    reference: EntityReference
    cve_ids: tuple[str, ...] = ()
    indicator_keys: tuple[str, ...] = ()
    cpe_keys: tuple[str, ...] = ()
    product_keys: tuple[str, ...] = ()
    attack_ids: tuple[str, ...] = ()
    content_hashes: tuple[str, ...] = ()
    provider_identifiers: tuple[str, ...] = ()
    infrastructure_keys: tuple[str, ...] = ()
    validated_infrastructure_keys: tuple[str, ...] = ()
    malware_names: tuple[str, ...] = ()
    tool_names: tuple[str, ...] = ()
    campaign_names: tuple[str, ...] = ()
    actor_aliases: tuple[str, ...] = ()
    behaviors: tuple[str, ...] = ()
    sectors: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    first_seen_at: UTCDateTime | None = None
    last_seen_at: UTCDateTime | None = None
    evidence_ids: tuple[UUID, ...] = ()
    assertions: tuple[EvidenceAssertion, ...] = ()
    semantic_similarities: tuple[SemanticSimilarity, ...] = ()

    @model_validator(mode="after")
    def validate_time_order(self) -> CorrelationEntity:
        if (
            self.first_seen_at is not None
            and self.last_seen_at is not None
            and self.first_seen_at > self.last_seen_at
        ):
            raise ValueError("first_seen_at must not be after last_seen_at")
        return self


class EvidenceAssertion(ContractModel):
    """A source-backed assertion retained for contradiction inspection."""

    claim_key: str = Field(..., min_length=1, max_length=128)
    value: str = Field(..., min_length=1, max_length=1024)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)
    evidence_role: Literal["supports", "contradicts", "contextualizes"] = "supports"
    source_document_ids: tuple[UUID, ...] = ()


class SemanticSimilarity(ContractModel):
    """Optional precomputed similarity; no embedding store is introduced in Phase 6."""

    candidate_reference: EntityReference
    score: Confidence
    evidence_ids: tuple[UUID, ...] = ()


class CorrelationCandidate(ContractModel):
    """A ranked lead that explicitly does not establish a relationship."""

    candidate_id: UUID
    source: EntityReference
    target: EntityReference
    candidate_type: str = Field(..., min_length=1, max_length=64)
    score: Confidence
    rationale: str = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = ()
    relationship_established: Literal[False] = False


class CorrelationRelationship(ContractModel):
    """A persistable relationship with complete provenance and review metadata."""

    relationship_id: UUID
    source: EntityReference
    relationship_type: str = Field(..., min_length=1, max_length=128)
    target: EntityReference
    direction: str = Field(default="forward", min_length=1, max_length=32)
    origin: RelationshipOrigin
    confidence: Confidence
    first_seen_at: UTCDateTime | None = None
    last_seen_at: UTCDateTime | None = None
    active: bool = True
    review_state: ReviewState
    supersedes_id: UUID | None = None
    origin_rule: str = Field(..., min_length=1, max_length=255)
    justification: str = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = ()
    prompt_version: str | None = None
    model_identifier: str | None = None

    @model_validator(mode="after")
    def validate_relationship_policy(self) -> CorrelationRelationship:
        if self.origin is RelationshipOrigin.DETERMINISTIC and not self.origin_rule:
            raise ValueError("deterministic relationships require a versioned rule")
        if (
            self.origin is RelationshipOrigin.SOURCED_ASSERTION
            and not self.evidence_ids
        ):
            raise ValueError("sourced assertions require evidence")
        if (
            self.origin is RelationshipOrigin.MODEL_INFERENCE
            and self.review_state
            not in {
                ReviewState.PROPOSED,
                ReviewState.REVIEWED,
            }
        ):
            raise ValueError("model-inference relationships require review state")
        return self


class CorrelationResult(ContractModel):
    """Complete deterministic output; candidates remain explicitly non-relational."""

    relationships: tuple[CorrelationRelationship, ...] = ()
    candidates: tuple[CorrelationCandidate, ...] = ()
    contradictions: tuple[ContradictionEvidence, ...] = ()


class ContradictionEvidence(ContractModel):
    """Conflicting public assertions preserved instead of silently resolved."""

    contradiction_id: UUID
    subject: EntityReference
    claim_key: str = Field(..., min_length=1, max_length=128)
    observed_values: tuple[str, ...] = Field(..., min_length=2)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=2)
    justification: str = Field(..., min_length=1)


class AssessmentSnapshot(ContractModel):
    """Immutable view of one versioned risk assessment for resurfacing."""

    assessment_id: UUID
    entity: EntityReference
    assessment_version: int = Field(..., ge=1)
    score: float = Field(..., ge=0, le=100)
    severity: Severity
    confidence: Confidence
    known_exploited: bool | None = None
    epss_score: float | None = Field(default=None, ge=0, le=1)
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    affected_product_keys: tuple[str, ...] = ()
    evidence_ids: tuple[UUID, ...] = ()
    active_exploitation_evidence: bool = False
    infrastructure_reactivated: bool = False
    independent_corroboration: bool = False
    attack_chain_completed: bool = False
    coverage_obsolete: bool = False


class ResurfacingReason(StrEnum):
    """Material public-CTI changes that can resurface a historical assessment."""

    KEV_ADDITION = "kev_addition"
    MATERIAL_EPSS_CHANGE = "material_epss_change"
    MATERIAL_CVSS_CHANGE = "material_cvss_change"
    ACTIVE_EXPLOITATION = "active_exploitation"
    INFRASTRUCTURE_REACTIVATED = "infrastructure_reactivated"
    INDEPENDENT_CORROBORATION = "independent_corroboration"
    AFFECTED_SURFACE_EXPANDED = "affected_surface_expanded"
    ATTACK_CHAIN_COMPLETED = "attack_chain_completed"
    COVERAGE_OBSOLETE = "coverage_obsolete"


class ResurfacingEvent(ContractModel):
    """Versioned link between prior assessment, new assessment, and evidence."""

    event_id: UUID
    entity: EntityReference
    previous_assessment_id: UUID
    new_assessment_id: UUID
    reasons: tuple[ResurfacingReason, ...] = Field(..., min_length=1)
    evidence_ids: tuple[UUID, ...] = Field(..., min_length=1)
    previous_score: float = Field(..., ge=0, le=100)
    new_score: float = Field(..., ge=0, le=100)
    justification: str = Field(..., min_length=1)
    review_state: ReviewState = ReviewState.PROPOSED
    created_at: UTCDateTime

    @model_validator(mode="after")
    def validate_assessment_order(self) -> ResurfacingEvent:
        if self.previous_assessment_id == self.new_assessment_id:
            raise ValueError("resurfacing requires distinct assessment versions")
        return self


def utc_now() -> datetime:
    """Return an aware UTC timestamp for service-created event records."""

    return datetime.now(UTC)
