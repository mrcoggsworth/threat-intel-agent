"""Offline Phase 2 ingestion and normalization tests."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from hermes_cti.core.settings import Settings
from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    HTTPClientConfig,
)
from hermes_cti.ingestion.normalization import (
    NormalizationError,
    normalize_feed,
    normalize_kev,
)
from hermes_cti.ingestion.service import IngestionService
from hermes_cti.models.contracts import (
    RawArtifactMetadata,
    RunStatus,
    SourceConfig,
    SourceRegistry,
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
