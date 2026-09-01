"""Transport-mocked unit tests for CTI OSINT enrichment.

Covers CISA KEV, FIRST EPSS, AbuseIPDB, and VirusTotal enrichment.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from hermes_cti.ingestion.enrichment import (
    AbuseIPDBEnricher,
    EPSSEnricher,
    IngestionEnrichmentService,
    KEVEnricher,
    VirusTotalEnricher,
)
from hermes_cti.models.contracts import EnrichmentStatus

KEV_MOCK_DATA = {
    "title": "CISA KEV Catalog",
    "catalogVersion": "2026.08.01",
    "vulnerabilities": [
        {
            "cveID": "CVE-2026-12345",
            "vendorProject": "Acme Corp",
            "product": "SecureGateway",
            "vulnerabilityName": "Acme Gateway Remote Code Execution",
            "dateAdded": "2026-08-10",
            "shortDescription": "Critical pre-auth RCE vulnerability.",
            "requiredAction": "Apply vendor patches immediately.",
            "dueDate": "2026-08-31",
            "knownRansomwareCampaignUse": "Known",
        }
    ],
}

EPSS_MOCK_DATA = {
    "status": "OK",
    "status-code": 200,
    "data": [
        {
            "cve": "CVE-2026-12345",
            "epss": "0.94120",
            "percentile": "0.99540",
            "date": "2026-08-22",
        },
        {
            "cve": "CVE-2026-54321",
            "epss": "0.00150",
            "percentile": "0.45000",
            "date": "2026-08-22",
        },
    ],
}

ABUSEIPDB_MOCK_DATA = {
    "data": {
        "ipAddress": "198.51.100.25",
        "isPublic": True,
        "ipVersion": 4,
        "isWhitelisted": False,
        "abuseConfidenceScore": 88,
        "countryCode": "US",
        "usageType": "Data Center/Web Hosting/Transit",
        "isp": "Example Cloud Provider",
        "domain": "examplecloud.com",
        "totalReports": 42,
        "numDistinctUsers": 12,
        "lastReportedAt": "2026-08-22T12:00:00+00:00",
    }
}

VT_IP_MOCK_DATA = {
    "data": {
        "id": "198.51.100.25",
        "type": "ip_address",
        "attributes": {
            "reputation": -50,
            "last_analysis_stats": {
                "malicious": 14,
                "suspicious": 3,
                "harmless": 40,
                "undetected": 15,
            },
            "tags": ["cobalt-strike", "c2"],
            "popular_threat_classification": {
                "suggested_threat_label": "trojan.cobaltstrike/beacon"
            },
        },
    }
}


@pytest.mark.asyncio
async def test_cisa_kev_lookup() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json=KEV_MOCK_DATA,
            headers={"content-type": "application/json"},
        )
    )
    enricher = KEVEnricher(transport=transport)
    try:
        is_exploited = await enricher.is_known_exploited("CVE-2026-12345")
        assert is_exploited is True

        details = await enricher.get_kev_details("CVE-2026-12345")
        assert details is not None
        assert details["vendor_project"] == "Acme Corp"
        assert details["product"] == "SecureGateway"

        # Not in KEV
        not_exploited = await enricher.is_known_exploited("CVE-1999-0001")
        assert not_exploited is False
    finally:
        await enricher.aclose()


@pytest.mark.asyncio
async def test_epss_lookup_and_batching() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=EPSS_MOCK_DATA,
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    enricher = EPSSEnricher(transport=transport)
    try:
        score_tuple = await enricher.get_epss_score("CVE-2026-12345")
        assert score_tuple is not None
        score, percentile = score_tuple
        assert score == pytest.approx(0.94120)
        assert percentile == pytest.approx(0.99540)

        # Batch lookup uses one request for uncached CVEs.
        requests.clear()
        batch = await enricher.get_epss_batch(["CVE-2026-54321", "CVE-2026-99999"])
        assert len(requests) == 1
        assert requests[0].url.params["cve"] == "CVE-2026-54321,CVE-2026-99999"
        assert batch["CVE-2026-54321"] is not None
        assert batch["CVE-2026-54321"][0] == pytest.approx(0.00150)
        assert batch["CVE-2026-99999"] is None

        # Per-CVE cache entries prevent a second batch request.
        await enricher.get_epss_batch(["CVE-2026-54321"])
        assert len(requests) == 1
    finally:
        await enricher.aclose()


@pytest.mark.asyncio
async def test_abuseipdb_enrichment_mocked() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json=ABUSEIPDB_MOCK_DATA,
            headers={"content-type": "application/json"},
        )
    )
    # Test with configured API key
    enricher = AbuseIPDBEnricher(api_key="test-abuseipdb-key", transport=transport)
    try:
        res = await enricher.check_ip("198.51.100.25")
        assert res is not None
        assert res["abuse_confidence_score"] == 88
        assert res["country_code"] == "US"
        assert res["total_reports"] == 42
    finally:
        await enricher.aclose()

    # Test without API key (graceful fallback)
    with patch.dict("os.environ", {}, clear=True):
        enricher_disabled = AbuseIPDBEnricher(api_key=None, transport=transport)
        try:
            disabled_res = await enricher_disabled.check_ip("198.51.100.25")
            assert disabled_res is None
        finally:
            await enricher_disabled.aclose()


@pytest.mark.asyncio
async def test_virustotal_enrichment_mocked() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json=VT_IP_MOCK_DATA,
            headers={"content-type": "application/json"},
        )
    )
    enricher = VirusTotalEnricher(api_key="test-vt-key", transport=transport)
    try:
        res = await enricher.enrich_indicator("ipv4", "198.51.100.25")
        assert res is not None
        assert res["malicious_count"] == 14
        assert res["suspicious_count"] == 3
        assert res["harmless_count"] == 40
        assert "cobalt-strike" in res["tags"]
    finally:
        await enricher.aclose()


@pytest.mark.asyncio
async def test_enrichment_cache_and_backoff() -> None:
    call_counts: dict[str, int] = {"kev": 0, "epss": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "known_exploited" in url_str:
            call_counts["kev"] += 1
            return httpx.Response(
                200,
                json=KEV_MOCK_DATA,
                headers={"content-type": "application/json"},
            )
        elif "epss" in url_str:
            call_counts["epss"] += 1
            return httpx.Response(
                200,
                json=EPSS_MOCK_DATA,
                headers={"content-type": "application/json"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    service = IngestionEnrichmentService(transport=transport)
    try:
        # First call hits network
        res1 = await service.enrich_cve("CVE-2026-12345")
        assert res1.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}
        assert call_counts["kev"] == 1
        assert call_counts["epss"] == 1

        # Second call hits in-memory cache
        res2 = await service.enrich_cve("CVE-2026-12345")
        assert res2.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}
        assert call_counts["kev"] == 1  # No additional network requests for KEV
        assert call_counts["epss"] == 1  # No additional network requests for EPSS
    finally:
        await service.aclose()
