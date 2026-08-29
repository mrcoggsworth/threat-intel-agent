"""Tests for interactive IOC enrichment modal and indicator enrichment endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.enrichment.ioc_analysis import (
    IOCRiskLevel,
    IOCVerdict,
    synthesize_ioc_analyst_assessment,
)
from hermes_cti.enrichment.providers import (
    AbuseIPDBProvider,
    OTXProvider,
    ProviderRuntimeConfig,
    VirusTotalProvider,
)
from hermes_cti.enrichment.service import EnrichmentService
from hermes_cti.ingestion.http_client import FetchResult
from hermes_cti.models.contracts import EnrichmentStatus
from tests.test_phase8 import MemoryPortalService


def _mock_fetch(url: str = "https://fixture") -> FetchResult:
    return FetchResult(
        url=url,
        status_code=200,
        body=b"{}",
        headers=(("content-type", "application/json"),),
        retry_count=0,
    )


class FakeVTProvider(VirusTotalProvider):
    def __init__(self) -> None:
        super().__init__(
            "https://fixture/vt",
            config=ProviderRuntimeConfig(),
            enabled=True,
            api_key="secret-vt",
        )

    async def _retrieve(self, request):
        return {
            "indicator": request.query_key,
            "reputation": 42,
            "last_analysis_stats": {
                "malicious": 12,
                "suspicious": 3,
                "harmless": 40,
                "undetected": 15,
            },
            "tags": ["trojan", "stealer"],
            "popular_threat_classification": "Trojan.Agent",
            "graph_url": f"https://www.virustotal.com/gui/{request.query_kind}/{request.query_key}",
            "hunting_available": True,
        }, _mock_fetch()


class FakeAbuseIPDBProvider(AbuseIPDBProvider):
    def __init__(self) -> None:
        super().__init__(
            "https://fixture/abuse",
            config=ProviderRuntimeConfig(),
            enabled=True,
            api_key="secret-abuse",
        )

    async def _retrieve(self, request):
        return {
            "indicator": request.query_key,
            "abuse_confidence_score": 85,
            "country_code": "US",
            "usage_type": "Data Center/Web Hosting/Transit",
            "total_reports": 24,
            "last_reported_at": "2026-08-20T10:00:00Z",
        }, _mock_fetch()


class FakeOTXProvider(OTXProvider):
    def __init__(self) -> None:
        super().__init__(
            "https://fixture/otx",
            config=ProviderRuntimeConfig(),
            enabled=True,
            api_key="secret-otx",
        )

    async def _retrieve(self, request):
        return {
            "indicator": request.query_key,
            "pulse_count": 5,
            "pulse_names": ["Threat Campaign Alpha", "Observed C2 Cluster"],
            "sections": ["general", "analysis"],
        }, _mock_fetch()


def test_synthesize_ioc_analyst_assessment_malicious() -> None:
    vt = {
        "last_analysis_stats": {"malicious": 12, "suspicious": 2, "harmless": 10},
        "tags": ["trojan", "stealer"],
        "popular_threat_classification": "Trojan.Agent",
    }
    abuse = {
        "abuse_confidence_score": 85,
        "total_reports": 24,
        "country_code": "US",
        "usage_type": "Hosting",
    }
    otx = {
        "pulse_count": 5,
        "pulse_names": ["Threat Campaign Alpha", "C2 Infrastructure"],
    }

    assessment = synthesize_ioc_analyst_assessment(
        ioc_type="ipv4",
        ioc_value="198.51.100.22",
        report_headline="DarkGate Campaign Advisory",
        vt_data=vt,
        abuse_data=abuse,
        otx_data=otx,
    )

    assert assessment.verdict == IOCVerdict.MALICIOUS
    assert assessment.risk_level == IOCRiskLevel.CRITICAL
    assert assessment.confidence == "High"
    assert assessment.badge_style == "danger"
    assert "MALICIOUS" in assessment.summary
    assert any("Trojan.Agent" in obs for obs in assessment.observations)
    assert any("12 vendors" in obs for obs in assessment.observations)
    assert any("DarkGate Campaign Advisory" in obs for obs in assessment.observations)
    assert any("Containment:" in rec for rec in assessment.recommendations)
    assert any("Telemetry Hunt:" in rec for rec in assessment.recommendations)


def test_synthesize_ioc_analyst_assessment_suspicious() -> None:
    vt = {
        "last_analysis_stats": {"malicious": 1, "suspicious": 1, "harmless": 20},
        "tags": ["suspicious"],
    }
    assessment = synthesize_ioc_analyst_assessment(
        ioc_type="domain",
        ioc_value="suspicious-domain.test",
        vt_data=vt,
    )

    assert assessment.verdict == IOCVerdict.SUSPICIOUS
    assert assessment.risk_level == IOCRiskLevel.MEDIUM
    assert assessment.badge_style == "warning"
    assert "SUSPICIOUS" in assessment.summary
    assert any("Watchlist:" in rec for rec in assessment.recommendations)


def test_synthesize_ioc_analyst_assessment_benign() -> None:
    vt = {
        "last_analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 65},
        "tags": [],
    }
    abuse = {
        "abuse_confidence_score": 0,
        "total_reports": 0,
        "country_code": "US",
    }
    otx = {"pulse_count": 0, "pulse_names": []}

    assessment = synthesize_ioc_analyst_assessment(
        ioc_type="ipv4",
        ioc_value="8.8.8.8",
        vt_data=vt,
        abuse_data=abuse,
        otx_data=otx,
    )

    assert assessment.verdict == IOCVerdict.BENIGN
    assert assessment.risk_level == IOCRiskLevel.LOW
    assert assessment.badge_style == "success"
    assert "Clean" in assessment.badge_label
    assert any("Standard Logging:" in rec for rec in assessment.recommendations)


def test_synthesize_ioc_analyst_assessment_inconclusive() -> None:
    assessment = synthesize_ioc_analyst_assessment(
        ioc_type="sha256",
        ioc_value="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )

    assert assessment.verdict == IOCVerdict.INCONCLUSIVE
    assert assessment.risk_level == IOCRiskLevel.UNKNOWN
    assert assessment.badge_style == "neutral"
    assert any("Manual Pivot:" in rec for rec in assessment.recommendations)


@pytest.mark.asyncio
async def test_enrich_indicator_service() -> None:
    service = EnrichmentService(
        [
            FakeVTProvider(),
            FakeAbuseIPDBProvider(),
            FakeOTXProvider(),
        ]
    )

    result = await service.enrich_indicator("ipv4", "198.51.100.22")
    assert result.status == EnrichmentStatus.SUCCESS
    assert len(result.provider_results) == 3

    vt = next(r for r in result.provider_results if r.provider == "virustotal")
    assert vt.normalized_result["reputation"] == 42
    assert vt.normalized_result["last_analysis_stats"]["malicious"] == 12

    abuse = next(r for r in result.provider_results if r.provider == "abuseipdb")
    assert abuse.normalized_result["abuse_confidence_score"] == 85
    assert abuse.normalized_result["country_code"] == "US"

    otx = next(r for r in result.provider_results if r.provider == "otx")
    assert otx.normalized_result["pulse_count"] == 5


def test_portal_ioc_modal_endpoint() -> None:
    portal_service = MemoryPortalService()
    enrichment_service = EnrichmentService(
        [
            FakeVTProvider(),
            FakeAbuseIPDBProvider(),
            FakeOTXProvider(),
        ]
    )

    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
        enrichment_service=enrichment_service,
    )

    with TestClient(app) as client:
        # Request with report context
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/ioc-modal?type=ipv4&value=198.51.100.22"
        )
        assert response.status_code == 200
        html = response.text
        # Header & Indicator info
        assert "198.51.100.22" in html
        # CTI Analyst Assessment Panel
        assert "CTI Analyst Assessment" in html
        assert "Malicious / Critical Risk" in html
        assert "Key Analytical Findings" in html
        assert "SOC Operational Guidance" in html
        assert "Containment:" in html
        # Raw Provider Cards
        assert "VirusTotal" in html
        assert "12 Detections" in html
        assert "AbuseIPDB" in html
        assert "85% Abuse Confidence" in html
        assert "AlienVault OTX" in html
        assert "5 Pulses" in html
        assert "Threat Campaign Alpha" in html

        # Request standalone modal endpoint
        response_standalone = client.get(
            "/partials/ioc-modal?type=domain&value=evil[.]com"
        )
        assert response_standalone.status_code == 200
        assert (
            "evil.com" in response_standalone.text
            or "evil[.]com" in response_standalone.text
        )
        assert "CTI Analyst Assessment" in response_standalone.text


def test_portal_ioc_modal_disabled_providers() -> None:
    portal_service = MemoryPortalService()
    settings = Settings(
        database_required=False,
        virustotal_enabled=False,
        abuseipdb_enabled=False,
        otx_enabled=False,
    )
    app = create_app(settings, portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/ioc-modal?type=ipv4&value=198.51.100.22"
        )
        assert response.status_code == 200
        html = response.text
        assert "198.51.100.22" in html
        assert "Not Configured" in html
        assert "CTI Analyst Assessment" in html
        assert "Inconclusive / Unassessed" in html


def test_portal_iocs_partial_rendering() -> None:
    from uuid import uuid4

    from hermes_cti.models.contracts import EntityReference
    from hermes_cti.portal.routes import templates
    from hermes_cti.reporting.contracts import ReportIOC

    ioc_id = uuid4()
    ioc = ReportIOC(
        indicator=EntityReference(entity_type="indicator", entity_id=ioc_id),
        display_value="198.51.100.22",
        indicator_type="ipv4",
        evidence_ids=(uuid4(),),
    )

    detail = {
        "summary": {"slug": "test-slug", "canonical_url": "/reports/test-slug"},
        "iocs": (ioc,),
    }

    rendered = templates.get_template("partials/iocs.html").render(detail=detail)
    assert 'data-ioc-type="ipv4"' in rendered
    assert 'data-ioc-value="198.51.100.22"' in rendered
    assert "select-none" in rendered
    assert "pointer-events-none" in rendered
