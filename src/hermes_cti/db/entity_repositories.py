"""Persistence boundaries for normalized CTI entities and provenance."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.db.entity_models import (
    Campaign,
    EntityEvidence,
    Infrastructure,
    Malware,
    ThreatActor,
    Tool,
)
from hermes_cti.db.lifecycle import validate_lifecycle_value
from hermes_cti.db.models import AttackTechnique, Product


class EntityRepository:
    """Idempotent upserts for stable entities and their evidence links."""

    @staticmethod
    async def _upsert(
        session: AsyncSession,
        model: Any,
        values: dict[str, Any],
        conflict_columns: list[Any],
        update_columns: set[str],
    ) -> Any:
        statement = insert(model).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={key: value for key, value in values.items() if key in update_columns}
            | {"updated_at": func.now()},
        )
        await session.execute(statement)
        return await session.scalar(
            select(model).where(
                *[
                    getattr(model, column.key) == values[column.key]
                    for column in conflict_columns
                ]
            )
        )

    async def upsert_threat_actor(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        canonical_name: str,
        normalized_name: str,
        aliases: tuple[str, ...] = (),
        attribution_state: str = "unknown",
        description: str | None = None,
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> ThreatActor:
        validate_lifecycle_value("threat_actor", "attribution_state", attribution_state)
        values = {
            "id": entity_id,
            "canonical_name": canonical_name,
            "normalized_name": normalized_name,
            "aliases": list(aliases),
            "attribution_state": attribution_state,
            "description": description,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
        }
        record = await self._upsert(
            session,
            ThreatActor,
            values,
            [ThreatActor.normalized_name],
            set(values) - {"id", "normalized_name"},
        )
        if record is None:
            raise RuntimeError("threat actor was not persisted")
        return cast(ThreatActor, record)

    async def upsert_malware(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        canonical_name: str,
        normalized_name: str,
        aliases: tuple[str, ...] = (),
        malware_type: str | None = None,
        platforms: tuple[str, ...] = (),
        description: str | None = None,
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> Malware:
        values = {
            "id": entity_id,
            "canonical_name": canonical_name,
            "normalized_name": normalized_name,
            "aliases": list(aliases),
            "malware_type": malware_type,
            "platforms": list(platforms),
            "description": description,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
        }
        record = await self._upsert(
            session,
            Malware,
            values,
            [Malware.normalized_name],
            set(values) - {"id", "normalized_name"},
        )
        if record is None:
            raise RuntimeError("malware was not persisted")
        return cast(Malware, record)

    async def upsert_tool(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        name: str,
        normalized_name: str,
        aliases: tuple[str, ...] = (),
        legitimate_use: bool | None = None,
        description: str | None = None,
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> Tool:
        values = {
            "id": entity_id,
            "name": name,
            "normalized_name": normalized_name,
            "aliases": list(aliases),
            "legitimate_use": legitimate_use,
            "description": description,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
        }
        record = await self._upsert(
            session,
            Tool,
            values,
            [Tool.normalized_name],
            set(values) - {"id", "normalized_name"},
        )
        if record is None:
            raise RuntimeError("tool was not persisted")
        return cast(Tool, record)

    async def upsert_campaign(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        stable_key: str,
        name: str | None = None,
        description: str | None = None,
        targeting: dict[str, Any] | None = None,
        state: str = "unknown",
        confidence: float = 0.0,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> Campaign:
        validate_lifecycle_value("campaign", "state", state)
        values = {
            "id": entity_id,
            "stable_key": stable_key,
            "name": name,
            "description": description,
            "targeting": targeting or {},
            "state": state,
            "confidence": confidence,
            "start_at": start_at,
            "end_at": end_at,
        }
        record = await self._upsert(
            session,
            Campaign,
            values,
            [Campaign.stable_key],
            set(values) - {"id", "stable_key"},
        )
        if record is None:
            raise RuntimeError("campaign was not persisted")
        return cast(Campaign, record)

    async def upsert_infrastructure(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        infrastructure_type: str,
        normalized_identifier: str,
        provider: str | None = None,
        asn: str | None = None,
        state: str = "unknown",
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
    ) -> Infrastructure:
        validate_lifecycle_value("infrastructure", "state", state)
        values = {
            "id": entity_id,
            "infrastructure_type": infrastructure_type,
            "normalized_identifier": normalized_identifier,
            "provider": provider,
            "asn": asn,
            "state": state,
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
        }
        record = await self._upsert(
            session,
            Infrastructure,
            values,
            [Infrastructure.infrastructure_type, Infrastructure.normalized_identifier],
            set(values) - {"id", "infrastructure_type", "normalized_identifier"},
        )
        if record is None:
            raise RuntimeError("infrastructure was not persisted")
        return cast(Infrastructure, record)

    async def upsert_product(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        vendor: str,
        product: str,
        normalized_vendor: str,
        normalized_product: str,
        ecosystem: str = "unknown",
        product_type: str | None = None,
        canonical_identifiers: dict[str, Any] | None = None,
    ) -> Product:
        values = {
            "id": entity_id,
            "vendor": vendor,
            "product": product,
            "normalized_vendor": normalized_vendor,
            "normalized_product": normalized_product,
            "ecosystem": ecosystem,
            "product_type": product_type,
            "canonical_identifiers": canonical_identifiers or {},
        }
        record = await self._upsert(
            session,
            Product,
            values,
            [Product.normalized_vendor, Product.normalized_product, Product.ecosystem],
            set(values)
            - {"id", "normalized_vendor", "normalized_product", "ecosystem"},
        )
        if record is None:
            raise RuntimeError("product was not persisted")
        return cast(Product, record)

    async def upsert_attack_technique(
        self,
        session: AsyncSession,
        *,
        entity_id: UUID,
        attack_id: str,
        framework_version: str,
        name: str,
        tactic: str | None = None,
        platform: str | None = None,
        description_reference: str | None = None,
    ) -> AttackTechnique:
        values = {
            "id": entity_id,
            "attack_id": attack_id,
            "framework_version": framework_version,
            "name": name,
            "tactic": tactic,
            "platform": platform,
            "description_reference": description_reference,
        }
        record = await self._upsert(
            session,
            AttackTechnique,
            values,
            [AttackTechnique.attack_id, AttackTechnique.framework_version],
            set(values) - {"id", "attack_id", "framework_version"},
        )
        if record is None:
            raise RuntimeError("attack technique was not persisted")
        return cast(AttackTechnique, record)

    async def link_evidence(
        self,
        session: AsyncSession,
        *,
        evidence_id: UUID,
        entity_type: str,
        entity_id: UUID,
        source_document_id: UUID | None = None,
        raw_artifact_id: UUID | None = None,
        evidence_claim_id: UUID | None = None,
        evidence_span: dict[str, Any] | None = None,
        first_seen_at: datetime | None = None,
        last_seen_at: datetime | None = None,
        confidence: float = 1.0,
        origin_type: str = "deterministic_service",
        supporting_urls: tuple[str, ...] = (),
        content_hash: str | None = None,
    ) -> EntityEvidence:
        if not any(
            (source_document_id, raw_artifact_id, evidence_claim_id, supporting_urls)
        ):
            raise ValueError(
                "evidence must reference a source, claim, or supporting URL"
            )
        values = {
            "id": evidence_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_document_id": source_document_id,
            "raw_artifact_id": raw_artifact_id,
            "evidence_claim_id": evidence_claim_id,
            "evidence_span": evidence_span or {},
            "first_seen_at": first_seen_at,
            "last_seen_at": last_seen_at,
            "confidence": confidence,
            "origin_type": origin_type,
            "supporting_urls": list(supporting_urls) or None,
            "content_hash": content_hash,
        }
        await session.execute(
            insert(EntityEvidence)
            .values(values)
            .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
        )
        record = await session.scalar(
            select(EntityEvidence).where(EntityEvidence.id == evidence_id)
        )
        if record is None:
            raise RuntimeError("entity evidence was not persisted")
        return record
