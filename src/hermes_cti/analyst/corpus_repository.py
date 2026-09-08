"""Bounded, read-only historical corpus queries for the analyst profile."""

from __future__ import annotations

import base64
import binascii
import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, exists, not_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.analyst.contracts import (
    AnalystActor,
    AnalystCampaign,
    AnalystContradiction,
    AnalystCorpusPage,
    AnalystCVE,
    AnalystEvidence,
    AnalystIOC,
    AnalystMalware,
    AnalystProduct,
    AnalystProductVersion,
    AnalystRelationship,
    AnalystTechnique,
    AnalystTool,
    AnalystURL,
    CorpusProvenance,
    CorpusQuery,
    CorpusResource,
)
from hermes_cti.db.entity_models import (
    Campaign,
    EntityEvidence,
    Malware,
    ThreatActor,
    Tool,
)
from hermes_cti.db.lifecycle import RecordStatus
from hermes_cti.db.models import (
    AffectedProduct,
    AttackTechnique,
    CorrelationContradictionRecord,
    EvidenceClaim,
    Indicator,
    Product,
    Relationship,
    RelationshipEvidence,
    Report,
    ReportEntity,
    ReportVersion,
    SourceDocument,
    Vulnerability,
)

QUERY_TIMEOUT_MS = 2_500
_SECRET_PATTERN = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|authorization|private[_-]?key)\s*[:=]\s*([^\s,;]+)"
)


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


def _encode_cursor(resource: CorpusResource, row: Any) -> str:
    payload = {
        "resource": resource.value,
        "updated_at": row.updated_at.isoformat(),
        "id": str(row.id),
    }
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str | None, resource: CorpusResource
) -> tuple[datetime, UUID] | None:
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if payload.get("resource") != resource.value:
            raise ValueError("cursor belongs to a different corpus resource")
        updated_at = datetime.fromisoformat(str(payload["updated_at"]))
        identifier = UUID(str(payload["id"]))
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise ValueError("cursor is invalid or expired") from exc
    if updated_at.tzinfo is None:
        raise ValueError("cursor timestamp must include timezone")
    return updated_at, identifier


def _keyset(statement: Any, model: Any, cursor: tuple[datetime, UUID] | None) -> Any:
    if cursor is None:
        return statement
    updated_at, identifier = cursor
    return statement.where(
        or_(
            model.updated_at < updated_at,
            and_(model.updated_at == updated_at, model.id > identifier),
        )
    )


def _redact(value: str | None) -> str | None:
    return _SECRET_PATTERN.sub(r"\1=[REDACTED]", value) if value is not None else None


def _common(
    statement: Any,
    model: Any,
    query: CorpusQuery,
    *,
    search_columns: tuple[Any, ...] = (),
    entity_type: str | None = None,
) -> Any:
    if query.record_status is not None:
        statement = statement.where(model.record_status == query.record_status.value)
    if query.entity_id is not None and entity_type is not None:
        statement = statement.where(model.id == query.entity_id)
    if query.search is not None:
        statement = statement.where(
            or_(*(column.ilike(f"{query.search}%") for column in search_columns))
        )
    if model is Vulnerability and query.cve_id is not None:
        statement = statement.where(model.cve_id == query.cve_id)
    if model is Indicator:
        if query.indicator_type is not None:
            statement = statement.where(model.indicator_type == query.indicator_type)
        if query.value is not None:
            statement = statement.where(model.safe_display_value == query.value)
    if model is CorrelationContradictionRecord:
        if query.entity_type is not None:
            statement = statement.where(
                model.subject_entity_type == query.entity_type.value
            )
        if query.entity_id is not None:
            statement = statement.where(model.subject_entity_id == query.entity_id)
        if query.review_state is not None:
            statement = statement.where(model.review_state == query.review_state.value)
    if query.published is not None and entity_type is not None:
        membership = _published_membership(entity_type, model.id)
        statement = statement.where(membership if query.published else not_(membership))
    return statement


def _base(row: Any, provenance: CorpusProvenance) -> dict[str, Any]:
    return {
        "id": row.id,
        "record_status": RecordStatus(row.record_status),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "provenance": provenance,
    }


def _uuid_values(values: Any) -> tuple[UUID, ...]:
    result: list[UUID] = []
    for value in values or ():
        try:
            result.append(UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    return tuple(result)


class CorpusRepository:
    """Read-only repository enforcing bounds, lifecycle, and publication policy."""

    async def _set_timeout(self, session: AsyncSession) -> None:
        await session.execute(
            text("SELECT set_config($$statement_timeout$$, :timeout_ms, true)"),
            {"timeout_ms": str(QUERY_TIMEOUT_MS)},
        )

    async def _rows(
        self,
        session: AsyncSession,
        resource: CorpusResource,
        model: Any,
        query: CorpusQuery,
        *,
        search_columns: tuple[Any, ...] = (),
        entity_type: str | None = None,
    ) -> tuple[Any, ...]:
        cursor = _decode_cursor(query.cursor, resource)
        statement = _common(
            select(model),
            model,
            query,
            search_columns=search_columns,
            entity_type=entity_type,
        )
        statement = _keyset(statement, model, cursor)
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(model.updated_at.desc(), model.id).limit(query.limit + 1)
        )
        return tuple(result.scalars().all())

    @staticmethod
    def _cursor_row(row: Any) -> Any:
        return row[0] if isinstance(row, tuple) or hasattr(row, "_mapping") else row

    async def _provenance(
        self,
        session: AsyncSession,
        entity_type: str,
        entity_ids: tuple[UUID, ...],
    ) -> dict[UUID, CorpusProvenance]:
        if not entity_ids:
            return {}
        result = await session.execute(
            select(EntityEvidence)
            .where(
                EntityEvidence.entity_type == entity_type,
                EntityEvidence.entity_id.in_(entity_ids),
            )
            .order_by(
                EntityEvidence.entity_id,
                EntityEvidence.updated_at,
                EntityEvidence.id,
            )
        )
        links = tuple(result.scalars().all())
        document_ids = tuple(
            row.source_document_id
            for row in links
            if row.source_document_id is not None
        )
        documents: dict[UUID, str] = {}
        if document_ids:
            document_result = await session.execute(
                select(SourceDocument.id, SourceDocument.canonical_url).where(
                    SourceDocument.id.in_(document_ids)
                )
            )
            documents = {row[0]: row[1] for row in document_result.all()}
        values: dict[UUID, dict[str, Any]] = defaultdict(
            lambda: {
                "source_document_ids": set(),
                "evidence_claim_ids": set(),
                "provider_result_ids": set(),
                "source_urls": set(),
                "first_seen_at": None,
                "last_seen_at": None,
            }
        )
        for row in links:
            item = values[row.entity_id]
            if row.source_document_id is not None:
                item["source_document_ids"].add(row.source_document_id)
                if row.source_document_id in documents:
                    item["source_urls"].add(documents[row.source_document_id])
            if row.evidence_claim_id is not None:
                item["evidence_claim_ids"].add(row.evidence_claim_id)
            if row.provider_result_id is not None:
                item["provider_result_ids"].add(row.provider_result_id)
            for url in row.supporting_urls or ():
                item["source_urls"].add(url)
            if row.first_seen_at is not None and (
                item["first_seen_at"] is None
                or row.first_seen_at < item["first_seen_at"]
            ):
                item["first_seen_at"] = row.first_seen_at
            if row.last_seen_at is not None and (
                item["last_seen_at"] is None or row.last_seen_at > item["last_seen_at"]
            ):
                item["last_seen_at"] = row.last_seen_at
        return {
            entity_id: CorpusProvenance(
                source_document_ids=tuple(sorted(item["source_document_ids"])),
                evidence_claim_ids=tuple(sorted(item["evidence_claim_ids"])),
                provider_result_ids=tuple(sorted(item["provider_result_ids"])),
                source_urls=tuple(sorted(item["source_urls"])),
                first_seen_at=item["first_seen_at"],
                last_seen_at=item["last_seen_at"],
            )
            for entity_id, item in values.items()
        }

    def _page(
        self,
        resource: CorpusResource,
        query: CorpusQuery,
        rows: tuple[Any, ...],
        items: tuple[Any, ...],
    ) -> Any:
        visible_rows = rows[: query.limit]
        has_more = len(rows) > query.limit
        return AnalystCorpusPage.model_construct(
            resource=resource,
            items=items[: query.limit],
            limit=query.limit,
            returned=min(len(items), query.limit),
            has_more=has_more,
            next_cursor=(
                _encode_cursor(resource, self._cursor_row(visible_rows[-1]))
                if has_more
                else None
            ),
            query_timeout_ms=QUERY_TIMEOUT_MS,
            query=query,
        )

    async def cves(self, session: AsyncSession, query: CorpusQuery) -> Any:
        rows = await self._rows(
            session,
            CorpusResource.CVES,
            Vulnerability,
            query,
            search_columns=(Vulnerability.cve_id, Vulnerability.description),
            entity_type="vulnerability",
        )
        provenance = await self._provenance(
            session, "vulnerability", tuple(row.id for row in rows[: query.limit])
        )
        items = tuple(
            AnalystCVE(
                **_base(row, provenance.get(row.id, CorpusProvenance())),
                cve_id=row.cve_id,
                description=row.description,
                published_at=row.published_at,
                modified_at=row.modified_at,
                cvss_score=row.cvss_score,
                epss_score=row.epss_score,
                known_exploited=row.known_exploited,
                exploitation_state=row.exploitation_state,
            )
            for row in rows
        )
        return self._page(CorpusResource.CVES, query, rows, items)

    async def iocs(self, session: AsyncSession, query: CorpusQuery) -> Any:
        rows = await self._rows(
            session,
            CorpusResource.IOCS,
            Indicator,
            query,
            search_columns=(Indicator.safe_display_value,),
            entity_type="indicator",
        )
        provenance = await self._provenance(
            session, "indicator", tuple(row.id for row in rows[: query.limit])
        )
        items = tuple(
            AnalystIOC(
                **_base(row, provenance.get(row.id, CorpusProvenance())),
                indicator_type=row.indicator_type,
                value=row.safe_display_value,
                validation_state=row.validation_state,
                public_visibility=row.public_visibility,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
            )
            for row in rows
        )
        return self._page(CorpusResource.IOCS, query, rows, items)

    async def products(self, session: AsyncSession, query: CorpusQuery) -> Any:
        statement = select(Product)
        if query.record_status is not None:
            statement = statement.where(
                Product.record_status == query.record_status.value
            )
        if query.vendor is not None:
            statement = statement.where(
                Product.normalized_vendor == query.vendor.casefold()
            )
        if query.product is not None:
            statement = statement.where(
                Product.normalized_product == query.product.casefold()
            )
        if query.ecosystem is not None:
            statement = statement.where(Product.ecosystem == query.ecosystem)
        if query.search is not None:
            statement = statement.where(
                or_(
                    Product.vendor.ilike(f"{query.search}%"),
                    Product.product.ilike(f"{query.search}%"),
                )
            )
        if query.entity_id is not None:
            statement = statement.where(Product.id == query.entity_id)
        if query.published is not None:
            membership = _published_membership("product", Product.id)
            statement = statement.where(
                membership if query.published else not_(membership)
            )
        cursor = _decode_cursor(query.cursor, CorpusResource.PRODUCTS)
        statement = _keyset(statement, Product, cursor)
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(Product.updated_at.desc(), Product.id).limit(
                query.limit + 1
            )
        )
        rows = tuple(result.scalars().all())
        ids = tuple(row.id for row in rows[: query.limit])
        provenance = await self._provenance(session, "product", ids)
        versions: dict[UUID, list[AnalystProductVersion]] = defaultdict(list)
        if ids:
            version_result = await session.execute(
                select(AffectedProduct)
                .where(AffectedProduct.product_id.in_(ids))
                .order_by(AffectedProduct.product_id, AffectedProduct.id)
            )
            for row in version_result.scalars():
                versions[row.product_id].append(
                    AnalystProductVersion(
                        version_range=row.version_range,
                        cpe=row.cpe,
                        vulnerability_id=row.vulnerability_id,
                        affected_status=row.affected_status,
                        confidence=row.confidence,
                        remediation_available=row.remediation_available,
                    )
                )
        items = tuple(
            AnalystProduct(
                **_base(row, provenance.get(row.id, CorpusProvenance())),
                vendor=row.vendor,
                product=row.product,
                ecosystem=row.ecosystem,
                product_type=row.product_type,
                canonical_identifiers=row.canonical_identifiers,
                versions=tuple(versions.get(row.id, ())),
            )
            for row in rows
        )
        return self._page(CorpusResource.PRODUCTS, query, rows, items)

    async def _simple_entities(
        self,
        session: AsyncSession,
        resource: CorpusResource,
        model: Any,
        entity_type: str,
        query: CorpusQuery,
        search_columns: tuple[Any, ...],
        mapper: Any,
    ) -> Any:
        rows = await self._rows(
            session,
            resource,
            model,
            query,
            search_columns=search_columns,
            entity_type=entity_type,
        )
        provenance = await self._provenance(
            session, entity_type, tuple(row.id for row in rows[: query.limit])
        )
        items = tuple(
            mapper(row, provenance.get(row.id, CorpusProvenance())) for row in rows
        )
        return self._page(resource, query, rows, items)

    async def actors(self, session: AsyncSession, query: CorpusQuery) -> Any:
        return await self._simple_entities(
            session,
            CorpusResource.ACTORS,
            ThreatActor,
            "actor",
            query,
            (ThreatActor.canonical_name, ThreatActor.normalized_name),
            lambda row, p: AnalystActor(
                **_base(row, p),
                canonical_name=row.canonical_name,
                normalized_name=row.normalized_name,
                aliases=tuple(row.aliases or ()),
                attribution_state=row.attribution_state,
                description=row.description,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                source_count=row.source_count,
            ),
        )

    async def malware(self, session: AsyncSession, query: CorpusQuery) -> Any:
        return await self._simple_entities(
            session,
            CorpusResource.MALWARE,
            Malware,
            "malware",
            query,
            (Malware.canonical_name, Malware.normalized_name),
            lambda row, p: AnalystMalware(
                **_base(row, p),
                canonical_name=row.canonical_name,
                normalized_name=row.normalized_name,
                aliases=tuple(row.aliases or ()),
                malware_type=row.malware_type,
                platforms=tuple(row.platforms or ()),
                description=row.description,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
            ),
        )

    async def tools(self, session: AsyncSession, query: CorpusQuery) -> Any:
        return await self._simple_entities(
            session,
            CorpusResource.TOOLS,
            Tool,
            "tool",
            query,
            (Tool.name, Tool.normalized_name),
            lambda row, p: AnalystTool(
                **_base(row, p),
                name=row.name,
                normalized_name=row.normalized_name,
                aliases=tuple(row.aliases or ()),
                legitimate_use=row.legitimate_use,
                description=row.description,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
            ),
        )

    async def campaigns(self, session: AsyncSession, query: CorpusQuery) -> Any:
        return await self._simple_entities(
            session,
            CorpusResource.CAMPAIGNS,
            Campaign,
            "campaign",
            query,
            (Campaign.name, Campaign.stable_key),
            lambda row, p: AnalystCampaign(
                **_base(row, p),
                stable_key=row.stable_key,
                name=row.name,
                description=row.description,
                targeting=row.targeting,
                state=row.state,
                confidence=row.confidence,
                start_at=row.start_at,
                end_at=row.end_at,
            ),
        )

    async def techniques(self, session: AsyncSession, query: CorpusQuery) -> Any:
        statement = select(AttackTechnique)
        if query.record_status is not None:
            statement = statement.where(
                AttackTechnique.record_status == query.record_status.value
            )
        if query.attack_id is not None:
            statement = statement.where(AttackTechnique.attack_id == query.attack_id)
        if query.framework_version is not None:
            statement = statement.where(
                AttackTechnique.framework_version == query.framework_version
            )
        if query.search is not None:
            statement = statement.where(
                or_(
                    AttackTechnique.attack_id.ilike(f"{query.search}%"),
                    AttackTechnique.name.ilike(f"{query.search}%"),
                )
            )
        if query.entity_id is not None:
            statement = statement.where(AttackTechnique.id == query.entity_id)
        if query.published is not None:
            membership = _published_membership("technique", AttackTechnique.id)
            statement = statement.where(
                membership if query.published else not_(membership)
            )
        cursor = _decode_cursor(query.cursor, CorpusResource.TECHNIQUES)
        statement = _keyset(statement, AttackTechnique, cursor)
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(
                AttackTechnique.updated_at.desc(), AttackTechnique.id
            ).limit(query.limit + 1)
        )
        rows = tuple(result.scalars().all())
        provenance = await self._provenance(
            session, "technique", tuple(row.id for row in rows[: query.limit])
        )
        items = tuple(
            AnalystTechnique(
                **_base(row, provenance.get(row.id, CorpusProvenance())),
                attack_id=row.attack_id,
                framework_version=row.framework_version,
                name=row.name,
                tactic=row.tactic,
                platform=row.platform,
                description_reference=row.description_reference,
            )
            for row in rows
        )
        return self._page(CorpusResource.TECHNIQUES, query, rows, items)

    async def urls(self, session: AsyncSession, query: CorpusQuery) -> Any:
        statement = select(SourceDocument)
        if query.record_status is not None:
            statement = statement.where(
                SourceDocument.record_status == query.record_status.value
            )
        if query.source_id is not None:
            statement = statement.where(SourceDocument.source_id == query.source_id)
        if query.published is not None:
            statement = statement.where(
                SourceDocument.published_at.is_not(None)
                if query.published
                else SourceDocument.published_at.is_(None)
            )
        if query.search is not None:
            statement = statement.where(
                or_(
                    SourceDocument.canonical_url.ilike(f"{query.search}%"),
                    SourceDocument.title.ilike(f"{query.search}%"),
                )
            )
        cursor = _decode_cursor(query.cursor, CorpusResource.URLS)
        statement = _keyset(statement, SourceDocument, cursor)
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(
                SourceDocument.updated_at.desc(), SourceDocument.id
            ).limit(query.limit + 1)
        )
        rows = tuple(result.scalars().all())
        items = tuple(
            AnalystURL(
                **_base(
                    row,
                    CorpusProvenance(
                        source_document_ids=(row.id,),
                        source_urls=(row.canonical_url,),
                        first_seen_at=row.published_at,
                        last_seen_at=row.retrieved_at,
                    ),
                ),
                source_id=row.source_id,
                canonical_url=row.canonical_url,
                title=row.title,
                published_at=row.published_at,
                retrieved_at=row.retrieved_at,
                content_type=row.content_type,
                document_type=row.document_type,
                normalized_content_hash=row.normalized_content_hash,
                supersedes_id=row.supersedes_id,
            )
            for row in rows
        )
        return self._page(CorpusResource.URLS, query, rows, items)

    async def evidence(self, session: AsyncSession, query: CorpusQuery) -> Any:
        cursor = _decode_cursor(query.cursor, CorpusResource.EVIDENCE)
        statement = select(EvidenceClaim, SourceDocument).join(
            SourceDocument, SourceDocument.id == EvidenceClaim.source_document_id
        )
        if query.record_status is not None:
            statement = statement.where(
                EvidenceClaim.record_status == query.record_status.value
            )
        if query.source_id is not None:
            statement = statement.where(SourceDocument.source_id == query.source_id)
        if query.entity_type is not None:
            statement = statement.where(
                EvidenceClaim.subject_entity_type == query.entity_type.value
            )
        if query.entity_id is not None:
            statement = statement.where(
                EvidenceClaim.subject_entity_id == query.entity_id
            )
        if query.search is not None:
            statement = statement.where(
                EvidenceClaim.evidence_text.ilike(f"{query.search}%")
            )
        if query.published is not None:
            statement = statement.where(
                SourceDocument.published_at.is_not(None)
                if query.published
                else SourceDocument.published_at.is_(None)
            )
        if cursor is not None:
            updated_at, identifier = cursor
            statement = statement.where(
                or_(
                    EvidenceClaim.updated_at < updated_at,
                    and_(
                        EvidenceClaim.updated_at == updated_at,
                        EvidenceClaim.id > identifier,
                    ),
                )
            )
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(EvidenceClaim.updated_at.desc(), EvidenceClaim.id).limit(
                query.limit + 1
            )
        )
        rows = tuple(result.all())
        items = tuple(
            AnalystEvidence(
                id=claim.id,
                record_status=RecordStatus(claim.record_status),
                created_at=claim.created_at,
                updated_at=claim.updated_at,
                provenance=CorpusProvenance(
                    source_document_ids=(document.id,),
                    evidence_claim_ids=(claim.id,),
                    source_urls=(document.canonical_url,),
                    first_seen_at=document.published_at,
                    last_seen_at=document.retrieved_at,
                ),
                source_document_id=document.id,
                source_id=document.source_id,
                canonical_url=document.canonical_url,
                claim_type=claim.claim_type,
                subject_entity_type=claim.subject_entity_type,
                subject_entity_id=claim.subject_entity_id,
                predicate=claim.predicate,
                object_entity_type=claim.object_entity_type,
                object_entity_id=claim.object_entity_id,
                object_literal=_redact(claim.object_literal),
                evidence_text=_redact(claim.evidence_text) or "",
                start_offset=claim.start_offset,
                end_offset=claim.end_offset,
                extraction_origin=claim.extraction_origin,
                confidence=claim.confidence,
            )
            for claim, document in rows
        )
        return self._page(CorpusResource.EVIDENCE, query, rows, items)

    async def relationships(self, session: AsyncSession, query: CorpusQuery) -> Any:
        statement = select(Relationship)
        if query.record_status is not None:
            statement = statement.where(
                Relationship.record_status == query.record_status.value
            )
        if query.review_state is not None:
            statement = statement.where(
                Relationship.review_state == query.review_state.value
            )
        if query.relationship_type is not None:
            statement = statement.where(
                Relationship.relationship_type == query.relationship_type
            )
        if query.search is not None:
            statement = statement.where(
                or_(
                    Relationship.relationship_type.ilike(f"{query.search}%"),
                    Relationship.origin_rule.ilike(f"{query.search}%"),
                )
            )
        if query.entity_type is not None and query.entity_id is not None:
            statement = statement.where(
                or_(
                    and_(
                        Relationship.source_entity_type == query.entity_type.value,
                        Relationship.source_entity_id == query.entity_id,
                    ),
                    and_(
                        Relationship.target_entity_type == query.entity_type.value,
                        Relationship.target_entity_id == query.entity_id,
                    ),
                )
            )
        if query.published is not None:
            membership = and_(
                _published_membership(
                    Relationship.source_entity_type, Relationship.source_entity_id
                ),
                _published_membership(
                    Relationship.target_entity_type, Relationship.target_entity_id
                ),
            )
            statement = statement.where(
                membership if query.published else not_(membership)
            )
        cursor = _decode_cursor(query.cursor, CorpusResource.RELATIONSHIPS)
        statement = _keyset(statement, Relationship, cursor)
        await self._set_timeout(session)
        result = await session.execute(
            statement.order_by(Relationship.updated_at.desc(), Relationship.id).limit(
                query.limit + 1
            )
        )
        rows = tuple(result.scalars().all())
        evidence_by_relationship: dict[UUID, dict[str, set[UUID]]] = defaultdict(
            lambda: {
                "source_document_ids": set(),
                "evidence_claim_ids": set(),
                "provider_result_ids": set(),
            }
        )
        if rows:
            evidence_result = await session.execute(
                select(RelationshipEvidence)
                .where(
                    RelationshipEvidence.relationship_id.in_(
                        tuple(row.id for row in rows[: query.limit])
                    )
                )
                .order_by(RelationshipEvidence.relationship_id, RelationshipEvidence.id)
            )
            for evidence in evidence_result.scalars():
                values = evidence_by_relationship[evidence.relationship_id]
                if evidence.source_document_id is not None:
                    values["source_document_ids"].add(evidence.source_document_id)
                if evidence.evidence_claim_id is not None:
                    values["evidence_claim_ids"].add(evidence.evidence_claim_id)
                if evidence.provider_result_id is not None:
                    values["provider_result_ids"].add(evidence.provider_result_id)
        relationship_urls: dict[UUID, str] = {}
        source_document_ids = tuple(
            {
                source_id
                for values in evidence_by_relationship.values()
                for source_id in values["source_document_ids"]
            }
        )
        if source_document_ids:
            document_result = await session.execute(
                select(SourceDocument.id, SourceDocument.canonical_url).where(
                    SourceDocument.id.in_(source_document_ids)
                )
            )
            relationship_urls = {row[0]: row[1] for row in document_result.all()}
        items = tuple(
            AnalystRelationship(
                **_base(
                    row,
                    CorpusProvenance(
                        source_document_ids=tuple(
                            sorted(
                                evidence_by_relationship[row.id]["source_document_ids"]
                            )
                        ),
                        evidence_claim_ids=tuple(
                            sorted(
                                evidence_by_relationship[row.id]["evidence_claim_ids"]
                            )
                        ),
                        provider_result_ids=tuple(
                            sorted(
                                evidence_by_relationship[row.id]["provider_result_ids"]
                            )
                        ),
                        source_urls=tuple(
                            sorted(
                                relationship_urls[source_id]
                                for source_id in evidence_by_relationship[row.id][
                                    "source_document_ids"
                                ]
                                if source_id in relationship_urls
                            )
                        ),
                    ),
                ),
                source_entity_type=row.source_entity_type,
                source_entity_id=row.source_entity_id,
                relationship_type=row.relationship_type,
                target_entity_type=row.target_entity_type,
                target_entity_id=row.target_entity_id,
                direction=row.direction,
                origin=row.origin,
                confidence=row.confidence,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
                active=row.active,
                review_state=row.review_state,
                supersedes_id=row.supersedes_id,
                origin_rule=row.origin_rule,
                justification=row.justification,
                prompt_version=row.prompt_version,
                model_identifier=row.model_identifier,
                analyst_run_id=row.analyst_run_id,
                evidence_ids=tuple(
                    sorted(
                        evidence_by_relationship[row.id]["source_document_ids"]
                        | evidence_by_relationship[row.id]["evidence_claim_ids"]
                        | evidence_by_relationship[row.id]["provider_result_ids"]
                    )
                ),
            )
            for row in rows
        )
        return self._page(CorpusResource.RELATIONSHIPS, query, rows, items)

    async def contradictions(self, session: AsyncSession, query: CorpusQuery) -> Any:
        rows = await self._rows(
            session,
            CorpusResource.CONTRADICTIONS,
            CorrelationContradictionRecord,
            query,
            search_columns=(CorrelationContradictionRecord.claim_key,),
        )
        filtered = tuple(
            row
            for row in rows
            if query.entity_type is None
            or (
                row.subject_entity_type == query.entity_type.value
                and (
                    query.entity_id is None or row.subject_entity_id == query.entity_id
                )
            )
            if query.review_state is None
            or getattr(row, "review_state", "proposed") == query.review_state.value
        )
        items = tuple(
            AnalystContradiction(
                **_base(
                    row,
                    CorpusProvenance(
                        evidence_claim_ids=_uuid_values(row.evidence_ids),
                    ),
                ),
                subject_entity_type=row.subject_entity_type,
                subject_entity_id=row.subject_entity_id,
                claim_key=row.claim_key,
                observed_values=tuple(row.observed_values or ()),
                evidence_ids=_uuid_values(row.evidence_ids),
                justification=row.justification,
                review_state=getattr(row, "review_state", "proposed"),
                confidence=getattr(row, "confidence", None),
                supersedes_id=getattr(row, "supersedes_id", None),
            )
            for row in filtered
        )
        return self._page(CorpusResource.CONTRADICTIONS, query, rows, items)

    async def query(
        self, session: AsyncSession, resource: CorpusResource, query: CorpusQuery
    ) -> Any:
        handlers = {
            CorpusResource.CVES: self.cves,
            CorpusResource.IOCS: self.iocs,
            CorpusResource.PRODUCTS: self.products,
            CorpusResource.ACTORS: self.actors,
            CorpusResource.MALWARE: self.malware,
            CorpusResource.TOOLS: self.tools,
            CorpusResource.CAMPAIGNS: self.campaigns,
            CorpusResource.TECHNIQUES: self.techniques,
            CorpusResource.URLS: self.urls,
            CorpusResource.EVIDENCE: self.evidence,
            CorpusResource.RELATIONSHIPS: self.relationships,
            CorpusResource.CONTRADICTIONS: self.contradictions,
        }
        return await handlers[resource](session, query)
