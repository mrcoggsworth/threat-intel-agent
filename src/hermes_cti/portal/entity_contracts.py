"""Safe public projections for approved entities and relationships."""

from __future__ import annotations

from datetime import date

from pydantic import Field

from hermes_cti.models.contracts import (
    Confidence,
    ContractModel,
    EntityType,
    RelationshipOrigin,
    UTCDateTime,
)


class PublicVulnerability(ContractModel):
    """Analyst-safe vulnerability fields for the public entity projection."""

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


class PublicEntity(ContractModel):
    """Public natural-key projection; internal database IDs are omitted."""

    entity_type: EntityType
    public_key: str
    display_name: str
    first_seen_at: UTCDateTime | None = None
    last_seen_at: UTCDateTime | None = None
    source_count: int = Field(default=0, ge=0)
    vulnerability: PublicVulnerability | None = None


class PublicEntityReference(ContractModel):
    """Safe relationship endpoint reference."""

    entity_type: EntityType
    public_key: str
    display_name: str


class PublicRelationship(ContractModel):
    """Reviewed, active relationship with public endpoint keys only."""

    source: PublicEntityReference
    relationship_type: str
    target: PublicEntityReference
    direction: str
    origin: RelationshipOrigin
    confidence: Confidence
    first_seen_at: UTCDateTime | None = None
    last_seen_at: UTCDateTime | None = None


class PublicRelationshipPage(ContractModel):
    """Bounded public relationship response."""

    items: tuple[PublicRelationship, ...]
    limit: int = Field(..., ge=1, le=100)
