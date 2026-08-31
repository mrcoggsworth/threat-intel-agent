"""Public portal projection service and private draft queries."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from hermes_cti.db.models import Report
from hermes_cti.db.session import Database
from hermes_cti.models.contracts import EntityType, ReportState, Severity
from hermes_cti.portal.contracts import (
    CVEQuery,
    CVESort,
    EvidenceAnalystSummary,
    PortalQuery,
    PrivateDraftPage,
    PublicAdminDraft,
    PublicCVEPage,
    PublicCVESummary,
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


_DOMAIN_SOURCE_MAP: dict[str, str] = {
    "cisa.gov": "CISA",
    "microsoft.com": "Microsoft Threat Intelligence",
    "paloaltonetworks.com": "Unit 42",
    "thedfirreport.com": "The DFIR Report",
    "bleepingcomputer.com": "BleepingComputer",
    "thehackernews.com": "The Hacker News",
    "krebsonsecurity.com": "Krebs on Security",
    "sentinelone.com": "SentinelLabs",
    "redcanary.com": "Red Canary",
    "rapid7.com": "Rapid7",
    "recordedfuture.com": "Recorded Future",
    "securityweek.com": "SecurityWeek",
    "isc.sans.edu": "SANS ISC",
    "ncsc.gov.uk": "UK NCSC",
    "zerodayinitiative.com": "Trend Micro ZDI",
    "socprime.com": "SOC Prime",
    "github.com/sigmahq": "SigmaHQ",
    "abuse.ch/urlhaus": "URLhaus",
    "abuse.ch/threatfox": "ThreatFox",
    "feodotracker": "Feodo Tracker",
    "qualys.com": "Qualys Security",
    "huntress.com": "Huntress",
    "darkreading.com": "Dark Reading",
    "nvd.nist.gov": "NIST NVD",
}


def _source_names(
    bundle: ReportBundle, headline: str = "", slug: str = ""
) -> tuple[str, ...]:
    names: list[str] = []

    # 1. Direct source references
    for ref in bundle.source_references:
        name = ref.name.strip()
        if name:
            if "dfir" in name.casefold():
                name = "The DFIR Report"
            elif "cisa" in name.casefold():
                if "known" in name.casefold() or "kev" in name.casefold():
                    name = "CISA KEV"
                else:
                    name = "CISA"
            elif "microsoft" in name.casefold():
                name = "Microsoft Threat Intelligence"
            if name.casefold() not in [n.casefold() for n in names]:
                names.append(name)

    # 2. Evidence items
    for item in bundle.evidence:
        if item.source_reference and item.source_reference.name:
            n = item.source_reference.name.strip()
            if n and n.casefold() not in [x.casefold() for x in names]:
                names.append(n)
        if item.source_url:
            url_str = str(item.source_url).casefold()
            for dom, clean_name in _DOMAIN_SOURCE_MAP.items():
                if dom in url_str and clean_name.casefold() not in [
                    x.casefold() for x in names
                ]:
                    names.append(clean_name)

    # 3. Check combined text
    remed_refs = " ".join(
        str(r)
        for r in (
            getattr(bundle.remediation, "references", ()) if bundle.remediation else ()
        )
    )
    combined_text = (
        f"{headline} {slug} {bundle.executive_summary} {remed_refs}"
    ).casefold()

    for dom, clean_name in _DOMAIN_SOURCE_MAP.items():
        if dom in combined_text and clean_name.casefold() not in [
            x.casefold() for x in names
        ]:
            names.append(clean_name)

    if not names:
        if "cisa" in combined_text:
            names.append("CISA")
        elif "dfir" in combined_text:
            names.append("The DFIR Report")
        elif "microsoft" in combined_text:
            names.append("Microsoft Threat Intelligence")
        elif "sentinellabs" in combined_text or "sentinelone" in combined_text:
            names.append("SentinelLabs")
        elif "unit 42" in combined_text or "unit42" in combined_text:
            names.append("Unit 42")
        elif "bleepingcomputer" in combined_text:
            names.append("BleepingComputer")
        elif "krebsonsecurity" in combined_text or "krebs" in combined_text:
            names.append("Krebs on Security")
        elif "hacker news" in combined_text:
            names.append("The Hacker News")
        elif "zdi" in combined_text or "zero day initiative" in combined_text:
            names.append("Trend Micro ZDI")
        elif "rapid7" in combined_text:
            names.append("Rapid7")
        else:
            names.append("Threat Advisory")

    return tuple(names)


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
        source_names = _source_names(content, report.headline, report.slug)
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
            source_names=source_names,
            primary_source=source_names[0] if source_names else None,
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

    async def list_cves(self, query: CVEQuery) -> PublicCVEPage:
        cve_map: dict[str, dict[str, Any]] = {}

        if self.database is not None:
            async with self.database.session() as session:
                page_idx = 1
                while True:
                    rows = await self.repository.list_reports(
                        session, PortalQuery(page=page_idx, page_size=100)
                    )
                    for row in rows.items:
                        bundle = self._bundle(row)
                        slug = row.report.slug
                        row_sources = _source_names(bundle, row.report.headline, slug)
                        for v in bundle.vulnerabilities:
                            cve_clean = v.cve_id.strip().upper()
                            entry = cve_map.setdefault(
                                cve_clean,
                                {
                                    "cve_id": cve_clean,
                                    "summary": v.summary
                                    or f"Vulnerability record for {cve_clean}",
                                    "cvss_score": v.cvss_score,
                                    "cvss_version": v.cvss_version,
                                    "cvss_vector": v.cvss_vector,
                                    "epss_score": v.epss_score,
                                    "epss_percentile": v.epss_percentile,
                                    "known_exploited": bool(v.known_exploited)
                                    if v.known_exploited is not None
                                    else False,
                                    "cwe_ids": set(v.cwe_ids),
                                    "products": set(),
                                    "report_slugs": set(),
                                    "source_names": set(),
                                    "published_at": None,
                                    "last_updated_at": None,
                                },
                            )
                            entry["report_slugs"].add(slug)
                            for s in row_sources:
                                entry["source_names"].add(s)
                            if v.known_exploited or v.kev_date_added:
                                entry["source_names"].add("CISA KEV")
                            if v.kev_date_added:
                                entry["published_at"] = str(v.kev_date_added)
                            elif (
                                row.report.first_published_at
                                and not entry["published_at"]
                            ):
                                entry["published_at"] = str(
                                    row.report.first_published_at
                                ).split("T")[0]
                            if row.report.last_updated_at:
                                entry["last_updated_at"] = str(
                                    row.report.last_updated_at
                                ).split("T")[0]
                            if v.cvss_score is not None and (
                                entry["cvss_score"] is None
                                or v.cvss_score > entry["cvss_score"]
                            ):
                                entry["cvss_score"] = v.cvss_score
                                entry["cvss_version"] = v.cvss_version
                                entry["cvss_vector"] = v.cvss_vector
                            if v.epss_score is not None:
                                entry["epss_score"] = v.epss_score
                                entry["epss_percentile"] = v.epss_percentile
                            if v.known_exploited:
                                entry["known_exploited"] = True
                            if v.summary and len(v.summary) > len(entry["summary"]):
                                entry["summary"] = v.summary
                            for cwe in v.cwe_ids:
                                entry["cwe_ids"].add(cwe)
                            for ap in v.affected_products:
                                p_str = f"{ap.product.vendor} {ap.product.product}"
                                if ap.version_range:
                                    p_str += f" ({ap.version_range})"
                                entry["products"].add(p_str)
                    if (
                        not rows.items
                        or len(rows.items) < 100
                        or page_idx * 100 >= rows.total
                    ):
                        break
                    page_idx += 1

        summaries: list[PublicCVESummary] = []
        for cve_clean, data in cve_map.items():
            score = data["cvss_score"]
            is_kev = bool(data.get("known_exploited", False))
            epss = data["epss_score"]
            cve_sources = tuple(sorted(data.get("source_names", ())))

            if (
                is_kev
                or (score is not None and score >= 9.0)
                or (epss is not None and epss >= 0.50)
            ):
                sev = Severity.CRITICAL
                b_label = (
                    "Active In-The-Wild Exploitation" if is_kev else "Critical Severity"
                )
                b_style = "danger"
            elif (score is not None and score >= 7.0) or (
                epss is not None and epss >= 0.20
            ):
                sev = Severity.HIGH
                b_label = "High Severity Exposure"
                b_style = "warning"
            elif score is not None and score >= 4.0:
                sev = Severity.MEDIUM
                b_label = "Moderate Severity"
                b_style = "warning"
            elif score is not None:
                sev = Severity.LOW
                b_label = "Low Severity"
                b_style = "success"
            else:
                sev = Severity.INFO
                b_label = "Telemetry Pending"
                b_style = "slate"

            summaries.append(
                PublicCVESummary(
                    cve_id=cve_clean,
                    summary=data["summary"],
                    cvss_score=score,
                    cvss_version=data["cvss_version"],
                    cvss_vector=data["cvss_vector"],
                    epss_score=epss,
                    epss_percentile=data["epss_percentile"],
                    known_exploited=is_kev,
                    severity=sev,
                    badge_label=b_label,
                    badge_style=b_style,
                    cwe_ids=tuple(sorted(data["cwe_ids"])),
                    affected_products=tuple(sorted(data["products"])),
                    report_count=len(data["report_slugs"]),
                    report_slugs=tuple(sorted(data["report_slugs"])),
                    source_names=cve_sources,
                    primary_source=cve_sources[0] if cve_sources else None,
                    published_at=data.get("published_at"),
                    last_updated_at=data.get("last_updated_at"),
                    canonical_url=f"/vulnerabilities/{cve_clean}",
                )
            )

        filtered = summaries
        if query.search:
            s = query.search.casefold()
            filtered = [
                c
                for c in filtered
                if s in c.cve_id.casefold()
                or s in c.summary.casefold()
                or any(s in p.casefold() for p in c.affected_products)
                or any(s in cwe.casefold() for cwe in c.cwe_ids)
            ]
        if query.severities:
            filtered = [c for c in filtered if c.severity in query.severities]
        if query.known_exploited_only:
            filtered = [c for c in filtered if c.known_exploited]
        if query.min_cvss is not None:
            filtered = [
                c
                for c in filtered
                if c.cvss_score is not None and c.cvss_score >= query.min_cvss
            ]
        if query.min_epss is not None:
            filtered = [
                c
                for c in filtered
                if c.epss_score is not None and c.epss_score >= query.min_epss
            ]

        if query.sort == CVESort.CVSS:
            filtered.sort(
                key=lambda x: (
                    x.cvss_score is None,
                    -(x.cvss_score or 0),
                    x.cve_id,
                )
            )
        elif query.sort == CVESort.EPSS:
            filtered.sort(
                key=lambda x: (
                    x.epss_score is None,
                    -(x.epss_score or 0),
                    x.cve_id,
                )
            )
        elif query.sort == CVESort.REPORTS:
            filtered.sort(key=lambda x: (-x.report_count, x.cve_id))
        elif query.sort == CVESort.NEWEST:
            filtered.sort(key=lambda x: x.cve_id, reverse=True)
        else:  # PRIORITY
            filtered.sort(
                key=lambda x: (
                    not x.known_exploited,
                    -(x.cvss_score or 0),
                    -(x.epss_score or 0),
                    x.cve_id,
                )
            )

        total = len(filtered)
        start_idx = (query.page - 1) * query.page_size
        end_idx = start_idx + query.page_size
        page_items = tuple(filtered[start_idx:end_idx])
        total_pages = math.ceil(total / query.page_size) if total else 0

        return PublicCVEPage(
            items=page_items,
            page=query.page,
            page_size=query.page_size,
            total=total,
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
