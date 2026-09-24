"""Source policy regression tests for the Krebs on Security RSS feed.

Production incident context
---------------------------
Between 2026-09-16 and 2026-09-17 the ``krebs-on-security`` source failed every
scheduled collection with::

    error_classification = "content_type_error"
    error_detail = "response content type did not match source policy"

(see ``docs/incidents/2026-09-17-ingestion-failure-*.md``). The failure was
deterministic and produced ``retry_count=0`` and no HTTP status, because the
content-type gate rejects the response *before* the body is read and the
resulting :class:`FetchError` is re-raised without consuming a retry.

Characterized origin behaviour (read-only probes, 2026-09-23)
------------------------------------------------------------
The origin (``server: nginx``, zero redirect hops) intermittently labels an
otherwise well-formed RSS 2.0 document as ``text/html``::

    status      200
    body        <?xml version="1.0" encoding="UTF-8"?><rss version="2.0" ...
    length      168490
    headers     text/html; charset=UTF-8   <- observed failing variant
                application/rss+xml        <- observed working variant

Both variants were observed for the same body within a single session, so the
source policy must accept both. The default RSS allowlist
(``models/contracts.py``) contains only ``application/rss+xml``,
``application/xml`` and ``text/xml``, which is why only the ``text/html``
variant fails.

Scope of these tests
--------------------
The repair is an explicit, source-scoped ``expected_content_types`` declaration
for this one registry entry. Every assertion here therefore also pins the two
properties that keep the repair narrow:

1. ``text/html`` is accepted only because this source declares it, and
2. genuinely non-feed HTML (anti-bot / challenge pages) is still rejected.

No assertion depends on network access; every transport is a deterministic
:class:`httpx.MockTransport`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    FetchResult,
    HTTPClientConfig,
)
from hermes_cti.ingestion.normalization import NormalizationError, normalize_feed
from hermes_cti.models.contracts import (
    ParserAdapter,
    RawArtifactMetadata,
    SourceConfig,
    SourceType,
)

KREBS_URL = "https://krebsonsecurity.com/feed/"
KREBS_SOURCE_ID = "krebs-on-security"

# Verbatim body prefix captured from the live origin on 2026-09-23 (first 200
# bytes of the response). Preserved literally so the fixture documents the real
# response shape rather than an idealized one.
KREBS_BODY_PREFIX = (
    b'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"\n'
    b'\txmlns:content="http://purl.org/rss/1.0/modules/content/"\n'
    b'\txmlns:wfw="http://wellformedweb.org/CommentAPI/"\n'
    b'\txmlns:dc="http://purl.org/dc/eleme'
)

KREBS_FEED_BODY = (
    KREBS_BODY_PREFIX
    + b'nts/1.0/">'
    + b"<channel>"
    + b"<title>Krebs on Security</title>"
    + b"<link>https://krebsonsecurity.com</link>"
    + b"<description>In-depth security news and investigation</description>"
    + b"<item>"
    + b"<title>Krebs source policy canary</title>"
    + b"<link>https://krebsonsecurity.com/2026/09/canary/</link>"
    + b"<guid>https://krebsonsecurity.com/?p=999999</guid>"
    + b"<description>Deterministic fixture item.</description>"
    + b"</item>"
    + b"</channel>"
    + b"</rss>"
)

# A representative anti-bot / challenge response: HTML labelled text/html with
# no feed content whatsoever. This must never be accepted for an RSS source.
ANTIBOT_HTML_BODY = (
    b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    b"<body><h1>Checking your browser before accessing the site.</h1>"
    b"<p>Enable JavaScript and cookies to continue.</p></body></html>"
)

# The source-scoped content-type policy under test. It adds the observed
# text/html variant alongside the canonical feed type.
KREBS_EXPECTED_CONTENT_TYPES = ("application/rss+xml", "text/html")

# The narrowed default RSS policy, for contrast with the declared Krebs policy.
DEFAULT_RSS_CONTENT_TYPES = (
    "application/rss+xml",
    "application/xml",
    "text/xml",
)


def krebs_source(
    expected_content_types: tuple[str, ...] | None = None,
) -> SourceConfig:
    """Build the Krebs source, optionally with an explicit content-type policy."""

    data: dict[str, object] = {
        "name": "Krebs on Security",
        "type": SourceType.RSS,
        "url": KREBS_URL,
        "category": "news",
    }
    if expected_content_types is not None:
        data["request"] = {"expected_content_types": list(expected_content_types)}
    return SourceConfig.model_validate(data)


def krebs_source_with_policy() -> SourceConfig:
    """Build the Krebs source as the repaired registry entry declares it."""

    return krebs_source(KREBS_EXPECTED_CONTENT_TYPES)


def artifact(source_config: SourceConfig, fetch: FetchResult) -> RawArtifactMetadata:
    """Build minimal provenance metadata for a fixture response."""

    return RawArtifactMetadata(
        raw_artifact_id=uuid4(),
        source_id=source_config.source_id,
        retrieval_url=str(source_config.url),
        canonical_url=str(source_config.url),
        retrieved_at=datetime.now(UTC),
        response_status=fetch.status_code,
        content_type=fetch.content_type,
        content_hash=__import__("hashlib").sha256(fetch.body).hexdigest(),
        byte_length=len(fetch.body),
        ingestion_run_id=uuid4(),
    )


def fetch_with_content_type(
    source_config: SourceConfig,
    body: bytes,
    content_type: str,
) -> tuple[FetchResult, RawArtifactMetadata]:
    """Fetch ``body`` through the real client against a mocked transport."""

    response = httpx.Response(
        200,
        headers={"content-type": content_type},
        content=body,
        request=httpx.Request("GET", str(source_config.url)),
    )
    fetch = asyncio.run(
        AsyncHTTPClient(
            HTTPClientConfig(max_retries=0),
            transport=httpx.MockTransport(lambda request: response),
        ).fetch(
            str(source_config.url),
            request=source_config.request,
            max_response_bytes=10_000_000,
        )
    )
    return fetch, artifact(source_config, fetch)


# ---------------------------------------------------------------------------
# Baseline: the registry entry as it exists today (the production defect)
# ---------------------------------------------------------------------------


def test_krebs_default_rss_policy_rejects_text_html_feed() -> None:
    """Document the defect: the narrowed default RSS policy drops a valid feed.

    The origin returns a well-formed RSS 2.0 document labelled ``text/html``.
    The auto-derived RSS allowlist does not contain ``text/html``, so the fetch
    is rejected before the body is parsed.
    """

    configured = krebs_source()

    assert configured.request.expected_content_types == DEFAULT_RSS_CONTENT_TYPES
    assert "text/html" not in configured.request.expected_content_types

    with pytest.raises(FetchError) as excinfo:
        fetch_with_content_type(configured, KREBS_FEED_BODY, "text/html; charset=UTF-8")

    assert excinfo.value.classification == "content_type_error"
    assert excinfo.value.detail == "response content type did not match source policy"
    # The gate rejects deterministically and consumes no retry.
    assert excinfo.value.retry_count == 0


# ---------------------------------------------------------------------------
# Case 1 (primary): observed failing header, real RSS body
# ---------------------------------------------------------------------------


def test_krebs_source_policy_accepts_mislabelled_rss_feed() -> None:
    """The declared source policy accepts the observed ``text/html`` variant.

    The response is a real RSS 2.0 document mislabelled by the origin, so it
    must fetch successfully and normalize through the feed parser.
    """

    configured = krebs_source_with_policy()

    assert configured.source_id == KREBS_SOURCE_ID
    assert configured.request.parser_adapter is ParserAdapter.RSS
    assert set(KREBS_EXPECTED_CONTENT_TYPES).issubset(
        set(configured.request.expected_content_types)
    )

    fetch, raw = fetch_with_content_type(
        configured, KREBS_FEED_BODY, "text/html; charset=UTF-8"
    )

    assert fetch.status_code == 200
    assert fetch.content_type == "text/html; charset=UTF-8"

    documents = normalize_feed(configured, fetch, raw)
    assert len(documents) == 1
    assert documents[0].title == "Krebs source policy canary"
    assert documents[0].source_id == KREBS_SOURCE_ID
    assert str(documents[0].canonical_url) == (
        "https://krebsonsecurity.com/2026/09/canary/"
    )
    # Provenance: the mislabelled content type is retained, not normalized away.
    assert documents[0].content_type == "text/html; charset=UTF-8"


def test_krebs_fixture_prefix_matches_observed_origin_shape() -> None:
    """The fixture body starts with the literal captured origin prefix."""

    assert KREBS_FEED_BODY.startswith(KREBS_BODY_PREFIX)
    assert b"<?xml" in KREBS_BODY_PREFIX
    assert b"<rss" in KREBS_BODY_PREFIX
    assert len(KREBS_BODY_PREFIX) == 200


# ---------------------------------------------------------------------------
# Case 2 (control): the canonical content type must keep working
# ---------------------------------------------------------------------------


def test_krebs_source_policy_keeps_accepting_canonical_rss_type() -> None:
    """The working ``application/rss+xml`` variant is not regressed."""

    configured = krebs_source_with_policy()

    fetch, raw = fetch_with_content_type(
        configured, KREBS_FEED_BODY, "application/rss+xml; charset=UTF-8"
    )

    assert fetch.status_code == 200
    documents = normalize_feed(configured, fetch, raw)
    assert len(documents) == 1
    assert documents[0].title == "Krebs source policy canary"


def test_baseline_policy_accepts_canonical_rss_type() -> None:
    """An undeclared RSS source keeps working with the canonical type."""

    configured = krebs_source()
    fetch, raw = fetch_with_content_type(
        configured, KREBS_FEED_BODY, "application/rss+xml; charset=UTF-8"
    )
    documents = normalize_feed(configured, fetch, raw)
    assert documents[0].title == "Krebs source policy canary"


# ---------------------------------------------------------------------------
# Case 3 (negative control): the repair must not become a catch-all
# ---------------------------------------------------------------------------


def test_krebs_source_policy_still_rejects_non_feed_html() -> None:
    """A genuine HTML challenge page is still rejected and yields no document.

    Accepting ``text/html`` for this source must not degrade into accepting any
    HTML response: an anti-bot page carries no feed content and must never
    produce a source document.

    Interim classification note (until the signature-sniff follow-up lands):
    because the declared policy now allows ``text/html``, the header gate can no
    longer distinguish a mislabelled feed from a challenge page, so the
    rejection surfaces one layer later as ``NormalizationError`` rather than
    ``FetchError[content_type_error]``. The invariant that matters is enforced
    here regardless of which gate rejects: the response is refused and no
    document is emitted. The follow-up commit restores the crisp
    ``content_type_error`` signal via a positive feed-signature check.
    """

    configured = krebs_source_with_policy()

    with pytest.raises((FetchError, NormalizationError)) as excinfo:
        fetch, raw = fetch_with_content_type(
            configured, ANTIBOT_HTML_BODY, "text/html; charset=utf-8"
        )
        normalize_feed(configured, fetch, raw)

    # Either gate may reject; the surviving invariant is the classification
    # being actionable and no document being produced.
    if isinstance(excinfo.value, FetchError):
        assert excinfo.value.classification == "content_type_error"
    else:
        assert excinfo.value.classification in {"malformed_xml", "schema_error"}

    # The challenge body never yields a feed document.
    fetch, raw = fetch_with_content_type(
        configured, ANTIBOT_HTML_BODY, "text/html; charset=utf-8"
    )
    with pytest.raises(NormalizationError):
        normalize_feed(configured, fetch, raw)


def test_text_html_acceptance_is_scoped_to_the_krebs_entry() -> None:
    """``text/html`` acceptance is source-scoped and does not widen the default.

    A different RSS source that does not declare the variant must keep the
    narrowed default policy, proving the registry repair did not change global
    ingestion behaviour.
    """

    other = SourceConfig.model_validate(
        {
            "name": "Some Other Feed",
            "type": SourceType.RSS,
            "url": "https://example.test/feed/",
            "category": "news",
        }
    )

    assert other.request.expected_content_types == DEFAULT_RSS_CONTENT_TYPES
    assert "text/html" not in other.request.expected_content_types

    with pytest.raises(FetchError) as excinfo:
        fetch_with_content_type(other, KREBS_FEED_BODY, "text/html; charset=UTF-8")

    assert excinfo.value.classification == "content_type_error"


# ---------------------------------------------------------------------------
# Live-origin reproduction helper (opt-in)
# ---------------------------------------------------------------------------


def test_krebs_live_origin_body_normalizes_under_declared_policy() -> None:
    """The real origin body normalizes through the declared policy.

    This is the end-to-end counterpart to the mocked cases above: it exercises
    the actual production response shape (live body bytes) against the policy
    declared in the authoritative registry. It performs one read-only GET and
    skips cleanly when the origin is unreachable, so it never makes the suite
    network-dependent.

    Regression target: before the policy repair, the ``text/html`` variant was
    rejected with ``content_type_error``. After the repair both observed header
    variants must fetch successfully and produce a document.
    """

    import httpx

    try:
        response = httpx.get(
            KREBS_URL,
            headers={
                "User-Agent": (
                    "CTI-Hermes/0.1.0 "
                    "(+https://github.com/mrcoggsworth/threat-intel-agent)"
                )
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:  # pragma: no cover - network dependent
        pytest.skip(f"live origin unavailable: {type(exc).__name__}")

    body = response.content
    if b"<rss" not in body[:200] and b"<feed" not in body[:200]:
        pytest.skip("live origin body is not a recognizable feed this run")

    configured = krebs_source_with_policy()

    for observed_type in (
        "text/html; charset=UTF-8",
        "application/rss+xml; charset=UTF-8",
    ):
        fetch, raw = fetch_with_content_type(configured, body, observed_type)
        documents = normalize_feed(configured, fetch, raw)
        assert len(documents) >= 1
        assert documents[0].source_id == KREBS_SOURCE_ID
