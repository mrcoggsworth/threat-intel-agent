"""Offline Phase 5 provider, cache, outage, and scoring tests."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from hermes_cti.api.main import create_app
from hermes_cti.cli.main import app as cli_app
from hermes_cti.core.settings import Settings
from hermes_cti.enrichment import (
    CISAKEVProvider,
    EnrichmentCache,
    EnrichmentService,
    EPSSProvider,
    NVDProvider,
    ScoreInputs,
    build_providers,
    calculate_priority_score,
)
from hermes_cti.enrichment.providers import ProviderRuntimeConfig
from hermes_cti.enrichment.vulnerability import (
    normalized_fields,
    select_canonical_fields,
)
from hermes_cti.ingestion.http_client import AsyncHTTPClient, HTTPClientConfig
from hermes_cti.models import (
    EnrichmentStatus,
    EntityReference,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    Severity,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)
ENTITY_ID = UUID("00000000-0000-0000-0000-000000000005")


def make_request(
    query: str = "CVE-2021-40438", *, kind: str = "cve"
) -> ProviderRequest:
    return ProviderRequest(
        entity=EntityReference(entity_type="vulnerability", entity_id=ENTITY_ID),
        query_key=query,
        query_kind=kind,
        requested_at=NOW,
    )


def kev_payload() -> dict[str, object]:
    return {
        "vulnerabilities": [
            {
                "cveID": "CVE-2021-40438",
                "vendorProject": "Example",
                "product": "Example Product",
                "vulnerabilityName": "Example RCE",
                "dateAdded": "2026-08-01",
                "dueDate": "2026-08-15",
                "requiredAction": "Apply vendor mitigation.",
            }
        ]
    }


def epss_payload() -> dict[str, object]:
    return {
        "status": "OK",
        "status-code": 200,
        "data": [
            {
                "cve": "CVE-2021-40438",
                "epss": "0.972240000",
                "percentile": "1.000000000",
                "date": "2026-08-23",
            }
        ],
    }


def nvd_payload() -> dict[str, object]:
    return {
        "resultsPerPage": 1,
        "startIndex": 0,
        "totalResults": 1,
        "vulnerabilities": [
            {
                "cve": {
                    "id": "CVE-2021-40438",
                    "published": "2026-07-01T00:00:00.000",
                    "lastModified": "2026-08-20T00:00:00.000",
                    "descriptions": [
                        {"lang": "en", "value": "A public vulnerability description."}
                    ],
                    "metrics": {
                        "cvssMetricV31": [
                            {
                                "cvssData": {
                                    "baseScore": 9.8,
                                    "vectorString": "CVSS:3.1/AV:N",
                                }
                            }
                        ]
                    },
                    "weaknesses": [
                        {"description": [{"lang": "en", "value": "CWE-787"}]}
                    ],
                }
            }
        ],
    }


def fixture_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "known_exploited" in url or url.endswith("/kev"):
            return httpx.Response(200, json=kev_payload())
        if "epss" in url:
            return httpx.Response(200, json=epss_payload())
        if "cves" in url:
            return httpx.Response(200, json=nvd_payload())
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_recorded_provider_success_responses() -> None:
    config = ProviderRuntimeConfig(max_retries=0, ttl_seconds=3600)
    providers = (
        CISAKEVProvider(
            "https://fixture/known_exploited.json",
            config=config,
            transport=fixture_transport(),
        ),
        EPSSProvider(
            "https://fixture/epss",
            config=config,
            transport=fixture_transport(),
        ),
        NVDProvider(
            "https://fixture/cves/2.0",
            config=config,
            transport=fixture_transport(),
        ),
    )
    try:
        responses = await asyncio.gather(
            *(provider.enrich(make_request()) for provider in providers)
        )
    finally:
        await asyncio.gather(*(provider.aclose() for provider in providers))
    assert all(item.status is EnrichmentStatus.SUCCESS for item in responses)
    assert responses[0].normalized_result["known_exploited"] is True
    assert responses[1].normalized_result["epss_score"] == 0.97224
    assert responses[2].normalized_result["cvss_score"] == 9.8
    assert responses[2].payload_hash is not None
    assert responses[2].raw_metadata.http_status == 200


@pytest.mark.asyncio
async def test_provider_timeout_is_retryable() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout")

    provider = CISAKEVProvider(
        "https://fixture/kev",
        config=ProviderRuntimeConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await provider.enrich(make_request())
    finally:
        await provider.aclose()
    assert response.status is EnrichmentStatus.UNAVAILABLE
    assert response.retryable is True
    assert response.error_classification.value == "timeout"
    assert "fixture timeout" not in response.error_detail


@pytest.mark.asyncio
async def test_rate_limit_honors_retry_after() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return (
            httpx.Response(429, headers={"retry-after": "3"})
            if calls == 1
            else httpx.Response(200, json={"ok": True})
        )

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    client = AsyncHTTPClient(
        HTTPClientConfig(
            max_retries=1, retry_max_delay_seconds=5, retry_jitter_seconds=0
        ),
        transport=httpx.MockTransport(handler),
        sleep=record_sleep,
    )
    result = await client.fetch("https://fixture/retry", timeout_seconds=1)
    await client.aclose()
    assert result.status_code == 200
    assert calls == 2
    assert sleeps == [3.0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "classification"),
    [(b"not-json", "malformed_payload"), (json.dumps({"wrong": []}), "schema_drift")],
)
async def test_malformed_payload_and_schema_drift(
    body: bytes | str, classification: str
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=body.encode() if isinstance(body, str) else body,
            headers={"content-type": "application/json"},
        )

    provider = CISAKEVProvider(
        "https://fixture/kev",
        config=ProviderRuntimeConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        response = await provider.enrich(make_request())
    finally:
        await provider.aclose()
    assert response.error_classification.value == classification
    assert response.normalized_result == {}


def test_missing_optional_credentials_disable_provider_without_startup_failure() -> (
    None
):
    settings = Settings(
        database_required=False,
        virustotal_enabled=True,
        otx_enabled=True,
        abuseipdb_enabled=True,
    )
    providers = build_providers(settings)
    assert [provider.enabled for provider in providers[-3:]] == [False, False, False]
    assert "api_key" not in json.dumps(
        [provider.health().model_dump(mode="json") for provider in providers]
    )


@pytest.mark.asyncio
async def test_cache_hit_and_expiry() -> None:
    clock = [NOW]
    cache = EnrichmentCache(now=lambda: clock[0], stale_if_error_seconds=60)
    provider = CISAKEVProvider(
        "https://fixture/kev",
        config=ProviderRuntimeConfig(max_retries=0, ttl_seconds=30),
        transport=fixture_transport(),
    )
    service = EnrichmentService((provider,), cache=cache)
    try:
        first = await service.enrich(make_request())
        second = await service.enrich(make_request())
        clock[0] = NOW + timedelta(seconds=31)
        expired = cache.get("cisa_kev", "CVE-2021-40438", now=clock[0])
    finally:
        await provider.aclose()
    assert first.provider_results[0].cache_hit is False
    assert second.provider_results[0].cache_hit is True
    assert expired.stale is True


def response(
    provider: str,
    status: EnrichmentStatus,
    values: dict[str, object],
    *,
    expires_at: datetime | None = NOW + timedelta(seconds=30),
) -> ProviderResponse:
    return ProviderResponse(
        provider=provider,
        request=make_request(),
        retrieved_at=NOW,
        expires_at=expires_at,
        status=status,
        normalized_result=values,
    )


class FakeProvider:
    def __init__(self, name: str, values: list[ProviderResponse]) -> None:
        self.name = name
        self.enabled = True
        self.values = values
        self.calls = 0

    async def enrich(self, _: ProviderRequest) -> ProviderResponse:
        item = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        return item

    def health(self, now: datetime | None = None) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name, enabled=True, state=EnrichmentStatus.SUCCESS
        )

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_partial_conflicting_evidence_and_stale_outage() -> None:
    provider_a = FakeProvider(
        "fake-a",
        [
            response("fake-a", EnrichmentStatus.SUCCESS, {"cvss_score": 9.8}),
            response("fake-a", EnrichmentStatus.UNAVAILABLE, {}),
        ],
    )
    provider_b = FakeProvider(
        "fake-b", [response("fake-b", EnrichmentStatus.SUCCESS, {"cvss_score": 7.5})]
    )
    service = EnrichmentService(
        (provider_a, provider_b), cache=EnrichmentCache(stale_if_error_seconds=120)
    )
    first = await service.enrich(make_request())
    later = make_request().model_copy(
        update={"requested_at": NOW + timedelta(seconds=31)}
    )
    second = await service.enrich(later)
    assert first.conflicts["cvss_score"] == (9.8, 7.5)
    assert second.provider_results[0].status is EnrichmentStatus.STALE
    assert second.provider_results[0].normalized_result["cvss_score"] == 9.8


def test_score_breakdown_reproduces_final_score() -> None:
    priority = calculate_priority_score(
        ScoreInputs(
            known_exploited=True,
            cvss_score=9.8,
            epss_score=0.97224,
            published_at=NOW - timedelta(days=10),
            affected_product_significance=0.8,
            source_reliability=0.9,
            independent_corroboration=2,
        ),
        now=NOW,
    )
    assert priority.severity is Severity.CRITICAL
    assert priority.score == round(sum(item.value for item in priority.components), 4)
    assert {item.name for item in priority.components} == {
        "exploitation_state",
        "cvss",
        "epss",
        "recency",
        "affected_product_significance",
        "source_reliability",
        "independent_corroboration",
    }


def test_private_health_and_cli_fail_closed() -> None:
    with TestClient(create_app(Settings(database_required=False))) as client:
        assert client.get("/api/v1/admin/provider-health").status_code == 404
    result = CliRunner().invoke(cli_app, ["db", "enrich"])
    assert result.exit_code == 1
    assert "provide at least one" in result.output
    assert "api_key" not in result.output.lower()


def test_typed_vulnerability_normalization_and_precedence() -> None:
    response = ProviderResponse(
        provider="nvd",
        request=make_request(),
        retrieved_at=NOW,
        status=EnrichmentStatus.SUCCESS,
        normalized_result={
            "cvss_vector": "CVSS:3.1/AV:N",
            "cwe_ids": ["CWE-787", "CWE-787"],
            "epss_percentile": "0.98",
            "published_at": "2026-07-01T00:00:00Z",
        },
        payload_hash="a" * 64,
    )
    fields = normalized_fields(response)
    assert fields["cvss_version"] == "3.1"
    assert fields["cwe_ids"] == ["CWE-787"]
    assert fields["epss_percentile"] == 0.98

    older = SimpleNamespace(
        provider="nvd", status="success", retrieved_at=NOW, cvss_score=7.5
    )
    newer = SimpleNamespace(
        provider="nvd",
        status="success",
        retrieved_at=NOW + timedelta(hours=1),
        cvss_score=9.8,
    )
    selected = select_canonical_fields([older, newer])
    assert selected["cvss_score"][0] == 9.8
