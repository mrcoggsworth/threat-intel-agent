"""Tests for interactive evidence modal endpoint and CTI analyst synthesis."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.models.contracts import (
    HuntPhase,
    HuntQuery,
    PublicSourceReference,
    ReliabilityClassification,
    SourceCategory,
    ThreatHunt,
)
from hermes_cti.reporting.contracts import ReportEvidence, ReportEvidenceType
from tests.test_phase7 import VERSION_ID
from tests.test_phase8 import MemoryPortalService


class EvidenceModalMemoryPortalService(MemoryPortalService):
    def __init__(self) -> None:
        super().__init__()
        self.test_evidence_id = UUID("00000000-0000-0000-0000-000000000999")
        evidence_item = ReportEvidence(
            evidence_id=self.test_evidence_id,
            evidence_type=ReportEvidenceType.SOURCE_TEXT,
            statement=(
                "Adversary executed powershell.exe and rundll32.exe to download "
                "second-stage payload from malicious C2 domain evil-c2.example."
            ),
            source_document_id=uuid4(),
            source_reference=PublicSourceReference(
                source_id="cisa-advisory-test",
                name="CISA Cybersecurity Advisory",
                canonical_url="https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-001a",
                category=SourceCategory.CERT_ADVISORIES,
                reliability=ReliabilityClassification.AUTHORITATIVE,
            ),
            confidence=0.95,
            public_safe=True,
        )

        hunt = ThreatHunt(
            hunt_id=uuid4(),
            report_version_id=VERSION_ID,
            objective="Detect abnormal rundll32 and powershell execution.",
            scope="Endpoints and network perimeter.",
            platforms=("Windows",),
            telemetry_requirements=("Sysmon Event 1", "DNS Logs"),
            lookback="30 days",
            hypothesis="Living-off-the-land binaries used for payload staging.",
            procedure=(
                "Scope rundll32 execution.",
                "Correlate with parent process tree.",
                "Exclude SCCM baselines.",
                "Isolate affected endpoints.",
            ),
            evidence_ids=(self.test_evidence_id,),
            typed_queries=(
                HuntQuery(
                    language="kql",
                    title="Suspicious Rundll32 Execution",
                    query="DeviceProcessEvents | where FileName =~ 'rundll32.exe'",
                ),
            ),
            execution_phases=(
                HuntPhase(
                    phase_number=1,
                    name="Baseline Scoping",
                    objective="Scope rundll32 executions.",
                    steps=("Sweep endpoint logs for rundll32.",),
                    evidence_ids=(self.test_evidence_id,),
                ),
            ),
        )

        bundle = self.bundle.model_copy(
            update={
                "evidence": (*self.bundle.evidence, evidence_item),
                "hunt": hunt,
            }
        )
        self.bundle = bundle
        self.version.structured_content = json.loads(bundle.stable_json())
        self.version.evidence_ids = [str(item.evidence_id) for item in bundle.evidence]


def test_portal_evidence_modal_endpoint_renders_statement_and_synthesis() -> None:
    portal_service = EvidenceModalMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/evidence/{portal_service.test_evidence_id}"
        )
        assert response.status_code == 200
        html = response.text

        # Verify header & evidence content
        assert "Public Evidence" in html
        assert "95% Confidence" in html
        assert "Source Statement" in html
        assert "powershell.exe and rundll32.exe" in html
        assert "CISA Cybersecurity Advisory" in html
        assert (
            "https://www.cisa.gov/news-events/cybersecurity-advisories/aa26-001a"
            in html
        )

        # Verify CTI Analyst synthesis & hunt context
        assert "CTI Analyst Interpretation &amp; Hunt Context" in html
        assert "What This Evidence Establishes" in html
        assert "Threat Hunt Application" in html
        assert "Triage &amp; False-Positive Caveats" in html
        assert "Recommended Telemetry Pivots" in html
        assert "Sysmon Event ID 1 (Process Creation)" in html
        assert "data-copy-target" in html


def test_portal_evidence_modal_query_param_routing() -> None:
    portal_service = EvidenceModalMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/evidence-modal?evidence_id={portal_service.test_evidence_id}"
        )
        assert response.status_code == 200
        assert "Source Statement" in response.text
        assert "CTI Analyst Interpretation" in response.text


def test_portal_hunt_page_renders_interactive_evidence_links() -> None:
    portal_service = EvidenceModalMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(f"/reports/{portal_service.report.slug}/hunt")
        assert response.status_code == 200
        html = response.text

        # Verify clickable evidence triggers
        assert "data-report-link" in html
        assert f"/evidence/{portal_service.test_evidence_id}" in html
        assert f'data-evidence-id="{portal_service.test_evidence_id}"' in html


def test_portal_evidence_modal_invalid_uuid_returns_400() -> None:
    portal_service = EvidenceModalMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/evidence/not-a-valid-uuid"
        )
        assert response.status_code == 400
        assert "Invalid evidence UUID" in response.json()["detail"]


def test_portal_evidence_modal_missing_id_returns_400() -> None:
    portal_service = EvidenceModalMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get("/partials/evidence-modal")
        assert response.status_code == 400
        assert "evidence_id is required" in response.json()["detail"]
