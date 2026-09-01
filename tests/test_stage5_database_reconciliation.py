"""Comprehensive verification suite for Stage 5 Database Reconciliation & Integrity.

Verifies:
1. Never synthesizing/inventing CTI fallback reports, CVEs, or IoCs.
2. Live CVE enrichment using KEV/EPSS without substituting guessed scores.
3. Determinism across processes (no hash()) and provenance URL preservation.
4. STIX 2.1 bundle reference consistency and valid JSON artifacts.
5. CLI flag mode & subcommand compatibility without silent error swallowing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from typer.testing import CliRunner

from hermes_cti.cli.main import _execute_rebuild_all, _execute_sync_db, app
from hermes_cti.playbooks.rule_generator import (
    generate_sigma_rule,
)
from hermes_cti.publisher.site_builder import classify_epss_quadrant
from hermes_cti.publisher.stix_exporter import STIXExporter, create_stix_bundle

runner = CliRunner()


def test_no_synthetic_fallback_data_when_sources_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When sources fail, the system emits an honest empty result with metadata."""
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps(
            [
                {
                    "name": "Offline Feed",
                    "url": "https://offline.source.invalid/rss.xml",
                    "type": "rss",
                    "category": "cert_advisories",
                }
            ]
        ),
        encoding="utf-8",
    )
    memory_file = tmp_path / "MEMORY.md"
    memory_file.write_text("# Project Memory\n", encoding="utf-8")
    output_dir = tmp_path / "portal"

    # Mock transport to return connection error / 500
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(500, text="Internal Server Error")
    )
    orig_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = mock_transport
        return orig_client(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", client_factory)

    _execute_sync_db(
        source_path=sources_file,
        memory_path=memory_file,
        output_dir=output_dir,
    )

    db_path = output_dir / "data" / "cti_database.json"
    assert db_path.exists()
    db_json = json.loads(db_path.read_text(encoding="utf-8"))

    # Assert honest empty data - NO fake "Emergency CTI Advisory" or "CVE-2026-1234"
    assert db_json["reports"] == []
    assert db_json["cves"] == []
    assert db_json["iocs"] == []

    # Assert failure metadata is present and accurate
    assert len(db_json["failures"]) == 1
    assert db_json["failures"][0]["source_name"] == "Offline Feed"
    assert "HTTP 500" in db_json["failures"][0]["error"]
    assert db_json["metrics"]["failed_sources_count"] == 1

    # Assert MEMORY.md reflects 0 reports and logged failure
    memory_content = memory_file.read_text(encoding="utf-8")
    assert "0 reports" in memory_content
    assert "Failed sources: 1" in memory_content


def test_rebuild_all_does_not_inject_synthetic_fallbacks(tmp_path: Path) -> None:
    """_execute_rebuild_all must not fabricate reports if database is empty."""
    output_dir = tmp_path / "portal"
    _execute_rebuild_all(output_dir=output_dir)

    db_path = output_dir / "data" / "cti_database.json"
    assert db_path.exists()
    db_json = json.loads(db_path.read_text(encoding="utf-8"))
    assert db_json["reports"] == []
    assert db_json["cves"] == []
    assert db_json["iocs"] == []


def test_live_cve_enrichment_no_guessed_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CVEs from KEV feed or extracted must use actual values and None for missing."""
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps(
            [
                {
                    "name": "CISA KEV Feed",
                    "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                    "type": "json",
                }
            ]
        ),
        encoding="utf-8",
    )
    memory_file = tmp_path / "MEMORY.md"
    memory_file.write_text("# Project Memory\n", encoding="utf-8")
    output_dir = tmp_path / "portal"

    kev_json = {
        "vulnerabilities": [
            {
                "cveID": "CVE-2024-3400",
                "vendorProject": "Palo Alto Networks",
                "vulnerabilityName": "PAN-OS Command Injection",
                "shortDescription": "PAN-OS GlobalProtect pre-auth RCE.",
                "dateAdded": "2024-04-12",
            }
        ]
    }
    epss_json = {
        "status": "OK",
        "data": [
            {
                "cve": "CVE-2024-3400",
                "epss": "0.92340",
                "percentile": "0.98760",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "known_exploited" in url_str:
            return httpx.Response(200, json=kev_json)
        elif "epss" in url_str:
            return httpx.Response(200, json=epss_json)
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(handler)
    orig_client2 = httpx.AsyncClient

    def client_factory2(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = mock_transport
        return orig_client2(*args, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", client_factory2)

    _execute_sync_db(
        source_path=sources_file,
        memory_path=memory_file,
        output_dir=output_dir,
    )

    db_json = json.loads(
        (output_dir / "data" / "cti_database.json").read_text(encoding="utf-8")
    )
    cves = db_json["cves"]
    assert len(cves) == 1
    cve = cves[0]
    assert cve["id"] == "CVE-2024-3400"
    assert cve["known_exploited"] is True
    # Real EPSS score from provider
    assert cve["epss_score"] == pytest.approx(0.92340)
    assert cve["epss_percentile"] == pytest.approx(0.98760)
    # CVSS is not in KEV, so it must be None - never guessed (like 9.0 or 7.5)
    assert cve["cvss"] is None
    assert cve["cvss_score"] is None
    # Provenance source preserved
    assert cve["source_name"] == "CISA KEV Feed"
    assert "known_exploited" in cve["source_url"]


def test_deterministic_identifiers_and_provenance() -> None:
    """Sigma rule IDs and STIX bundle IDs must be deterministic and preserve URLs."""
    # 1. Deterministic Sigma Rule IDs
    rule1 = generate_sigma_rule(
        title="Cobalt Strike Named Pipe",
        description="Detects default Cobalt Strike named pipe patterns",
        process_names=["powershell.exe"],
        command_lines=["msagent_"],
    )
    rule2 = generate_sigma_rule(
        title="Cobalt Strike Named Pipe",
        description="Detects default Cobalt Strike named pipe patterns",
        process_names=["powershell.exe"],
        command_lines=["msagent_"],
    )
    assert "id:" in rule1
    id1 = [line for line in rule1.splitlines() if line.startswith("id:")][0]
    id2 = [line for line in rule2.splitlines() if line.startswith("id:")][0]
    assert id1 == id2

    # 2. Deterministic STIX 2.1 Bundle & Provenance Preservation
    exporter = STIXExporter()
    bundle1 = exporter.create_stix_bundle(
        report_title="Campaign Alpha",
        summary="Summary Alpha",
        published_date="2026-08-31T12:00:00Z",
        iocs=[
            {
                "type": "ipv4",
                "value": "198.51.100.25",
                "source_url": "https://cert.org/alert/1",
                "source_name": "CERT-US",
            }
        ],
        cves=[
            {
                "cve_id": "CVE-2024-1111",
                "source_url": "https://cert.org/alert/1",
                "source_name": "CERT-US",
            }
        ],
        techniques=["T1190"],
    )
    bundle2 = exporter.create_stix_bundle(
        report_title="Campaign Alpha",
        summary="Summary Alpha",
        published_date="2026-08-31T12:00:00Z",
        iocs=[
            {
                "type": "ipv4",
                "value": "198.51.100.25",
                "source_url": "https://cert.org/alert/1",
                "source_name": "CERT-US",
            }
        ],
        cves=[
            {
                "cve_id": "CVE-2024-1111",
                "source_url": "https://cert.org/alert/1",
                "source_name": "CERT-US",
            }
        ],
        techniques=["T1190"],
    )
    assert bundle1["id"] == bundle2["id"]

    # Check indicator and CVE external references preserve provenance URLs
    indicator_sdo = next(o for o in bundle1["objects"] if o["type"] == "indicator")
    assert "external_references" in indicator_sdo
    assert indicator_sdo["external_references"][0]["url"] == "https://cert.org/alert/1"

    vulnerability_sdo = next(
        o for o in bundle1["objects"] if o["type"] == "vulnerability"
    )
    assert any(
        ref.get("url") == "https://cert.org/alert/1"
        for ref in vulnerability_sdo["external_references"]
    )


def test_stix_bundle_and_object_reference_consistency() -> None:
    """Every relationship and report object ref must point to an object in bundle."""
    bundle = create_stix_bundle(
        report_title="Test Bundle Consistency",
        summary="Testing relationships and references",
        published_date="2026-08-31T12:00:00Z",
        iocs={"ipv4": ["198.51.100.55"]},
        cves=["CVE-2024-9999"],
        techniques=["T1059.001"],
    )

    objects = bundle["objects"]
    objects_by_id = {obj["id"]: obj for obj in objects}

    report_sdo = next(obj for obj in objects if obj["type"] == "report")
    # All object_refs must be valid IDs in the bundle
    for ref in report_sdo["object_refs"]:
        assert ref in objects_by_id

    relationships = [obj for obj in objects if obj["type"] == "relationship"]
    for rel in relationships:
        assert rel["source_ref"] in objects_by_id
        assert rel["target_ref"] in objects_by_id


def test_cli_flag_mode_and_subcommands_compatibility() -> None:
    """CLI must support top-level flags as well as subcommands."""
    with (
        patch("hermes_cti.cli.main._execute_sync_db") as mock_sync,
        patch("hermes_cti.cli.main._execute_rebuild_all") as mock_rebuild,
    ):
        # 1. Dual flags: python main.py --sync-db --rebuild-all
        res1 = runner.invoke(app, ["--sync-db", "--rebuild-all"])
        assert res1.exit_code == 0
        assert mock_sync.called
        assert mock_rebuild.called

    with patch("hermes_cti.cli.main._execute_sync_db") as mock_sync:
        # 2. Single flag: python main.py --sync-db
        res2 = runner.invoke(app, ["--sync-db"])
        assert res2.exit_code == 0
        assert mock_sync.called

    with patch("hermes_cti.cli.main._execute_sync_db") as mock_sync:
        # 3. Subcommand: python main.py sync-db
        res3 = runner.invoke(app, ["sync-db"])
        assert res3.exit_code == 0
        assert mock_sync.called

    with patch("hermes_cti.cli.main._execute_rebuild_all") as mock_rebuild:
        # 4. Subcommand: python main.py rebuild-all
        res4 = runner.invoke(app, ["rebuild-all"])
        assert res4.exit_code == 0
        assert mock_rebuild.called


def test_epss_quadrant_none_handling() -> None:
    """classify_epss_quadrant must handle None without crashing or guessing."""
    assert classify_epss_quadrant(None, None) == 3
    assert classify_epss_quadrant(8.5, None) == 2
    assert classify_epss_quadrant(None, 0.75) == 4
    assert classify_epss_quadrant(9.0, 0.50) == 1
