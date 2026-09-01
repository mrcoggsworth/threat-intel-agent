"""Tests for interactive CVE modal, dedicated CVE analysis page, and CTI synthesis."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from hermes_cti.api.dependencies import get_enrichment_service
from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.enrichment.cve_analysis import (
    CVERiskLevel,
    CVEVerdict,
    synthesize_cve_analyst_assessment,
)
from hermes_cti.models.contracts import (
    AffectedProduct,
    EnrichmentRunResult,
    EnrichmentStatus,
    EntityReference,
    EntityType,
    Product,
    ProviderRequest,
    ProviderResponse,
)
from hermes_cti.reporting.contracts import ReportVulnerability
from tests.test_phase8 import MemoryPortalService


class EmptyEnrichmentService:
    async def enrich_cve(self, **_: object) -> None:
        return None


class StaticEnrichmentService:
    def __init__(self, result: EnrichmentRunResult) -> None:
        self.result = result

    async def enrich_cve(self, **_: object) -> EnrichmentRunResult:
        return self.result


def test_cve_analyst_assessment_known_exploited() -> None:
    assessment = synthesize_cve_analyst_assessment(
        "CVE-2026-8452",
        kev_data={
            "cve_id": "CVE-2026-8452",
            "found": True,
            "date_added": "2026-08-15",
            "due_date": "2026-09-05",
            "required_action": "Apply vendor mitigation immediately.",
            "notes": "Actively exploited in the wild targeting gateway appliances.",
        },
        nvd_data={
            "cve_id": "CVE-2026-8452",
            "cvss_score": 9.8,
            "cvss_version": "v3.1",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "cwe_ids": ["CWE-787", "CWE-20"],
            "description": "Out-of-bounds write in gateway parser.",
        },
        epss_data={
            "cve_id": "CVE-2026-8452",
            "epss": 0.824,
            "percentile": 0.985,
        },
    )

    assert assessment.cve_id == "CVE-2026-8452"
    assert assessment.verdict == CVEVerdict.CRITICAL_EXPLOITED
    assert assessment.risk_level == CVERiskLevel.CRITICAL
    assert assessment.known_exploited is True
    assert assessment.badge_style == "danger"
    assert "Active In-The-Wild Exploitation" in assessment.badge_label
    # TLM Briefing must be present and strategic
    assert "URGENT OPERATIONAL PRIORITY" in assessment.tlm_briefing
    assert "Engineering leads" in assessment.tlm_briefing
    # Technical analysis must detail flaw mechanics and CWEs
    assert "CWE-787: Out-of-bounds Write" in assessment.technical_analysis
    assert (
        "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" in assessment.technical_analysis
    )


def test_cve_analyst_assessment_high_risk_unexploited() -> None:
    assessment = synthesize_cve_analyst_assessment(
        "CVE-2026-1111",
        nvd_data={
            "cve_id": "CVE-2026-1111",
            "cvss_score": 7.5,
            "cvss_version": "v3.1",
            "cwe_ids": ["CWE-89"],
            "description": "SQL Injection in search API.",
        },
        epss_data={"cve_id": "CVE-2026-1111", "epss": 0.25, "percentile": 0.85},
    )

    assert assessment.verdict == CVEVerdict.ELEVATED_EXPOSURE
    assert assessment.risk_level == CVERiskLevel.HIGH
    assert assessment.known_exploited is False
    assert "High Severity Exposure" in assessment.badge_label
    assert "ELEVATED EXPOSURE" in assessment.tlm_briefing


def test_cve_analyst_assessment_reads_canonical_provider_epss_fields() -> None:
    assessment = synthesize_cve_analyst_assessment(
        "CVE-2026-2222",
        epss_data={
            "cve_id": "CVE-2026-2222",
            "found": True,
            "epss_score": 0.824,
            "epss_percentile": 0.985,
        },
    )

    assert assessment.epss_score == 0.824
    assert assessment.epss_percentile == 0.985


def test_portal_cve_modal_endpoint_standalone() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    app.dependency_overrides[get_enrichment_service] = lambda: EmptyEnrichmentService()

    with TestClient(app) as client:
        response = client.get("/partials/cve-modal?cve_id=CVE-2026-8452")
        assert response.status_code == 200
        html = response.text
        assert "CVE-2026-8452" in html
        assert "data-dialog" in html
        assert "Tech Lead Manager Strategic Briefing" in html
        assert "CTI Analyst Evaluation" in html
        assert "/vulnerabilities/CVE-2026-8452" in html
        assert "N/A%" not in html
        assert "EPSS Probability" in html


def test_portal_cve_modal_renders_canonical_provider_epss_score() -> None:
    portal_service = MemoryPortalService()
    entity = EntityReference(
        entity_type=EntityType.VULNERABILITY,
        entity_id=uuid4(),
    )
    request = ProviderRequest(
        entity=entity,
        query_key="CVE-2026-8452",
        query_kind="cve",
        requested_at=datetime(2026, 8, 31, tzinfo=UTC),
    )
    result = EnrichmentRunResult(
        entity=entity,
        status=EnrichmentStatus.SUCCESS,
        provider_results=(
            ProviderResponse(
                provider="epss",
                request=request,
                retrieved_at=datetime(2026, 8, 31, tzinfo=UTC),
                status=EnrichmentStatus.SUCCESS,
                normalized_result={
                    "cve_id": "CVE-2026-8452",
                    "found": True,
                    "epss_score": 0.824,
                    "epss_percentile": 0.985,
                },
            ),
        ),
    )
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    app.dependency_overrides[get_enrichment_service] = lambda: StaticEnrichmentService(
        result
    )

    with TestClient(app) as client:
        response = client.get("/partials/cve-modal?cve_id=CVE-2026-8452")

    assert response.status_code == 200
    assert "82.40%" in response.text
    assert "N/A%" not in response.text


def test_portal_cve_modal_endpoint_in_report_context() -> None:
    portal_service = MemoryPortalService()
    rep_vuln = ReportVulnerability(
        vulnerability_id=uuid4(),
        cve_id="CVE-2026-9999",
        summary="Remote code execution in Acme Core.",
        cvss_score=9.8,
        cvss_version="v3.1",
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        epss_score=0.91,
        epss_percentile=0.99,
        cwe_ids=("CWE-502",),
        known_exploited=True,
        affected_products=(
            AffectedProduct(
                affected_product_id=uuid4(),
                vulnerability_id=uuid4(),
                product=Product(
                    product_id=uuid4(),
                    vendor="Acme",
                    product="Core",
                    ecosystem="enterprise",
                ),
                version_range="< 2.4.1",
                affected_status="affected",
                confidence=0.9,
            ),
        ),
        evidence_ids=(portal_service.bundle.evidence[0].evidence_id,),
    )
    bundle = portal_service.bundle.model_copy(update={"vulnerabilities": (rep_vuln,)})
    portal_service.bundle = bundle
    portal_service.version.structured_content = json.loads(bundle.stable_json())

    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/cve-modal?cve_id=CVE-2026-9999"
        )
        assert response.status_code == 200
        html = response.text
        assert "CVE-2026-9999" in html
        assert portal_service.report.headline in html
        assert "Acme Core" in html
        assert "CWE-502: Deserialization of Untrusted Data" in html
        assert "/vulnerabilities/CVE-2026-9999" in html


def test_dedicated_vulnerability_page() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    app.dependency_overrides[get_enrichment_service] = lambda: EmptyEnrichmentService()

    with TestClient(app) as client:
        response = client.get("/vulnerabilities/CVE-2026-8452")
        assert response.status_code == 200
        html = response.text
        assert "CVE-2026-8452" in html
        assert "Tech Lead Manager (TLM) Strategic Briefing" in html
        assert "Deep Technical &amp; Root-Cause Analysis" in html
        assert "Authoritative Telemetry &amp; Scoring" in html
        assert "National Vulnerability Database" in html
        assert "CISA KEV Catalog" in html
        assert "FIRST EPSS Model" in html
        assert "N/A%" not in html
        assert "N/Ath %" not in html
        assert "Exploit Probability:" in html
        assert "Global Percentile:" in html
        assert html.count("N/A") >= 2


def test_cve_links_do_not_expose_raw_backend_api() -> None:
    portal_service = MemoryPortalService()
    rep_vuln = ReportVulnerability(
        vulnerability_id=uuid4(),
        cve_id="CVE-2026-7777",
        summary="Buffer overflow vulnerability.",
        cvss_score=8.5,
        evidence_ids=(portal_service.bundle.evidence[0].evidence_id,),
    )
    bundle = portal_service.bundle.model_copy(update={"vulnerabilities": (rep_vuln,)})
    portal_service.bundle = bundle
    portal_service.version.structured_content = json.loads(bundle.stable_json())

    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )

    with TestClient(app) as client:
        # Check /reports list
        res_list = client.get("/reports")
        assert res_list.status_code == 200
        assert "/api/v1/public/vulnerabilities" not in res_list.text
        assert "data-cve-id=" in res_list.text

        # Check /reports/{slug} detail
        res_detail = client.get(f"/reports/{portal_service.report.slug}")
        assert res_detail.status_code == 200
        assert "/api/v1/public/vulnerabilities" not in res_detail.text
        assert 'data-cve-id="CVE-2026-7777"' in res_detail.text
        assert (
            f"/partials/reports/{portal_service.report.slug}/cve-modal?cve_id=CVE-2026-7777"
            in res_detail.text
        )
