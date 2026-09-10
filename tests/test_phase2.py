"""Offline Phase 2 ingestion and normalization tests."""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from hermes_cti.core.settings import Settings
from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    HTTPClientConfig,
)
from hermes_cti.ingestion.normalization import (
    NormalizationError,
    normalize_feed,
    normalize_html,
    normalize_json,
    normalize_kev,
    normalize_pdf,
)
from hermes_cti.ingestion.service import IngestionService
from hermes_cti.models.contracts import (
    BodyEncoding,
    HTTPMethod,
    ParserAdapter,
    RawArtifactMetadata,
    RunStatus,
    SourceConfig,
    SourceRegistry,
    SourceRequest,
)

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Example</title><language>en-US</language>
<item><guid>item-2</guid><title>Second</title><link>https://example.test/second</link>
<pubDate>Tue, 03 Feb 2026 12:00:00 GMT</pubDate>
<description><![CDATA[<p>Visible <strong>content</strong>.</p>
<script>bad()</script><style>.x{}</style>]]></description>
<author>Alice</author></item>
<item><guid>item-1</guid><title>First</title><link>https://example.test/first</link>
<description>First body</description></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">
<title>Atom source</title>
<entry><id>tag:example.test,2026:item-1</id>
<title>Atom item</title><link rel="alternate" href="https://example.test/atom-1"/>
<updated>2026-02-04T12:00:00Z</updated><author><name>Bob</name></author>
<summary type="html">&lt;p&gt;Atom &lt;b&gt;summary&lt;/b&gt;&lt;/p&gt;</summary>
<content type="html">&lt;p&gt;Atom body&lt;/p&gt;
&lt;script&gt;bad()&lt;/script&gt;</content>
</entry></feed>"""

KEV = {
    "title": "CISA KEV Catalog",
    "catalogVersion": "2026.02.01",
    "dateReleased": "2026-02-01",
    "count": 1,
    "vulnerabilities": [
        {
            "cveID": "CVE-2026-1234",
            "vendorProject": "Example",
            "product": "Gateway",
            "vulnerabilityName": "Example auth bypass",
            "dateAdded": "2026-01-31",
            "shortDescription": "An authentication bypass.",
            "requiredAction": "Apply the vendor update.",
            "dueDate": "2026-02-21",
            "knownRansomwareCampaignUse": "Unknown",
            "notes": "Public advisory.",
            "cwes": ["CWE-287"],
        }
    ],
}


def source(
    name: str = "Example",
    source_type: str = "rss",
    url: str = "https://example.test/feed",
    category: str = "news",
    **overrides: object,
) -> SourceConfig:
    values: dict[str, object] = {
        "name": name,
        "type": source_type,
        "url": url,
        "category": category,
        "timeout_seconds": 1,
        "max_response_bytes": 10_000,
    }
    values.update(overrides)
    return SourceConfig.model_validate(values)


def artifact(source_config: SourceConfig, body: bytes) -> RawArtifactMetadata:
    from hashlib import sha256
    from uuid import uuid5

    digest = sha256(body).hexdigest()
    return RawArtifactMetadata(
        raw_artifact_id=uuid5(UUID("00000000-0000-0000-0000-000000000010"), digest),
        source_id=source_config.source_id,
        retrieval_url=source_config.url,
        canonical_url=source_config.url,
        retrieved_at=datetime(2026, 2, 5, tzinfo=UTC),
        response_status=200,
        content_type="application/xml",
        encoding="utf-8",
        content_hash=digest,
        byte_length=len(body),
        ingestion_run_id=UUID("00000000-0000-0000-0000-000000000011"),
    )


def response_fetch(
    source_config: SourceConfig, body: bytes, content_type: str = "application/xml"
) -> tuple[httpx.Response, RawArtifactMetadata]:
    response = httpx.Response(
        200,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("GET", str(source_config.url)),
    )
    raw = artifact(source_config, body)
    return response, raw


def test_rss_normalization_preserves_provenance_and_sanitizes_html() -> None:
    configured = source()
    response, raw = response_fetch(configured, RSS)
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )
    documents = normalize_feed(configured, fetch, raw)

    assert [document.external_source_id for document in documents] == [
        "item-2",
        "item-1",
    ]
    assert documents[0].content_type == "application/xml"
    assert documents[0].raw_artifact_id == raw.raw_artifact_id
    assert "Visible content." in documents[0].normalized_text
    assert "bad()" not in documents[0].normalized_text
    assert documents[0].language == "en-US"


def test_atom_normalization_supports_namespaces_and_optional_fields() -> None:
    configured = source(source_type="atom")
    response, raw = response_fetch(configured, ATOM)
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    documents = normalize_feed(configured, fetch, raw)

    assert len(documents) == 1
    assert documents[0].authors == ("Bob",)
    assert documents[0].language == "en"
    assert documents[0].published_at is None
    assert documents[0].updated_at_source == datetime(2026, 2, 4, 12, tzinfo=UTC)
    assert "Atom body" in documents[0].normalized_text


def test_malformed_xml_is_classified() -> None:
    configured = source()
    response, raw = response_fetch(configured, b"<rss><channel><item>")
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    with pytest.raises(NormalizationError, match="could not be parsed"):
        normalize_feed(configured, fetch, raw)


def test_nvd_normalization_produces_one_document_per_cve() -> None:
    configured = source(
        name="NIST National Vulnerability Database (NVD)",
        source_type="json",
        url="https://example.test/nvd.json",
        category="vulnerabilities",
    )
    body = json.dumps(
        {
            "format": "NVD_CVE",
            "vulnerabilities": [
                {
                    "cve": {
                        "id": "CVE-2026-1234",
                        "published": "2026-02-01T12:00:00.000",
                        "lastModified": "2026-02-02T12:00:00.000",
                        "descriptions": [
                            {"lang": "en", "value": "An NVD test vulnerability."}
                        ],
                        "references": [{"url": "https://example.test/advisory"}],
                    }
                }
            ],
        }
    ).encode()
    response, raw = response_fetch(configured, body, "application/json")
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    documents = normalize_json(configured, fetch, raw)

    assert len(documents) == 1
    assert documents[0].external_source_id == "CVE-2026-1234"
    assert (
        str(documents[0].canonical_url)
        == "https://nvd.nist.gov/vuln/detail/CVE-2026-1234"
    )
    assert "An NVD test vulnerability." in documents[0].normalized_text


def test_kev_normalization_produces_complete_documents() -> None:
    configured = source(
        name="CISA Known Exploited Vulnerabilities",
        source_type="json",
        url="https://www.cisa.gov/kev.json",
        category="vulnerabilities",
    )
    body = json.dumps(KEV).encode()
    response, raw = response_fetch(configured, body, "application/json")
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    documents = normalize_kev(configured, fetch, raw)

    assert len(documents) == 1
    document = documents[0]
    assert document.external_source_id == "CVE-2026-1234"
    assert document.document_type.value == "advisory"
    assert document.content_type == "application/json"
    assert "Required action: Apply the vendor update." in document.normalized_text
    assert document.sanitized_summary == "An authentication bypass."


def test_changed_kev_schema_fails_closed() -> None:
    configured = source(source_type="json")
    body = b'{"entries": []}'
    response, raw = response_fetch(configured, body, "application/json")
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    with pytest.raises(NormalizationError, match="vulnerabilities array"):
        normalize_kev(configured, fetch, raw)


def test_duplicates_are_deduplicated_but_changed_content_is_a_new_version() -> None:
    configured = source()
    body = b"""<rss><channel>
    <item><guid>same</guid><title>Same</title><link>https://example.test/a</link>
    <description>One</description></item>
    <item><guid>same</guid><title>Same</title><link>https://example.test/a</link>
    <description>One</description></item>
    <item><guid>changed</guid><title>Changed</title><link>https://example.test/a</link>
    <description>Two</description></item>
    </channel></rss>"""
    response, raw = response_fetch(configured, body)
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )

    documents = normalize_feed(configured, fetch, raw)

    assert len(documents) == 2
    assert {document.normalized_content_hash for document in documents}.__len__() == 2


def test_http_client_decompresses_bounded_gzip_archives() -> None:
    payload = b"x" * 100
    compressed = gzip.compress(payload)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/gzip"},
            content=compressed,
            request=request,
        )

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        client.fetch(
            "https://example.test/feed.json.gz",
            request=SourceRequest(expected_content_types=("application/gzip",)),
            max_response_bytes=200,
        )
    )
    assert result.body == payload

    with pytest.raises(FetchError, match="decompressed response exceeds"):
        asyncio.run(
            client.fetch(
                "https://example.test/feed.json.gz",
                request=SourceRequest(expected_content_types=("application/gzip",)),
                max_response_bytes=len(compressed),
            )
        )


def test_http_client_retries_rate_limit_and_respects_retry_after() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"retry-after": "0"},
                request=request,
            )
        return httpx.Response(200, content=b"ok", request=request)

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=2, retry_jitter_seconds=0),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    result = asyncio.run(
        client.fetch("https://example.test/feed", max_response_bytes=10)
    )
    assert result.body == b"ok"
    assert result.retry_count == 1
    assert attempts == 2
    assert sleeps == [0]


def test_http_client_rejects_oversized_responses_before_processing() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-length": "100"},
            content=b"x" * 100,
            request=request,
        )

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(FetchError, match="exceeds"):
        asyncio.run(client.fetch("https://example.test/feed", max_response_bytes=10))


@pytest.mark.parametrize(
    ("exception", "classification"),
    [
        (httpx.ReadTimeout("timed out"), "timeout"),
        (httpx.ConnectError("connection failed"), "connection_error"),
        (httpx.ConnectError("certificate verify failed"), "tls_error"),
    ],
)
def test_http_client_classifies_network_failures(
    exception: Exception, classification: str
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise exception

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(FetchError) as raised:
        asyncio.run(client.fetch("https://example.test/feed", max_response_bytes=10))
    assert raised.value.classification == classification


def test_ingestion_continues_after_one_source_fails_and_emits_manifest() -> None:
    good = source(name="Good", url="https://example.test/good")
    bad = source(name="Bad", url="https://example.test/bad")
    registry = SourceRegistry(sources=(good, bad))

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bad":
            raise httpx.ConnectError("offline")
        return httpx.Response(
            200,
            headers={"content-type": "application/rss+xml"},
            content=RSS,
            request=request,
        )

    service = IngestionService(
        Settings(database_required=False, max_concurrency=2, http_max_retries=0),
        http_client=AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(handler),
        ),
    )
    collection = asyncio.run(service.collect_once(registry))

    assert collection.manifest.status is RunStatus.FAILED
    assert collection.manifest.failed_sources == 1
    assert collection.manifest.successful_sources == 1
    assert len(collection.source_documents) == 2
    assert collection.manifest.source_results[0].source_id == "bad"
    assert (
        collection.manifest.source_results[0].error_classification == "connection_error"
    )
    assert len(collection.raw_artifacts) == 1


def test_abusech_key_is_injected_for_abusech_sources() -> None:
    configured = source(
        name="ThreatFox Recent Indicators (Abuse.ch)",
        source_type="json",
        url="https://threatfox-api.abuse.ch/api/v1/",
        category="tactical_iocs",
        request={
            "method": "POST",
            "body": {"query": "get_iocs", "days": 7},
            "body_encoding": "json",
        },
    )
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"data": []},
            request=request,
        )

    service = IngestionService(
        Settings(
            database_required=False,
            http_max_retries=0,
            abusech_api_key=SecretStr("fixture-abusech-key"),
        ),
        http_client=AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(handler),
        ),
    )
    collection = asyncio.run(
        service.collect_once(SourceRegistry(sources=(configured,)))
    )

    assert collection.manifest.status is RunStatus.COMPLETED
    assert seen[0].headers["auth-key"] == "fixture-abusech-key"


def test_conditional_requests_use_etag_and_return_not_modified() -> None:
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                200,
                headers={"etag": '"v1"', "content-type": "application/rss+xml"},
                content=RSS,
                request=request,
            )
        assert request.headers["if-none-match"] == '"v1"'
        return httpx.Response(304, headers={"etag": '"v1"'}, request=request)

    configured = source()
    service = IngestionService(
        Settings(database_required=False, http_max_retries=0),
        http_client=AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(handler),
        ),
    )
    registry = SourceRegistry(sources=(configured,))
    first = asyncio.run(service.collect_once(registry))
    second = asyncio.run(service.collect_once(registry))

    assert first.manifest.source_results[0].cache_state.value == "miss"
    assert second.manifest.source_results[0].cache_state.value == "not_modified"
    assert second.manifest.source_results[0].item_count == 0


def test_redirects_are_followed_and_redirect_limit_is_bounded() -> None:
    async def final_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"}, request=request)
        return httpx.Response(200, content=b"done", request=request)

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0, max_redirects=2),
        transport=httpx.MockTransport(final_handler),
    )
    result = asyncio.run(
        client.fetch("https://example.test/start", max_response_bytes=10)
    )
    assert result.body == b"done"
    assert result.url.endswith("/final")

    async def loop_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": str(request.url)},
            request=request,
        )

    limited = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0, max_redirects=2),
        transport=httpx.MockTransport(loop_handler),
    )
    with pytest.raises(FetchError, match="redirect limit"):
        asyncio.run(limited.fetch("https://example.test/loop", max_response_bytes=10))


def test_non_utf8_xml_uses_declared_encoding() -> None:
    configured = source()
    body = (
        b'<?xml version="1.0" encoding="iso-8859-1"?>'
        b"<rss><channel><item><title>Caf\xe9</title>"
        b"<link>https://example.test/cafe</link></item></channel></rss>"
    )
    response, raw = response_fetch(
        configured,
        body,
        "application/rss+xml; charset=iso-8859-1",
    )
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(str(configured.url), max_response_bytes=10_000)
    )
    documents = normalize_feed(configured, fetch, raw)
    assert documents[0].title == "Café"


def test_source_request_contract_defaults_and_post_shape() -> None:
    configured = source(
        source_type="json",
        request={
            "method": "POST",
            "url_params": {"page": "1"},
            "headers": {"Accept": "application/json", "X-Trace": "fixture"},
            "body": {"query": "recent", "limit": 10},
            "body_encoding": "json",
            "retry_policy": {"max_retries": 1, "jitter_seconds": 0},
        },
    )
    assert configured.request.method is HTTPMethod.POST
    assert configured.request.parser_adapter is ParserAdapter.JSON
    assert configured.request.expected_content_types == (
        "application/json",
        "application/*+json",
    )
    assert configured.request.retry_policy.max_retries == 1
    assert configured.request.url_params == (("page", "1"),)


def test_source_request_rejects_invalid_policy_and_secret_configuration() -> None:
    with pytest.raises(ValueError):
        SourceRequest(expected_content_types=("not-a-media-type",))
    with pytest.raises(ValueError):
        SourceRequest(method="GET", body="query", body_encoding=BodyEncoding.TEXT)


def test_http_client_builds_post_request_from_contract_without_logging_secrets() -> (
    None
):
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json; charset=utf-8"},
            content=b"{}",
            request=request,
        )

    configured = SourceRequest(
        method=HTTPMethod.POST,
        url_params={"page": "1"},
        headers={"Accept": "application/json", "X-Fixture": "safe"},
        body={"query": "recent", "limit": 10},
        body_encoding=BodyEncoding.JSON,
        expected_content_types=("application/json",),
        parser_adapter=ParserAdapter.JSON,
        retry_policy={"max_retries": 0},
    )
    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=0),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = asyncio.run(
            client.fetch("https://example.test/search", request=configured)
        )
    finally:
        asyncio.run(client.aclose())

    assert result.body == b"{}"
    assert seen[0].method == "POST"
    assert str(seen[0].url) == "https://example.test/search?page=1"
    assert seen[0].headers["accept"] == "application/json"
    assert seen[0].headers["content-type"] == "application/json"
    assert seen[0].content == b'{"limit":10,"query":"recent"}'


def test_http_client_content_type_policy_is_non_retryable() -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/plain"},
            content=b"not json",
            request=request,
        )

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=3),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(FetchError) as raised:
        asyncio.run(
            client.fetch(
                "https://example.test/api",
                request=SourceRequest(expected_content_types=("application/json",)),
            )
        )
    asyncio.run(client.aclose())
    assert raised.value.classification == "content_type_error"
    assert raised.value.retry_count == 0
    assert attempts == 1


def test_http_client_retries_connection_errors_with_source_budget() -> None:
    attempts = 0
    sleeps: list[float] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"{}",
            request=request,
        )

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    client = AsyncHTTPClient(
        HTTPClientConfig(max_retries=3),
        transport=httpx.MockTransport(handler),
        sleep=sleep,
    )
    result = asyncio.run(
        client.fetch(
            "https://example.test/api",
            request=SourceRequest(
                expected_content_types=("application/json",),
                retry_policy={
                    "max_retries": 1,
                    "backoff_seconds": 0,
                    "jitter_seconds": 0,
                },
            ),
        )
    )
    asyncio.run(client.aclose())
    assert result.retry_count == 1
    assert attempts == 2
    assert sleeps == [0]


def test_html_and_pdf_adapter_fixtures_are_provenance_linked() -> None:
    html_source = source(
        name="HTML fixture", source_type="html", url="https://example.test/advisory"
    )
    html_body = (
        b"<html><head><title>Fixture Advisory</title></head><body>"
        b"<article><p>Visible advisory text.</p><script>secret()</script>"
        b"</article></body></html>"
    )
    html_fetch, html_artifact = response_fetch(html_source, html_body, "text/html")
    html_result = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: html_fetch),
        ).fetch(str(html_source.url), request=html_source.request)
    )
    html_documents = normalize_html(html_source, html_result, html_artifact)
    assert html_documents[0].title == "Fixture Advisory"
    assert "Visible advisory text." in html_documents[0].normalized_text
    assert "secret()" not in html_documents[0].normalized_text

    pdf_source = source(
        name="PDF fixture", source_type="pdf", url="https://example.test/advisory.pdf"
    )
    pdf_body = b"%PDF-1.4\nBT\n/F1 12 Tf\n(Fixture PDF advisory) Tj\nET\n%%EOF"
    pdf_fetch, pdf_artifact = response_fetch(pdf_source, pdf_body, "application/pdf")
    pdf_result = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: pdf_fetch),
        ).fetch(str(pdf_source.url), request=pdf_source.request)
    )
    pdf_documents = normalize_pdf(pdf_source, pdf_result, pdf_artifact)
    assert "Fixture PDF advisory" in pdf_documents[0].normalized_text
