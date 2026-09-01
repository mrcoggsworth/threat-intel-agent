"""Published-only entity and relationship read projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.db.entity_models import (
    Campaign,
    Infrastructure,
    Malware,
    ThreatActor,
    Tool,
)
from hermes_cti.db.models import (
    AttackTechnique,
    Indicator,
    Product,
    Relationship,
    Report,
    ReportEntity,
    ReportVersion,
    Vulnerability,
)
from hermes_cti.models.contracts import EntityType, ReviewState


@dataclass(frozen=True, slots=True)
class PublicEntityRow:
    entity_type: EntityType
    entity_id: UUID
    public_key: str
    display_name: str
    first_seen_at: Any = None
    last_seen_at: Any = None
    source_count: int = 0
    vulnerability: Any = None


@dataclass(frozen=True, slots=True)
class PublicRelationshipRow:
    relationship: Relationship
    source: PublicEntityRow
    target: PublicEntityRow


def _vulnerability_projection(kind: EntityType, record: Any) -> dict[str, Any] | None:
    if kind is not EntityType.VULNERABILITY:
        return None
    return {
        "cvss_score": record.cvss_score,
        "cvss_version": record.cvss_version,
        "cvss_vector": record.cvss_vector,
        "epss_score": record.epss_score,
        "epss_percentile": record.epss_percentile,
        "cwe_ids": tuple(record.cwe_ids or ()),
        "known_exploited": record.known_exploited,
        "exploitation_state": record.exploitation_state,
        "kev_date_added": record.kev_date_added,
        "kev_due_date": record.kev_due_date,
        "kev_required_action": record.kev_required_action,
    }


def _published_membership(entity_type: Any, entity_id: Any) -> Any:
    return exists(
        select(ReportEntity.id)
        .join(ReportVersion, ReportVersion.id == ReportEntity.report_version_id)
        .join(Report, Report.id == ReportVersion.report_id)
        .where(
            Report.state == "published",
            ReportEntity.entity_type == entity_type,
            ReportEntity.entity_id == entity_id,
        )
    )


class SqlEntityReadRepository:
    """Resolve only entities represented by a published report version."""

    async def get_public_entity(
        self, session: AsyncSession, entity_type: str, identifier: str
    ) -> PublicEntityRow | None:
        try:
            kind = EntityType(entity_type)
        except ValueError:
            return None

        record: Any = None
        public_key = identifier
        display_name = identifier
        first_seen = None
        last_seen = None
        source_count = 0

        if kind is EntityType.INDICATOR:
            record = await session.scalar(
                select(Indicator).where(
                    Indicator.public_visibility.is_(True),
                    Indicator.safe_display_value == identifier,
                    _published_membership(kind.value, Indicator.id),
                )
            )
            if record:
                public_key, display_name = (
                    record.safe_display_value,
                    record.safe_display_value,
                )
                first_seen, last_seen = record.first_seen_at, record.last_seen_at
        elif kind is EntityType.VULNERABILITY:
            record = await session.scalar(
                select(Vulnerability).where(
                    Vulnerability.cve_id == identifier.upper(),
                    _published_membership(kind.value, Vulnerability.id),
                )
            )
            if record:
                public_key = display_name = record.cve_id
                first_seen, last_seen = record.published_at, record.modified_at
        elif kind is EntityType.PRODUCT:
            parts = identifier.split("|", 2)
            if len(parts) == 3:
                record = await session.scalar(
                    select(Product).where(
                        Product.normalized_vendor == parts[0],
                        Product.normalized_product == parts[1],
                        Product.ecosystem == parts[2],
                        _published_membership(kind.value, Product.id),
                    )
                )
            if record:
                public_key = "|".join(
                    (
                        record.normalized_vendor,
                        record.normalized_product,
                        record.ecosystem,
                    )
                )
                display_name = f"{record.vendor} {record.product}"
        elif kind is EntityType.TECHNIQUE:
            parts = identifier.split("|", 1)
            if len(parts) == 2:
                record = await session.scalar(
                    select(AttackTechnique).where(
                        AttackTechnique.attack_id == parts[0],
                        AttackTechnique.framework_version == parts[1],
                        _published_membership(kind.value, AttackTechnique.id),
                    )
                )
            if record:
                public_key = f"{record.attack_id}|{record.framework_version}"
                display_name = record.name
        elif kind is EntityType.ACTOR:
            record = await session.scalar(
                select(ThreatActor).where(
                    ThreatActor.normalized_name == identifier,
                    _published_membership(kind.value, ThreatActor.id),
                )
            )
            if record:
                display_name = record.canonical_name
                first_seen, last_seen, source_count = (
                    record.first_seen_at,
                    record.last_seen_at,
                    record.source_count,
                )
        elif kind is EntityType.MALWARE:
            record = await session.scalar(
                select(Malware).where(
                    Malware.normalized_name == identifier,
                    _published_membership(kind.value, Malware.id),
                )
            )
            if record:
                display_name = record.canonical_name
                first_seen, last_seen = record.first_seen_at, record.last_seen_at
        elif kind is EntityType.TOOL:
            record = await session.scalar(
                select(Tool).where(
                    Tool.normalized_name == identifier,
                    _published_membership(kind.value, Tool.id),
                )
            )
            if record:
                display_name = record.name
                first_seen, last_seen = record.first_seen_at, record.last_seen_at
        elif kind is EntityType.CAMPAIGN:
            record = await session.scalar(
                select(Campaign).where(
                    Campaign.stable_key == identifier,
                    _published_membership(kind.value, Campaign.id),
                )
            )
            if record:
                display_name = record.name or record.stable_key
                first_seen, last_seen = record.start_at, record.end_at
        elif kind is EntityType.INFRASTRUCTURE:
            record = await session.scalar(
                select(Infrastructure).where(
                    Infrastructure.normalized_identifier == identifier,
                    _published_membership(kind.value, Infrastructure.id),
                )
            )
            if record:
                display_name = record.normalized_identifier
                first_seen, last_seen = record.first_seen_at, record.last_seen_at

        if record is None:
            return None
        return PublicEntityRow(
            entity_type=kind,
            entity_id=record.id,
            public_key=public_key,
            display_name=display_name,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            source_count=source_count,
            vulnerability=_vulnerability_projection(kind, record),
        )

    async def get_public_entity_by_id(
        self, session: AsyncSession, entity_type: str, entity_id: UUID
    ) -> PublicEntityRow | None:
        """Resolve a relationship endpoint without exposing its database ID."""
        try:
            kind = EntityType(entity_type)
        except ValueError:
            return None
        models: dict[EntityType, Any] = {
            EntityType.INDICATOR: Indicator,
            EntityType.VULNERABILITY: Vulnerability,
            EntityType.PRODUCT: Product,
            EntityType.TECHNIQUE: AttackTechnique,
            EntityType.ACTOR: ThreatActor,
            EntityType.MALWARE: Malware,
            EntityType.TOOL: Tool,
            EntityType.CAMPAIGN: Campaign,
            EntityType.INFRASTRUCTURE: Infrastructure,
        }
        model = models.get(kind)
        if model is None:
            return None
        record = await session.scalar(
            select(model).where(
                model.id == entity_id, _published_membership(kind.value, entity_id)
            )
        )
        if record is None:
            return None
        if kind is EntityType.INDICATOR:
            key = display = record.safe_display_value
            first_seen, last_seen, count = record.first_seen_at, record.last_seen_at, 0
        elif kind is EntityType.VULNERABILITY:
            key = display = record.cve_id
            first_seen, last_seen, count = record.published_at, record.modified_at, 0
        elif kind is EntityType.PRODUCT:
            key = "|".join(
                (record.normalized_vendor, record.normalized_product, record.ecosystem)
            )
            display, first_seen, last_seen, count = (
                f"{record.vendor} {record.product}",
                None,
                None,
                0,
            )
        elif kind is EntityType.TECHNIQUE:
            key = f"{record.attack_id}|{record.framework_version}"
            display, first_seen, last_seen, count = record.name, None, None, 0
        elif kind is EntityType.ACTOR:
            key, display = record.normalized_name, record.canonical_name
            first_seen, last_seen, count = (
                record.first_seen_at,
                record.last_seen_at,
                record.source_count,
            )
        elif kind is EntityType.MALWARE:
            key, display = record.normalized_name, record.canonical_name
            first_seen, last_seen, count = record.first_seen_at, record.last_seen_at, 0
        elif kind is EntityType.TOOL:
            key, display = record.normalized_name, record.name
            first_seen, last_seen, count = record.first_seen_at, record.last_seen_at, 0
        elif kind is EntityType.CAMPAIGN:
            key, display = record.stable_key, record.name or record.stable_key
            first_seen, last_seen, count = record.start_at, record.end_at, 0
        else:
            key = display = record.normalized_identifier
            first_seen, last_seen, count = record.first_seen_at, record.last_seen_at, 0
        return PublicEntityRow(
            kind,
            entity_id,
            key,
            display,
            first_seen,
            last_seen,
            count,
            _vulnerability_projection(kind, record),
        )

    async def public_relationships(
        self,
        session: AsyncSession,
        *,
        entity_type: str | None = None,
        identifier: str | None = None,
        limit: int = 100,
    ) -> tuple[PublicRelationshipRow, ...]:
        statement = select(Relationship).where(
            Relationship.active.is_(True),
            Relationship.review_state == ReviewState.REVIEWED.value,
            _published_membership(
                Relationship.source_entity_type, Relationship.source_entity_id
            ),
            _published_membership(
                Relationship.target_entity_type, Relationship.target_entity_id
            ),
        )
        if entity_type is not None and identifier is not None:
            entity = await self.get_public_entity(session, entity_type, identifier)
            if entity is None:
                return ()
            statement = statement.where(
                (
                    (Relationship.source_entity_type == entity.entity_type.value)
                    & (Relationship.source_entity_id == entity.entity_id)
                )
                | (
                    (Relationship.target_entity_type == entity.entity_type.value)
                    & (Relationship.target_entity_id == entity.entity_id)
                )
            )
        result = await session.execute(
            statement.order_by(Relationship.id).limit(min(limit, 100))
        )
        rows: list[PublicRelationshipRow] = []
        for relationship in result.scalars():
            source = await self.get_public_entity_by_id(
                session, relationship.source_entity_type, relationship.source_entity_id
            )
            target = await self.get_public_entity_by_id(
                session, relationship.target_entity_type, relationship.target_entity_id
            )
            if source is not None and target is not None:
                rows.append(PublicRelationshipRow(relationship, source, target))
        return tuple(rows)
