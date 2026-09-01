"""Focused unit tests for Publisher subagent: SiteBuilder, STIXExporter, etc."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.models.contracts import Severity
from hermes_cti.publisher.notifier import (
    DiscordNotifier,
    SlackNotifier,
    TeamsNotifier,
    ThreatNotifier,
    WebhookDispatcher,
)
from hermes_cti.publisher.site_builder import (
    SiteBuilder,
    classify_epss_quadrant,
)
from hermes_cti.publisher.stix_exporter import STIXExporter
from tests.test_phase8 import MemoryPortalService


def test_stix_bundle_generation() -> None:
    """Verify STIX 2.1 bundle structure, object types, and UUID formatting."""
    exporter = STIXExporter()

    report_title = "Active Exploitation Campaign against Apache ActiveMQ"
    summary = "Threat actor deploying Golang backdoor via CVE-2023-46604."
    iocs = {
        "ipv4": ["198.51.100.45", "203.0.113.10"],
        "sha256": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
        "domain": ["c2-callback.example.org"],
    }
    cves = ["CVE-2023-46604"]
    techniques = ["T1190", "T1059.001"]

    bundle = exporter.create_stix_bundle(
        report_title=report_title,
        summary=summary,
        published_date="2026-08-31T20:00:00.000Z",
        iocs=iocs,
        cves=cves,
        techniques=techniques,
        confidence=0.92,
    )

    # Validate Bundle wrapper
    assert bundle["type"] == "bundle"
    assert bundle["id"].startswith("bundle--")
    objects = bundle["objects"]
    assert len(objects) > 0

    # Index objects by type and id
    obj_by_type: dict[str, list[dict[str, Any]]] = {}
    obj_by_id: dict[str, dict[str, Any]] = {}
    for obj in objects:
        assert obj["spec_version"] == "2.1"
        assert "--" in obj["id"]
        obj_by_type.setdefault(obj["type"], []).append(obj)
        obj_by_id[obj["id"]] = obj

    # 1. Author identity
    assert "identity" in obj_by_type
    assert obj_by_type["identity"][0]["name"] == "CTI-Hermes Autonomous Agent"

    # 2. Report SDO
    assert "report" in obj_by_type
    report_sdo = obj_by_type["report"][0]
    assert report_sdo["name"] == report_title
    assert report_sdo["description"] == summary
    assert report_sdo["confidence"] == 92
    assert len(report_sdo["object_refs"]) > 0

    # 3. Indicator SDOs & Patterning
    assert "indicator" in obj_by_type
    assert len(obj_by_type["indicator"]) == 4  # 2 IPs + 1 SHA256 + 1 Domain
    for ind in obj_by_type["indicator"]:
        assert ind["pattern_type"] == "stix"
        assert ind["pattern_version"] == "2.1"
        assert ind["id"] in report_sdo["object_refs"]

    patterns = [ind["pattern"] for ind in obj_by_type["indicator"]]
    assert "[ipv4-addr:value = '198.51.100.45']" in patterns
    assert "[domain-name:value = 'c2-callback.example.org']" in patterns
    sha_pattern = (
        "[file:hashes.'SHA-256' = "
        "'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855']"
    )
    assert sha_pattern in patterns

    # 4. Vulnerability SDOs
    assert "vulnerability" in obj_by_type
    vuln = obj_by_type["vulnerability"][0]
    assert vuln["name"] == "CVE-2023-46604"
    assert vuln["external_references"][0]["source_name"] == "cve"

    # 5. Attack Pattern SDOs
    assert "attack-pattern" in obj_by_type
    attack_ids = [
        ap["external_references"][0]["external_id"]
        for ap in obj_by_type["attack-pattern"]
    ]
    assert "T1190" in attack_ids
    assert "T1059.001" in attack_ids

    # 6. Relationship SROs
    assert "relationship" in obj_by_type
    rel_types = {rel["relationship_type"] for rel in obj_by_type["relationship"]}
    assert "indicates" in rel_types
    assert "targets" in rel_types

    # Ensure source and target references exist in bundle
    for rel in obj_by_type["relationship"]:
        assert rel["source_ref"] in obj_by_id
        assert rel["target_ref"] in obj_by_id


def test_slack_webhook_payload_format() -> None:
    """Validate Slack Block Kit JSON schema and section blocks."""
    notifier = SlackNotifier()
    payload = notifier.build_payload(
        headline="Critical 0-Day Flaw in Edge Routers",
        summary="Remote unauthenticated code execution observed in the wild.",
        severity=Severity.CRITICAL,
        confidence=0.95,
        report_url="https://hermes.intel.local/reports/critical-edge-0day",
        cves=["CVE-2026-9999"],
        iocs=["198.51.100.99"],
        techniques=["T1190"],
    )

    assert "blocks" in payload
    blocks = payload["blocks"]
    assert len(blocks) >= 4

    # Header block
    assert blocks[0]["type"] == "header"
    assert "Critical 0-Day Flaw" in blocks[0]["text"]["text"]

    # Severity and Confidence block
    assert blocks[1]["type"] == "section"
    assert "*Severity:*" in blocks[1]["text"]["text"]
    assert "CRITICAL" in blocks[1]["text"]["text"]
    assert "95%" in blocks[1]["text"]["text"]

    # Summary block
    assert blocks[2]["type"] == "section"
    assert "*Executive Summary*" in blocks[2]["text"]["text"]

    # Fields block (CVEs, MITRE, IOCs)
    fields_block = next((b for b in blocks if "fields" in b), None)
    assert fields_block is not None
    field_texts = [f["text"] for f in fields_block["fields"]]
    assert any("CVE-2026-9999" in text for text in field_texts)
    assert any("T1190" in text for text in field_texts)
    assert any("198.51.100.99" in text for text in field_texts)

    # Actions button block
    action_block = next((b for b in blocks if b["type"] == "actions"), None)
    assert action_block is not None
    button = action_block["elements"][0]
    assert button["type"] == "button"
    assert button["url"] == "https://hermes.intel.local/reports/critical-edge-0day"


def test_teams_webhook_payload_format() -> None:
    """Validate Teams card JSON schema and facts formatting."""
    notifier = TeamsNotifier()
    payload = notifier.build_payload(
        headline="Ransomware Campaign Targeting Healthcare",
        summary="Phishing vector delivering encrypted payload via Cobalt Strike.",
        severity=Severity.HIGH,
        confidence=0.88,
        report_url="https://hermes.intel.local/reports/healthcare-ransomware",
        cves=["CVE-2025-1111"],
        iocs=["malicious-domain.com"],
        techniques=["T1566.001"],
    )

    assert payload["type"] == "message"
    assert "attachments" in payload
    attachment = payload["attachments"][0]
    assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"

    card = attachment["content"]
    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.4"
    assert len(card["body"]) >= 3

    # Title & summary TextBlocks
    assert "Ransomware Campaign" in card["body"][0]["text"]
    assert "Phishing vector" in card["body"][1]["text"]

    # FactSet
    fact_set = next((b for b in card["body"] if b["type"] == "FactSet"), None)
    assert fact_set is not None
    fact_dict = {f["title"]: f["value"] for f in fact_set["facts"]}
    assert fact_dict["Severity"] == "HIGH"
    assert fact_dict["Confidence"] == "88%"
    assert "CVE-2025-1111" in fact_dict["CVEs"]
    assert "T1566.001" in fact_dict["MITRE ATT&CK"]

    # Action open url
    assert len(card["actions"]) == 1
    assert card["actions"][0]["type"] == "Action.OpenUrl"
    assert (
        card["actions"][0]["url"]
        == "https://hermes.intel.local/reports/healthcare-ransomware"
    )


def test_discord_webhook_payload_format() -> None:
    """Validate Discord Embed payload formatting."""
    notifier = DiscordNotifier()
    payload = notifier.build_payload(
        headline="Supply Chain Compromise in PyPI Package",
        summary="Typosquatted package exfiltrating environment tokens.",
        severity=Severity.MEDIUM,
        confidence=0.90,
        report_url="https://hermes.intel.local/reports/pypi-supply-chain",
        iocs=["evil-exfil.com"],
        techniques=["T1195.001"],
    )

    assert payload["username"] == "Hermes CTI"
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "Supply Chain Compromise" in embed["title"]
    assert embed["url"] == "https://hermes.intel.local/reports/pypi-supply-chain"
    assert embed["color"] > 0

    field_dict = {f["name"]: f["value"] for f in embed["fields"]}
    assert field_dict["Severity"] == "MEDIUM"
    assert field_dict["Confidence"] == "90%"
    assert "T1195.001" in field_dict["MITRE ATT&CK"]
    assert "`evil-exfil.com`" in field_dict["Sample IOCs"]


@pytest.mark.asyncio
async def test_threat_notifier_dispatcher_mocked() -> None:
    """Validate async dispatching with mocked HTTP client."""
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_client.post.return_value = mock_response

    dispatcher = WebhookDispatcher(client=mock_client, rate_limit_delay=0.0)
    notifier = ThreatNotifier(dispatcher=dispatcher)

    portal_service = MemoryPortalService()
    report = portal_service.report

    # Test Slack dispatch
    ok = await notifier.notify_slack(
        "https://hooks.slack.com/services/test/test/test",
        report,
        report_url="https://hermes.local/reports/test",
    )
    assert ok is True
    assert mock_client.post.called
    args, kwargs = mock_client.post.call_args
    assert "blocks" in kwargs["json"]


def test_epss_quadrant_classification_logic() -> None:
    """Verify classification of CVEs into the 4 exploitability quadrants."""
    from hermes_cti.publisher.site_builder import get_quadrant_metadata

    # Quadrant I: Urgent Action / Active Exploitation (CVSS >= 7.0, EPSS >= 0.15)
    q1_a = classify_epss_quadrant(7.0, 0.15)
    assert q1_a == 1
    meta1 = get_quadrant_metadata(q1_a)
    assert meta1["priority"] == "critical"
    assert "Urgent Action" in meta1["label"]

    q1_b = classify_epss_quadrant(9.8, 0.85)
    assert q1_b == 1

    # Quadrant II: High Impact / Low Probability (CVSS >= 7.0, EPSS < 0.15)
    q2_a = classify_epss_quadrant(7.5, 0.05)
    assert q2_a == 2
    meta2 = get_quadrant_metadata(q2_a)
    assert meta2["priority"] == "high"
    assert "High Impact" in meta2["label"]

    # Quadrant III: Low Priority (CVSS < 7.0, EPSS < 0.15)
    q3_a = classify_epss_quadrant(5.3, 0.02)
    assert q3_a == 3
    meta3 = get_quadrant_metadata(q3_a)
    assert meta3["priority"] == "low"
    assert "Low Priority" in meta3["label"]

    # Quadrant IV: Weaponized Fast Attack (CVSS < 7.0, EPSS >= 0.15)
    q4_a = classify_epss_quadrant(6.5, 0.45)
    assert q4_a == 4
    meta4 = get_quadrant_metadata(q4_a)
    assert meta4["priority"] == "medium"
    assert "Weaponized" in meta4["label"]

    # Edge cases: None or zero
    q_none = classify_epss_quadrant(None, None)
    assert q_none == 3


def test_site_builder_static_compilation(tmp_path: Path) -> None:
    """Verify SiteBuilder.build_portal produces valid HTML files."""
    builder = SiteBuilder()

    reports_data = [
        {
            "headline": "LockBit 4.0 Campaign Analysis",
            "executive_summary": "Active ransomware targeting Windows AD.",
            "report_type": "Ransomware Advisory",
            "severity": "critical",
            "confidence": 0.95,
        }
    ]
    cves_data = [
        {
            "cve_id": "CVE-2024-21413",
            "summary": "Microsoft Outlook Remote Code Execution Flaw",
            "cvss_score": 9.8,
            "epss_score": 0.35,
            "known_exploited": True,
        },
        {
            "cve_id": "CVE-2024-1000",
            "summary": "Minor Local Privilege Escalation",
            "cvss_score": 5.0,
            "epss_score": 0.01,
            "known_exploited": False,
        },
    ]
    iocs_data = [
        {"indicator_type": "ipv4", "display_value": "198.51.100.22"},
        {"indicator_type": "sha256", "display_value": "abc123def456"},
    ]

    output_dir = tmp_path / "portal_export"
    builder.build_portal(
        output_dir=output_dir,
        reports_data=reports_data,
        cves_data=cves_data,
        iocs_data=iocs_data,
    )

    # Check generated files
    assert (output_dir / "index.html").exists()
    assert (output_dir / "reports.html").exists()
    assert (output_dir / "cves.html").exists()
    assert (output_dir / "data" / "cti_database.json").exists()
    assert (output_dir / "data" / "stix2_bundle.json").exists()
    assert (output_dir / "assets" / "portal.css").exists()
    assert (output_dir / "assets" / "portal.js").exists()

    # Validate cti_database.json contents
    cti_json = json.loads(
        (output_dir / "data" / "cti_database.json").read_text(encoding="utf-8")
    )
    assert cti_json["metrics"]["total_reports"] == 1
    assert cti_json["metrics"]["total_cves"] == 2
    assert cti_json["metrics"]["total_iocs"] == 2
    assert cti_json["metrics"]["critical_cves"] == 1
    assert cti_json["metrics"]["active_kev_count"] == 1

    # Validate STIX 2.1 export bundle
    stix_json = json.loads(
        (output_dir / "data" / "stix2_bundle.json").read_text(encoding="utf-8")
    )
    assert stix_json["type"] == "bundle"
    assert len(stix_json["objects"]) > 0

    # Validate index.html rendering
    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "EPSS vs. CVSS Exploitability Matrix" in index_html
    assert "LockBit 4.0 Campaign Analysis" in index_html
    assert "198.51.100.22" in index_html
    assert "data/stix2_bundle.json" in index_html


def test_portal_api_stix_endpoint() -> None:
    """Verify portal STIX 2.1 JSON export endpoint."""
    portal_service = MemoryPortalService()
    app = create_app(Settings(database_required=False), portal_service=portal_service)

    with TestClient(app) as client:
        slug = portal_service.report.slug
        response = client.get(f"/api/v1/reports/{slug}/stix")
        assert response.status_code == 200
        bundle = response.json()
        assert bundle["type"] == "bundle"
        assert any(obj["type"] == "report" for obj in bundle["objects"])
        assert any(obj["type"] == "indicator" for obj in bundle["objects"])
