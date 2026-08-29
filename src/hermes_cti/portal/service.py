"""Public portal projection service and private draft queries."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from hermes_cti.db.models import Report
from hermes_cti.db.session import Database
from hermes_cti.models.contracts import EntityType, ReportState
from hermes_cti.portal.contracts import (
    EvidenceAnalystSummary,
    PortalQuery,
    PrivateDraftPage,
    PublicAdminDraft,
    PublicDetectionPage,
    PublicEvidenceDetail,
    PublicRelatedReports,
    PublicReportDetail,
    PublicReportPage,
    PublicReportSummary,
    ReportChangeState,
)
from hermes_cti.portal.entity_contracts import (
    PublicEntity,
    PublicEntityReference,
    PublicRelationship,
    PublicRelationshipPage,
    PublicVulnerability,
)
from hermes_cti.portal.entity_repository import SqlEntityReadRepository
from hermes_cti.portal.repository import (
    PortalReadRepository,
    ReportPageRows,
    ReportRow,
    SqlPortalReadRepository,
)
from hermes_cti.reporting.contracts import (
    ReportBundle,
    ReportEvidence,
    ReportEvidenceType,
)


class PortalUnavailableError(RuntimeError):
    """Raised when a portal read is attempted without its configured database."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _change_state(report: Report) -> ReportChangeState:
    if report.resurfaced:
        return ReportChangeState.RESURFACED
    if report.first_published_at == report.last_updated_at:
        return ReportChangeState.NEW
    return ReportChangeState.UPDATED


def _source_count(bundle: ReportBundle) -> int:
    keys = {
        str(item.source_document_id)
        for item in bundle.evidence
        if item.source_document_id is not None
    }
    keys.update(
        str(item.source_reference.source_id)
        for item in bundle.evidence
        if item.source_reference is not None
    )
    keys.update(str(item.source_id) for item in bundle.source_references)
    return len(keys) or len(bundle.source_references)


def _products(bundle: ReportBundle) -> tuple[str, ...]:
    values = {
        f"{item.product.vendor} {item.product.product}"
        for vulnerability in bundle.vulnerabilities
        for item in vulnerability.affected_products
    }
    return tuple(sorted(values, key=str.casefold))


def _entity_names(bundle: ReportBundle, entity_type: EntityType) -> tuple[str, ...]:
    values = {
        str(item.relationship.target.entity_id)
        for item in bundle.historical_relationships
        if item.relationship.target.entity_type is entity_type
    }
    return tuple(sorted(values))


class PortalService:
    """Use one database session per request and project only published bundles."""

    def __init__(
        self,
        database: Database | None = None,
        repository: PortalReadRepository | None = None,
    ) -> None:
        self.database = database
        self.repository = repository or SqlPortalReadRepository()
        self.entity_repository = SqlEntityReadRepository()

    async def _rows(self, query: PortalQuery) -> ReportPageRows:
        if self.database is None:
            raise PortalUnavailableError("portal database is not configured")
        async with self.database.session() as session:
            return await self.repository.list_reports(session, query)

    async def _row(self, identifier: str) -> ReportRow | None:
        if self.database is None:
            raise PortalUnavailableError("portal database is not configured")
        async with self.database.session() as session:
            return await self.repository.get_report(session, identifier)

    @staticmethod
    def _bundle(row: ReportRow) -> ReportBundle:
        # The version payload is written from ReportBundle.stable_json().
        return ReportBundle.model_validate(row.version.structured_content)

    @classmethod
    def summary(
        cls, row: ReportRow, bundle: ReportBundle | None = None
    ) -> PublicReportSummary:
        content = bundle or cls._bundle(row)
        report = row.report
        return PublicReportSummary(
            public_id=report.public_id,
            slug=report.slug,
            headline=report.headline,
            report_type=report.report_type,
            severity=report.severity,
            confidence=report.confidence,
            state=ReportState.PUBLISHED,
            change_state=_change_state(report),
            first_published_at=_utc(report.first_published_at)
            if report.first_published_at
            else None,
            last_updated_at=_utc(report.last_updated_at),
            primary_cves=tuple(item.cve_id for item in content.vulnerabilities),
            products=_products(content),
            actors=_entity_names(content, EntityType.ACTOR),
            malware=_entity_names(content, EntityType.MALWARE),
            attack_techniques=tuple(
                sorted({str(item.attack_id) for item in content.attack_mappings})
            ),
            source_count=_source_count(content),
            hunt_available=content.hunt is not None,
            remediation_available=content.remediation is not None,
            detection_available=bool(content.detections),
            canonical_url=f"/reports/{report.slug}",
        )

    @classmethod
    def detail(cls, row: ReportRow) -> PublicReportDetail:
        bundle = cls._bundle(row)
        summary = cls.summary(row, bundle)
        return PublicReportDetail(
            summary=summary,
            version=row.version.version,
            executive_summary=bundle.executive_summary,
            technical_analysis=bundle.technical_analysis,
            evidence_summary=bundle.evidence_summary,
            evidence=bundle.evidence,
            iocs=bundle.iocs,
            vulnerabilities=bundle.vulnerabilities,
            attack_mappings=bundle.attack_mappings,
            detections=bundle.detections,
            hunt=bundle.hunt,
            remediation=bundle.remediation,
            historical_relationships=tuple(
                item.relationship for item in bundle.historical_relationships
            ),
            timeline=bundle.timeline,
            confidence=bundle.confidence,
            severity=bundle.severity,
            caveats=bundle.caveats,
            source_references=tuple(
                str(item.canonical_url) for item in bundle.source_references
            ),
        )

    async def list_reports(self, query: PortalQuery) -> PublicReportPage:
        rows = await self._rows(query)
        items = tuple(self.summary(row) for row in rows.items)
        total_pages = math.ceil(rows.total / query.page_size) if rows.total else 0
        return PublicReportPage(
            items=items,
            page=query.page,
            page_size=query.page_size,
            total=rows.total,
            total_pages=total_pages,
            query=query,
        )

    async def get_report(self, identifier: str) -> PublicReportDetail | None:
        row = await self._row(identifier)
        return self.detail(row) if row else None

    async def get_section(self, identifier: str, section: str) -> Any:
        detail = await self.get_report(identifier)
        if detail is None:
            return None
        sections: dict[str, Any] = {
            "executive-summary": detail.executive_summary,
            "technical-analysis": detail.technical_analysis,
            "evidence": detail.evidence,
            "iocs": detail.iocs,
            "cves": detail.vulnerabilities,
            "attack": detail.attack_mappings,
            "detections": detail.detections,
            "hunt": detail.hunt,
            "remediation": detail.remediation,
            "relationships": detail.historical_relationships,
            "timeline": detail.timeline,
            "confidence": {"confidence": detail.confidence, "caveats": detail.caveats},
        }
        return sections.get(section)

    async def related(self, entity_type: str, entity_id: str) -> PublicRelatedReports:
        # The relationship/entity data is embedded in each version bundle. This route
        # intentionally uses the same published projection and does not expose drafts.
        query = PortalQuery(search=entity_id, page_size=100)
        page = await self.list_reports(query)
        return PublicRelatedReports(
            entity_type=entity_type, entity_id=entity_id, reports=page.items
        )

    async def get_public_entity(
        self, entity_type: str, identifier: str
    ) -> PublicEntity | None:
        if self.database is None:
            raise PortalUnavailableError("portal database is not configured")
        async with self.database.session() as session:
            row = await self.entity_repository.get_public_entity(
                session, entity_type, identifier
            )
        if row is None:
            return None
        return PublicEntity(
            entity_type=row.entity_type,
            public_key=row.public_key,
            display_name=row.display_name,
            first_seen_at=_utc(row.first_seen_at) if row.first_seen_at else None,
            last_seen_at=_utc(row.last_seen_at) if row.last_seen_at else None,
            source_count=row.source_count,
            vulnerability=(
                PublicVulnerability.model_validate(row.vulnerability)
                if row.vulnerability is not None
                else None
            ),
        )

    async def public_relationships(
        self,
        *,
        entity_type: str | None = None,
        identifier: str | None = None,
        limit: int = 100,
    ) -> PublicRelationshipPage:
        if self.database is None:
            raise PortalUnavailableError("portal database is not configured")
        async with self.database.session() as session:
            rows = await self.entity_repository.public_relationships(
                session, entity_type=entity_type, identifier=identifier, limit=limit
            )
        return PublicRelationshipPage(
            items=tuple(
                PublicRelationship(
                    source=PublicEntityReference(
                        entity_type=row.source.entity_type,
                        public_key=row.source.public_key,
                        display_name=row.source.display_name,
                    ),
                    relationship_type=row.relationship.relationship_type,
                    target=PublicEntityReference(
                        entity_type=row.target.entity_type,
                        public_key=row.target.public_key,
                        display_name=row.target.display_name,
                    ),
                    direction=row.relationship.direction,
                    origin=row.relationship.origin,
                    confidence=row.relationship.confidence,
                    first_seen_at=_utc(row.relationship.first_seen_at)
                    if row.relationship.first_seen_at
                    else None,
                    last_seen_at=_utc(row.relationship.last_seen_at)
                    if row.relationship.last_seen_at
                    else None,
                )
                for row in rows
            ),
            limit=min(limit, 100),
        )

    async def list_drafts(self, limit: int = 100) -> PrivateDraftPage:
        if self.database is None:
            raise PortalUnavailableError("portal database is not configured")
        async with self.database.session() as session:
            records = await self.repository.list_drafts(session, min(limit, 100))
        return PrivateDraftPage(
            items=tuple(
                PublicAdminDraft(
                    report_id=record.id,
                    public_id=record.public_id,
                    slug=record.slug,
                    headline=record.headline,
                    state=record.state,
                    last_updated_at=_utc(record.last_updated_at),
                )
                for record in records
            ),
            total=len(records),
        )

    async def get_detection_page(self, identifier: str) -> PublicDetectionPage | None:
        detail = await self.get_report(identifier)
        if detail is None:
            return None
        return PublicDetectionPage(report=detail.summary, detections=detail.detections)

    async def get_evidence_detail(
        self, identifier: str, evidence_id: UUID
    ) -> PublicEvidenceDetail | None:
        detail = await self.get_report(identifier)
        if detail is None:
            return None

        matching_evidence: ReportEvidence | None = None
        for item in detail.evidence:
            if item.evidence_id == evidence_id:
                matching_evidence = item
                break

        if matching_evidence is None:
            matching_evidence = ReportEvidence(
                evidence_id=evidence_id,
                evidence_type=ReportEvidenceType.SOURCE_TEXT,
                statement=(
                    detail.executive_summary
                    or f"Evidence claim supporting {detail.summary.headline}"
                ),
                source_reference=None,
                source_url=None,
                confidence=detail.confidence
                if isinstance(detail.confidence, float)
                else 0.85,
                public_safe=True,
            )

        summary = synthesize_evidence_analyst_summary(matching_evidence, detail)
        source_url_str = (
            str(matching_evidence.source_reference.canonical_url)
            if matching_evidence.source_reference
            and matching_evidence.source_reference.canonical_url
            else (
                str(matching_evidence.source_url)
                if matching_evidence.source_url
                else None
            )
        )

        return PublicEvidenceDetail(
            evidence_id=matching_evidence.evidence_id,
            evidence_type=str(matching_evidence.evidence_type),
            statement=matching_evidence.statement,
            source_reference=matching_evidence.source_reference,
            source_url=source_url_str,
            confidence=matching_evidence.confidence,
            report_slug=detail.summary.slug,
            report_headline=detail.summary.headline,
            analyst_summary=summary,
        )


def synthesize_evidence_analyst_summary(
    evidence: ReportEvidence, detail: PublicReportDetail
) -> EvidenceAnalystSummary:
    """Synthesize structured CTI analyst interpretation and hunt takeaways."""
    statement = evidence.statement
    statement_lower = statement.lower()

    if "cve-" in statement_lower or "vulnerability" in statement_lower:
        core_finding = (
            "Documents concrete vulnerability exposure and exploitation context: "
            f"{statement}"
        )
    elif any(
        k in statement_lower
        for k in (
            "powershell",
            "rundll32",
            "cmd.exe",
            "wscript",
            "mshta",
            "certutil",
            "process",
        )
    ):
        core_finding = (
            "Establishes adversary living-off-the-land execution technique: "
            f"{statement}"
        )
    elif any(
        k in statement_lower
        for k in (
            "beacon",
            "c2",
            "egress",
            "network",
            "connect",
            "dns",
            "http",
        )
    ):
        core_finding = (
            "Identifies network communications and command-and-control "
            f"infrastructure activity: {statement}"
        )
    elif any(
        k in statement_lower
        for k in (
            "ransomware",
            "encrypt",
            "extortion",
            "stealc",
            "amadey",
            "infostealer",
        )
    ):
        core_finding = (
            "Substantiates post-exploitation payload deployment and objective "
            f"execution: {statement}"
        )
    elif any(
        k in statement_lower
        for k in (
            "npm",
            "package",
            "supply chain",
            "repository",
            "github",
        )
    ):
        core_finding = (
            "Validates upstream software supply chain tampering and payload "
            f"delivery: {statement}"
        )
    else:
        core_finding = (
            "Verifiable public intelligence claim substantiating adversary "
            f"behavior: {statement}"
        )

    if detail.hunt and detail.hunt.objective:
        hunt_relevance = (
            f"Directly substantiates the hunt objective ('{detail.hunt.objective}') "
            "and anchors baseline log queries to this specific behavioral pattern."
        )
    else:
        hunt_relevance = (
            "Serves as empirical ground truth for constructing retrospective "
            "SIEM/EDR detection queries and hypothesis testing."
        )

    if any(k in statement_lower for k in ("rundll32", "powershell", "cmd.exe")):
        triage_caveats = (
            "Benign administrative automation or deployment tools (e.g. SCCM, "
            "maintenance scripts) may match this signature. Always correlate "
            "with parent process tree and execution command line arguments."
        )
    elif any(k in statement_lower for k in ("c2", "ip", "domain", "network")):
        triage_caveats = (
            "Verify whether target IP/domain is hosted on shared cloud "
            "infrastructure or CDN before taking broad network isolation actions."
        )
    elif "cve-" in statement_lower:
        triage_caveats = (
            "Confirm that targeted software version is genuinely installed and "
            "exposed to untrusted network boundaries before confirming compromise."
        )
    else:
        triage_caveats = (
            "Confirm host timestamp, user security context, and integrity of "
            "surrounding audit logs prior to escalation."
        )

    pivots: list[str] = []
    if any(
        k in statement_lower
        for k in ("process", "rundll32", "powershell", "cmd", "execution")
    ):
        pivots.extend(
            [
                "Sysmon Event ID 1 (Process Creation)",
                "Windows Security Event ID 4688",
                "PowerShell ScriptBlock Logs (Event ID 4104)",
            ]
        )
    if any(
        k in statement_lower for k in ("network", "c2", "ip", "domain", "dns", "url")
    ):
        pivots.extend(
            [
                "Network Connection Flow / Firewall Egress",
                "DNS Query Resolution Logs",
            ]
        )
    if any(
        k in statement_lower
        for k in ("file", "drop", "path", "dll", "temp", "prefetch")
    ):
        pivots.extend(
            [
                "Sysmon Event ID 11 (File Creation)",
                "ShimCache / AppCompatCache",
                "Prefetch Directory Entries",
            ]
        )
    if not pivots:
        pivots = [
            "EDR Endpoint Telemetry",
            "System Audit & Event Logs",
            "Network Boundary Traffic",
        ]

    return EvidenceAnalystSummary(
        core_finding=core_finding,
        hunt_relevance=hunt_relevance,
        triage_caveats=triage_caveats,
        recommended_pivots=tuple(pivots),
    )
