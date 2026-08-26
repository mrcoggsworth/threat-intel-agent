"""Normalized threat entities and first-class evidence links.

These tables keep searchable CTI relationships out of provider-specific JSONB
and give public projection code a concrete target for entity validation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from hermes_cti.db.base import Base, TimestampMixin


class ThreatActor(TimestampMixin, Base):
    __tablename__ = "threat_actor"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_threat_actor_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    attribution_state: Mapped[str] = mapped_column(
        String(32), default="unknown", nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_count: Mapped[int] = mapped_column(default=0, nullable=False)


class Malware(TimestampMixin, Base):
    __tablename__ = "malware"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_malware_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    malware_type: Mapped[str | None] = mapped_column(String(128))
    platforms: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Tool(TimestampMixin, Base):
    __tablename__ = "tool"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_tool_name"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    legitimate_use: Mapped[bool | None] = mapped_column()
    description: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaign"
    __table_args__ = (UniqueConstraint("stable_key", name="uq_campaign_stable_key"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    stable_key: Mapped[str] = mapped_column(String(255), nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
    targeting: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    confidence: Mapped[float] = mapped_column(default=0.0, nullable=False)


class Infrastructure(TimestampMixin, Base):
    __tablename__ = "infrastructure"
    __table_args__ = (
        UniqueConstraint(
            "infrastructure_type",
            "normalized_identifier",
            name="uq_infrastructure_natural_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    infrastructure_type: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_identifier: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(255))
    asn: Mapped[str | None] = mapped_column(String(64))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)


class EntityEvidence(TimestampMixin, Base):
    """Normalized provenance link for any supported intelligence entity."""

    __tablename__ = "entity_evidence"
    __table_args__ = (
        Index("ix_entity_evidence_entity", "entity_type", "entity_id"),
        CheckConstraint(
            "source_document_id IS NOT NULL OR raw_artifact_id IS NOT NULL "
            "OR evidence_claim_id IS NOT NULL OR supporting_urls IS NOT NULL "
            "OR content_hash IS NOT NULL OR provider_result_id IS NOT NULL",
            name="ck_entity_evidence_source",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_entity_evidence_confidence"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_document.id")
    )
    raw_artifact_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("raw_artifact.id")
    )
    evidence_claim_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("evidence_claim.id")
    )
    provider_result_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("enrichment_result.id")
    )
    evidence_span: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(default=1.0, nullable=False)
    origin_type: Mapped[str] = mapped_column(String(64), nullable=False)
    supporting_urls: Mapped[list[str] | None] = mapped_column(JSONB)
    content_hash: Mapped[str | None] = mapped_column(String(64))
