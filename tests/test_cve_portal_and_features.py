"""Tests for dedicated CVE portal page (/cves), top navigation, collapsible sources,
and JSON feeds.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.ingestion.http_client import FetchResult
from hermes_cti.ingestion.normalization import normalize_json
from hermes_cti.models.contracts import (
    RawArtifactMetadata,
    SourceCategory,
    SourceConfig,
    SourceType,
)
from tests.test_phase2 import artifact as make_artifact
from tests.test_phase8 import MemoryPortalService


def _dummy_fetch_and_artifact(
    source_cfg: SourceConfig, body: bytes
) -> tuple[FetchResult, RawArtifactMetadata]:
    fetch = FetchResult(
        url=str(source_cfg.url),
        status_code=200,
        body=body,
        headers=(("content-type", "application/json"),),
        retry_count=0,
    )
    raw_art = make_artifact(source_cfg, body)
    return fetch, raw_art


def test_root_redirects_to_reports() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/reports"


def test_top_navigation_bar_in_base_template() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        # Check /reports has active Reports tab
        res_reports = client.get("/reports")
        assert res_reports.status_code == 200
        assert "Reports" in res_reports.text
        assert "CVEs &amp; Vulnerabilities" in res_reports.text
        assert 'href="/cves"' in res_reports.text

        # Check /cves has active CVEs tab
        res_cves = client.get("/cves")
        assert res_cves.status_code == 200
        assert "CVE &amp; Vulnerability Intelligence" in res_cves.text
        assert 'href="/reports"' in res_cves.text


def test_dedicated_cves_html_page_and_partials() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        # 1. Full HTML page
        res = client.get("/cves")
        assert res.status_code == 200
        assert "Vulnerability Center" in res.text
        assert 'id="q"' in res.text
        assert 'id="min_cvss"' in res.text
        assert 'id="min_epss"' in res.text
        assert 'id="sort"' in res.text
        assert 'name="known_exploited_only"' in res.text

        # 2. HTMX Partial list
        res_partial = client.get("/partials/cves")
        assert res_partial.status_code == 200


def test_public_cves_api_filtering_and_sorting() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        res = client.get("/api/v1/public/cves")
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["page"] == 1

        # Test query parameters
        res_search = client.get("/api/v1/public/cves?q=CVE-2026&sort=cvss")
        assert res_search.status_code == 200


def test_report_page_collapsible_sources_dropdown_card() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        res = client.get(f"/reports/{portal_service.report.slug}")
        assert res.status_code == 200
        html = res.text
        # Must have the collapsible details dropdown card at the bottom
        assert "Intelligence Sources &amp; Advisory Feeds" in html
        assert "<details" in html
        assert "<summary" in html
        assert "reference" in html


def test_vulnerability_page_exploit_mechanics_and_threat_hunt() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        # Full vulnerability page
        res = client.get("/vulnerabilities/CVE-2026-8452")
        assert res.status_code == 200
        html = res.text
        assert "Exploitation Mechanics &amp; Attack Progression" in html
        assert "4-Phase Exploit Sequence" in html
        assert "Phase 1 - Attack Surface Discovery" in html
        assert "Dedicated Threat Hunt &amp; Movement Detections" in html
        assert "Hypothesis &amp; Telemetry Hunt Procedure" in html
        assert "Lateral Movement &amp; Post-Exploitation Indicators" in html
        assert "Production Threat Detection Rules" in html
        assert "data-copy-target" in html
        assert "Sigma Rule" in html

        # Dedicated hunt sub-route
        res_hunt = client.get("/vulnerabilities/CVE-2026-8452/hunt")
        assert res_hunt.status_code == 200
        assert "Dedicated Threat Hunt &amp; Movement Detections" in res_hunt.text


def test_multi_format_json_feed_normalization() -> None:
    # 1. URLhaus JSON
    urlhaus_cfg = SourceConfig(
        source_id="urlhaus-recent",
        name="URLhaus",
        url="https://urlhaus-api.abuse.ch/v1/urls/recent/",
        source_type=SourceType.JSON,
        category=SourceCategory.TACTICAL_IOCS,
    )
    urlhaus_body = json.dumps(
        {
            "query_status": "ok",
            "urls": [
                {
                    "id": "310001",
                    "url": "http://198.51.100.44/payload.exe",
                    "url_status": "online",
                    "threat": "malware_download",
                    "tags": ["exe", "RedLine"],
                    "reporter": "abuse_ch",
                }
            ],
        }
    ).encode()
    fetch, artifact = _dummy_fetch_and_artifact(urlhaus_cfg, urlhaus_body)
    docs = normalize_json(urlhaus_cfg, fetch, artifact)
    assert len(docs) == 1
    assert "payload.exe" in str(docs[0].canonical_url)
    assert "malware_download" in docs[0].title

    # 2. ThreatFox JSON
    threatfox_cfg = SourceConfig(
        source_id="threatfox-recent",
        name="ThreatFox",
        url="https://threatfox-api.abuse.ch/api/v1/",
        source_type=SourceType.JSON,
        category=SourceCategory.TACTICAL_IOCS,
    )
    threatfox_body = json.dumps(
        {
            "query_status": "ok",
            "data": [
                {
                    "id": "99001",
                    "ioc": "203.0.113.88:443",
                    "threat_type": "botnet_cc",
                    "threat_type_desc": "Botnet C2",
                    "ioc_type": "ip:port",
                    "malware_printable": "AsyncRAT",
                    "confidence_level": 90,
                    "reporter": "threatfox",
                }
            ],
        }
    ).encode()
    fetch2, artifact2 = _dummy_fetch_and_artifact(threatfox_cfg, threatfox_body)
    docs2 = normalize_json(threatfox_cfg, fetch2, artifact2)
    assert len(docs2) == 1
    assert "AsyncRAT" in docs2[0].title
    assert "203.0.113.88:443" in docs2[0].normalized_text


def test_report_and_cve_rows_render_source_feed_tags() -> None:
    portal_service = MemoryPortalService()
    app = create_app(
        Settings(database_required=False),
        portal_service=portal_service,
    )
    with TestClient(app) as client:
        # 1. Reports page source tag
        resp_reports = client.get("/reports")
        assert resp_reports.status_code == 200
        assert "Origin Source Feed:" in resp_reports.text or "Updated " in resp_reports.text

        # 2. CVEs page source tag
        resp_cves = client.get("/cves")
        assert resp_cves.status_code == 200
        assert "CVE-2027-1234" in resp_cves.text
        assert "Origin Source Feed:" in resp_cves.text or "Active In-The-Wild" in resp_cves.text

