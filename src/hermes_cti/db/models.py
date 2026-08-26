"""Typed SQLAlchemy 2 persistence models for the Phase 4 baseline."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes_cti.db.base import Base, TimestampMixin
from hermes_cti.db.vulnerability_models import (  # noqa: F401
    VulnerabilityAttributeSelection,
    VulnerabilityProviderObservation,
)


class IngestionRun(TimestampMixin, Base):
    __tablename__ = "ingestion_run"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingestion_run_idempotency"),
        CheckConstraint(
            "status IN ('scheduled', 'running', 'completed', 'failed', 'skipped')",
            name="ck_ingestion_run_status",
        ),
        CheckConstraint(
            "(status IN ('completed', 'failed', 'skipped')) = "
            "(completed_at IS NOT NULL)",
            name="ck_ingestion_run_terminal_completion",
        ),
        Index("ix_ingestion_run_status_schedule", "status", "scheduled_for"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    triggering_origin: Mapped[str] = mapped_column(String(128), nullable=False)
    application_version: Mapped[str] = mapped_column(String(128), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    total_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_sources: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changed_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unchanged_documents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_findings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)


class SourceRun(TimestampMixin, Base):
    __tablename__ = "source_run"

    ingestion_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion_run.id"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("source.source_id"), primary_key=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cache_state: Mapped[str] = mapped_column(String(32), nullable=False)
    error_classification: Mapped[str | None] = mapped_column(String(128))

    error_detail: Mapped[str | None] = mapped_column(Text)


class OperationalEvent(TimestampMixin, Base):
    __tablename__ = "operational_event"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion_run.id")
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    public_safe: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Source(TimestampMixin, Base):
    __tablename__ = "source"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reliability: Mapped[str] = mapped_column(String(64), nullable=False)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    max_response_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    configuration_version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    last_successful_retrieval: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_failure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failure_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )


class SourceConfigurationHistory(TimestampMixin, Base):
    """Immutable, secret-free history of accepted source configurations."""

    __tablename__ = "source_configuration_history"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "configuration_hash",
            name="uq_source_configuration_history_hash",
        ),
        UniqueConstraint(
            "source_id",
            "configuration_version",
            name="uq_source_configuration_history_version",
        ),
        Index(
            "ix_source_configuration_history_source_recorded",
            "source_id",
            "recorded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("source.source_id"), nullable=False
    )
    configuration_version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RawArtifact(TimestampMixin, Base):
    __tablename__ = "raw_artifact"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "canonical_url",
            "content_hash",
            name="uq_raw_artifact_identity",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("source.source_id"), nullable=False
    )
    retrieval_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    encoding: Mapped[str | None] = mapped_column(String(64))
    etag: Mapped[str | None] = mapped_column(String(512))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_length: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_locator: Mapped[str | None] = mapped_column(Text)
    retention_policy: Mapped[str] = mapped_column(
        String(64), default="immutable_evidence", nullable=False
    )
    retention_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    storage_state: Mapped[str] = mapped_column(
        String(32), default="retained", nullable=False
    )
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    ingestion_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion_run.id"), nullable=False
    )


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_document"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "identity_key",
            "normalized_content_hash",
            name="uq_source_document_version",
        ),
        Index(
            "ix_source_document_canonical_hash",
            "canonical_url",
            "normalized_content_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("source.source_id"), nullable=False
    )
    raw_artifact_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("raw_artifact.id"), nullable=False
    )
    external_source_id: Mapped[str | None] = mapped_column(String(512))
    identity_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_document.id")
    )
    document_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parse_version: Mapped[str] = mapped_column(String(128), nullable=False)


class EvidenceClaim(TimestampMixin, Base):
    __tablename__ = "evidence_claim"
    __table_args__ = (
        CheckConstraint(
            "start_offset >= 0 AND end_offset >= start_offset",
            name="ck_evidence_claim_offsets",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_evidence_claim_confidence"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    claim_type: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    predicate: Mapped[str] = mapped_column(String(128), nullable=False)
    object_entity_type: Mapped[str | None] = mapped_column(String(64))
    object_entity_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    object_literal: Mapped[str | None] = mapped_column(Text)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    extraction_origin: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class Indicator(TimestampMixin, Base):
    __tablename__ = "indicator"
    __table_args__ = (
        UniqueConstraint(
            "indicator_type", "normalized_value", name="uq_indicator_natural_key"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    indicator_type: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    safe_display_value: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    validation_state: Mapped[str] = mapped_column(String(32), nullable=False)
    routability: Mapped[str | None] = mapped_column(String(64))
    public_visibility: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    suppression_reason: Mapped[str | None] = mapped_column(Text)


class IndicatorObservation(TimestampMixin, Base):
    __tablename__ = "indicator_observation"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id",
            "source_document_id",
            "start_offset",
            "end_offset",
            name="uq_indicator_observation_evidence",
        ),
        CheckConstraint(
            "start_offset >= 0 AND end_offset >= start_offset",
            name="ck_indicator_observation_offsets",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_indicator_observation_confidence",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    indicator_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("indicator.id"), nullable=False
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    ingestion_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion_run.id"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class Vulnerability(TimestampMixin, Base):
    __tablename__ = "vulnerability"
    __table_args__ = (UniqueConstraint("cve_id", name="uq_vulnerability_cve"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    cve_id: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cvss_score: Mapped[float | None] = mapped_column(Float)
    epss_score: Mapped[float | None] = mapped_column(Float)
    known_exploited: Mapped[bool | None] = mapped_column(Boolean)
    cvss_version: Mapped[str | None] = mapped_column(String(16))
    cvss_vector: Mapped[str | None] = mapped_column(Text)
    epss_percentile: Mapped[float | None] = mapped_column(Float)
    epss_date: Mapped[date | None] = mapped_column(Date)
    cwe_ids: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, nullable=False
    )
    kev_date_added: Mapped[date | None] = mapped_column(Date)
    kev_due_date: Mapped[date | None] = mapped_column(Date)
    kev_vendor_project: Mapped[str | None] = mapped_column(String(255))
    kev_product: Mapped[str | None] = mapped_column(String(255))
    kev_required_action: Mapped[str | None] = mapped_column(Text)
    exploitation_state: Mapped[str] = mapped_column(
        String(32), default="unknown", nullable=False
    )


class Product(TimestampMixin, Base):
    __tablename__ = "product"
    __table_args__ = (
        UniqueConstraint(
            "normalized_vendor",
            "normalized_product",
            "ecosystem",
            name="uq_product_natural_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    product: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_product: Mapped[str] = mapped_column(String(255), nullable=False)
    ecosystem: Mapped[str] = mapped_column(
        String(128), default="unknown", nullable=False
    )
    product_type: Mapped[str | None] = mapped_column(String(64))
    canonical_identifiers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )


class AffectedProduct(TimestampMixin, Base):
    __tablename__ = "affected_product"
    __table_args__ = (
        UniqueConstraint(
            "vulnerability_id",
            "product_id",
            "version_range",
            "cpe",
            name="uq_affected_product_natural_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    vulnerability_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vulnerability.id"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product.id"), nullable=False
    )
    version_range: Mapped[str | None] = mapped_column(Text)
    cpe: Mapped[str | None] = mapped_column(Text)
    affected_status: Mapped[str] = mapped_column(String(32), nullable=False)
    source_claim_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_claim.id")
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    remediation_available: Mapped[bool | None] = mapped_column(Boolean)


class AttackTechnique(TimestampMixin, Base):
    __tablename__ = "attack_technique"
    __table_args__ = (
        UniqueConstraint(
            "attack_id", "framework_version", name="uq_attack_technique_natural_key"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    attack_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tactic: Mapped[str | None] = mapped_column(String(128))
    platform: Mapped[str | None] = mapped_column(String(128))
    framework_version: Mapped[str] = mapped_column(String(32), nullable=False)
    description_reference: Mapped[str | None] = mapped_column(Text)


class EnrichmentResult(TimestampMixin, Base):
    __tablename__ = "enrichment_result"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_query_key",
            "raw_payload_hash",
            name="uq_enrichment_natural_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_query_key: Mapped[str] = mapped_column(String(512), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    normalized_result: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_classification: Mapped[str | None] = mapped_column(String(128))
    quota_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class RiskAssessment(TimestampMixin, Base):
    __tablename__ = "risk_assessment"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "assessment_version",
            name="uq_risk_assessment_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    assessment_version: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_version: Mapped[str] = mapped_column(
        String(64), default="phase5-v1", nullable=False
    )
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    component_breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    origin: Mapped[str] = mapped_column(String(64), nullable=False)
    priority_explanation: Mapped[str | None] = mapped_column(Text)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk_assessment.id")
    )


class Relationship(TimestampMixin, Base):
    __tablename__ = "relationship"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "relationship_type",
            "target_entity_type",
            "target_entity_id",
            "origin_rule",
            name="uq_relationship_natural_key",
        ),
        Index("ix_relationship_source", "source_entity_type", "source_entity_id"),
        Index("ix_relationship_target", "target_entity_type", "target_entity_id"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_relationship_confidence"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(128), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), nullable=False)
    origin: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("relationship.id")
    )
    origin_rule: Mapped[str] = mapped_column(String(255), nullable=False)
    justification: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    model_identifier: Mapped[str | None] = mapped_column(String(255))
    analyst_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))


class RelationshipEvidence(TimestampMixin, Base):
    __tablename__ = "relationship_evidence"
    __table_args__ = (
        UniqueConstraint(
            "relationship_id",
            "source_document_id",
            "evidence_claim_id",
            "provider_result_id",
            name="uq_relationship_evidence",
        ),
        CheckConstraint(
            "source_document_id IS NOT NULL OR evidence_claim_id IS NOT NULL "
            "OR provider_result_id IS NOT NULL",
            name="ck_relationship_evidence_source",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    relationship_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("relationship.id"), nullable=False
    )
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_document.id")
    )
    evidence_claim_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_claim.id")
    )
    provider_result_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("enrichment_result.id")
    )
    evidence_role: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)


class CorrelationCandidateRecord(TimestampMixin, Base):
    """Persisted lead that cannot be projected as an established relationship."""

    __tablename__ = "correlation_candidate"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "target_entity_type",
            "target_entity_id",
            "candidate_type",
            name="uq_correlation_candidate_natural_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    source_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    relationship_established: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class CorrelationContradictionRecord(TimestampMixin, Base):
    """Durable contradictory public claims for analyst review."""

    __tablename__ = "correlation_contradiction"
    __table_args__ = (
        UniqueConstraint(
            "subject_entity_type",
            "subject_entity_id",
            "claim_key",
            name="uq_correlation_contradiction_subject_claim",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    subject_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_entity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_values: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)


class ResurfacingEventRecord(TimestampMixin, Base):
    """Versioned link between a prior and current public-CTI assessment."""

    __tablename__ = "resurfacing_event"
    __table_args__ = (
        UniqueConstraint(
            "previous_assessment_id",
            "new_assessment_id",
            name="uq_resurfacing_assessment_transition",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    previous_assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk_assessment.id"), nullable=False
    )
    new_assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("risk_assessment.id"), nullable=False
    )
    reasons: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    previous_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    review_state: Mapped[str] = mapped_column(String(32), nullable=False)


class Report(TimestampMixin, Base):
    __tablename__ = "report"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_report_public_id"),
        UniqueConstraint("slug", name="uq_report_slug"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    public_id: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    report_type: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "report_version.id",
            name="fk_report_current_version",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    resurfaced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ReportVersion(TimestampMixin, Base):
    __tablename__ = "report_version"
    __table_args__ = (
        UniqueConstraint("report_id", "version", name="uq_report_version"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    technical_analysis: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    analytical_caveats: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    source_coverage: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    generated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    model_identifier: Mapped[str | None] = mapped_column(String(255))
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_version.id")
    )
    structured_content: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    artifact_manifest: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    skill_versions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    application_version: Mapped[str] = mapped_column(
        String(128), default="unknown", nullable=False
    )


class ReportEntity(TimestampMixin, Base):
    __tablename__ = "report_entity"
    __table_args__ = (
        UniqueConstraint(
            "report_version_id",
            "entity_type",
            "entity_id",
            "role",
            name="uq_report_entity",
        ),
        Index(
            "ix_report_entity_entity",
            "entity_type",
            "entity_id",
            "report_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_version.id"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)


class Hunt(TimestampMixin, Base):
    __tablename__ = "hunt"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_version.id"),
        nullable=False,
        unique=True,
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    platforms: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    telemetry_requirements: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    lookback: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    procedure: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    expected_evidence: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    false_positives: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    escalation_criteria: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    validation_checklist: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    queries: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class Remediation(TimestampMixin, Base):
    __tablename__ = "remediation"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("report_version.id"),
        nullable=False,
        unique=True,
    )
    immediate_containment: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    exposure_reduction: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    patching: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    configuration_changes: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    credential_actions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    blocking_limitations: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    evidence_preservation: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    recovery: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    verification: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    rollback: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    references: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class Detection(TimestampMixin, Base):
    __tablename__ = "detection"
    __table_args__ = (
        UniqueConstraint(
            "report_version_id",
            "detection_type",
            "artifact_hash",
            name="uq_detection_artifact",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_version.id"), nullable=False
    )
    detection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    telemetry_requirements: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    assumptions: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    attack_references: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    validation_tool: Mapped[str | None] = mapped_column(String(128))
    validation_result: Mapped[str | None] = mapped_column(Text)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class Publication(TimestampMixin, Base):
    __tablename__ = "publication"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    report_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_version.id"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    publication_target: Mapped[str] = mapped_column(String(128), nullable=False)
    application_version: Mapped[str] = mapped_column(String(128), nullable=False)
    validation_manifest: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    rollback_target: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("report_version.id")
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)


class ModelRun(TimestampMixin, Base):
    __tablename__ = "model_run"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    triggering_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion_run.id")
    )
    model_provider: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_version_hash: Mapped[str | None] = mapped_column(String(64))
    system_prompt_hash: Mapped[str | None] = mapped_column(String(64))
    skill_version_hashes: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    cost_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    input_evidence_ids: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    output_hash: Mapped[str | None] = mapped_column(String(64))
    token_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_classification: Mapped[str | None] = mapped_column(String(128))


# Imported at the end so normalized entities share this module.s Base.
from hermes_cti.db.entity_models import (  # noqa: E402,F401
    Campaign,
    EntityEvidence,
    Infrastructure,
    Malware,
    ThreatActor,
    Tool,
)
