"""Tests for two-tiered threat hunt playbooks.

Covers modal play-by-play vs dedicated operational console.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.db.models import ReportVersion
from hermes_cti.models.contracts import (
    HuntPhase,
    HuntQuery,
    ThreatHunt,
)
from hermes_cti.portal.repository import ReportRow
from tests.test_phase7 import EVIDENCE_ID, VERSION_ID
from tests.test_phase8 import MemoryPortalService


class DetailedHuntMemoryPortalService(MemoryPortalService):
    def __init__(self) -> None:
        super().__init__()
        detailed_hunt = ThreatHunt(
            hunt_id=UUID("00000000-0000-0000-0000-000000000106"),
            report_version_id=VERSION_ID,
            objective="Find public exploitation telemetry.",
            scope="Publicly documented indicators and process execution behavior.",
            platforms=("Windows", "Linux"),
            telemetry_requirements=(
                "Process creation (Event ID 4688 / Sysmon 1)",
                "PowerShell scriptblock logs",
            ),
            lookback="30 days",
            hypothesis=(
                "The documented rundll32 process pattern may recur in telemetry."
            ),
            procedure=(
                "Scope endpoints with rundll32 execution.",
                "Run baseline SIEM query for suspicious parent processes.",
                "Eliminate benign administrative software hits.",
                "Validate forensic artifacts and isolate affected hosts.",
            ),
            expected_evidence=(
                "rundll32 process execution spawning unexpected child shells",
            ),
            false_positives=(
                "Scheduled administrative tasks using known signed scripts",
            ),
            escalation_criteria=(
                "Confirmed interactive command execution via rundll32",
            ),
            validation_checklist=("Confirm host IP, timestamp, and user context",),
            queries=("DeviceProcessEvents | where ProcessCommandLine has 'rundll32'",),
            typed_queries=(
                HuntQuery(
                    language="kql",
                    title="Microsoft Defender for Endpoint Rundll32 Search",
                    query=(
                        "DeviceProcessEvents | where FileName =~ 'rundll32.exe' "
                        "and ProcessCommandLine has 'setup.dll'"
                    ),
                    target_log_sources=("DeviceProcessEvents",),
                    tuning_guidance=(
                        "Filter out known SCCM deployment paths in Program Files."
                    ),
                ),
                HuntQuery(
                    language="spl",
                    title="Splunk Process Anomaly Query",
                    query=(
                        "index=main EventCode=4688 NewProcessName=*rundll32.exe "
                        "| stats count by ComputerName, CommandLine"
                    ),
                    target_log_sources=("index=main EventCode=4688",),
                    tuning_guidance=(
                        "Exclude domain controllers running standard "
                        "maintenance scripts."
                    ),
                ),
            ),
            execution_phases=(
                HuntPhase(
                    phase_number=1,
                    name="Baseline & Telemetry Scoping",
                    objective=(
                        "Ensure telemetry completeness and establish normal "
                        "parent-child baselines."
                    ),
                    steps=(
                        "Verify Sysmon Event ID 1 ingestion over the past 30 days.",
                        "Establish top 10 benign parent processes launching rundll32.",
                    ),
                    telemetry_sources=("Sysmon Event 1", "Security Event 4688"),
                    queries=(
                        HuntQuery(
                            language="kql",
                            title="Baseline Parent Process Sweep",
                            query=(
                                "DeviceProcessEvents | where FileName =~ "
                                "'rundll32.exe' | summarize count() by "
                                "InitiatingProcessFileName"
                            ),
                            target_log_sources=("DeviceProcessEvents",),
                            tuning_guidance=(
                                "Filter out known SCCM deployment paths in "
                                "Program Files."
                            ),
                        ),
                    ),
                    pivot_guidance=(
                        "Look for abnormal parent processes like winword.exe, "
                        "excel.exe, or powershell.exe",
                    ),
                    evidence_ids=(EVIDENCE_ID,),
                ),
                HuntPhase(
                    phase_number=2,
                    name="Triage & False Positive Elimination",
                    objective=(
                        "Filter benign software and identify true positive "
                        "malicious executions."
                    ),
                    steps=(
                        "Correlate DLL command line parameters against known "
                        "vendor hash lists.",
                        "Review network egress from matching process PIDs.",
                    ),
                    telemetry_sources=("Network Flow", "DNS Logs"),
                    pivot_guidance=(
                        "Check for outbound connections to newly registered domains",
                    ),
                    evidence_ids=(EVIDENCE_ID,),
                ),
            ),
            pivot_guidance=(
                "Correlate anomalous rundll32 invocations with scheduled task "
                "creation (Event ID 4698).",
            ),
            forensic_artifacts=(
                "Prefetch files (C:\\Windows\\Prefetch\\RUNDLL32.EXE-*.pf)",
                "PowerShell ScriptBlock Event Logs (Event ID 4104)",
                "ShimCache / AppCompatCache entries",
            ),
            evidence_ids=(EVIDENCE_ID,),
        )
        self.bundle = self.bundle.model_copy(update={"hunt": detailed_hunt})
        self.version = ReportVersion(
            id=self.bundle.report_version_id,
            report_id=self.bundle.report_id,
            version=self.bundle.version,
            executive_summary=self.bundle.executive_summary,
            technical_analysis=self.bundle.technical_analysis,
            evidence_summary=self.bundle.evidence_summary,
            analytical_caveats=list(self.bundle.caveats),
            source_coverage={},
            generated_by=self.bundle.generated_by,
            validation_status="published",
            structured_content=json.loads(self.bundle.stable_json()),
            evidence_ids=[str(item.evidence_id) for item in self.bundle.evidence],
            artifact_manifest={},
            skill_versions=[],
            application_version=self.bundle.application_version,
        )
        self.row = ReportRow(report=self.report, version=self.version)


def test_hunt_modal_partial_renders_concise_play_by_play() -> None:
    portal_service = DetailedHuntMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(
            f"/partials/reports/{portal_service.report.slug}/component/hunt"
        )
        assert response.status_code == 200
        html = response.text

        # Verify modal elements
        assert "Hunt Objective" in html
        assert "Lookback: 30 days" in html
        assert "Play-by-Play Procedure" in html
        assert "Rapid Triage Sequence" in html
        assert "Scope endpoints with rundll32 execution." in html
        assert "data-copy-target" in html
        assert "Open dedicated hunt page" in html


def test_dedicated_hunt_page_renders_operational_console() -> None:
    portal_service = DetailedHuntMemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        response = client.get(f"/reports/{portal_service.report.slug}/hunt")
        assert response.status_code == 200
        html = response.text

        # Verify operational execution phases and deep-dive elements
        assert "Hunt Strategy &amp; Objective" in html
        assert "Operational Execution Phases" in html
        assert "Baseline &amp; Telemetry Scoping" in html
        assert "Triage &amp; False Positive Elimination" in html
        assert "Tuning &amp; Baselines:" in html
        assert "Filter out known SCCM deployment paths" in html
        assert "Forensic Artifacts to Collect &amp; Preserve" in html
        assert "Prefetch files" in html
        assert "True Positive Confirmation Evidence" in html
        assert "Benign &amp; False Positive Explanations" in html
        assert "data-copy-target" in html


def test_legacy_hunt_backwards_compatibility() -> None:
    """Ensure older hunt contracts without execution_phases still render properly."""
    portal_service = MemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        modal_resp = client.get(
            f"/partials/reports/{portal_service.report.slug}/component/hunt"
        )
        assert modal_resp.status_code == 200
        assert "Play-by-Play Procedure" in modal_resp.text

        page_resp = client.get(f"/reports/{portal_service.report.slug}/hunt")
        assert page_resp.status_code == 200
        assert "Procedural Hunting Sequence" in page_resp.text
