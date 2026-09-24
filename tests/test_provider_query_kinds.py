"""RED tests for provider query-kind selection and honest failure classification.

Context
-------
``EnrichmentService.enrich`` dispatched every configured provider for every
request regardless of what the request asked for, and providers had no way to
declare what they can serve. A CVE enrichment request therefore reached three
indicator-only providers that rejected it at runtime:

    VirusTotalProvider._kinds  {ipv4, ipv6, domain, url, md5, sha1, sha256}
    OTXProvider._kinds         {ipv4, ipv6, domain, url, md5, sha1, sha256}
    AbuseIPDBProvider          {ipv4, ipv6}

A 489-CVE enrichment run produced 978 such rejections (489 x 2 for the two
indicator sets, plus AbuseIPDB) recorded as ``schema_drift``, which is
misleading: the rejection happens in a guard *before* any HTTP request, so no
payload ever drifted and no provider quota was consumed.

These tests pin three behaviours:
1. Providers declare the query kinds they can serve.
2. The service dispatches only applicable providers, recording the rest.
3. A kind rejection is classified as ``invalid_request``, while a genuine
   payload-shape mismatch stays ``schema_drift``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from hermes_cti.enrichment.providers import (
    AbuseIPDBProvider,
    BaseProvider,
    CISAKEVProvider,
    EnrichmentProvider,
    EPSSProvider,
    NVDProvider,
    OTXProvider,
    ProviderQueryKindError,
    ProviderSchemaError,
    VirusTotalProvider,
)
from hermes_cti.enrichment.service import EnrichmentService
from hermes_cti.models.contracts import (
    EnrichmentRunResult,
    EnrichmentStatus,
    EntityReference,
    EntityType,
    ProviderErrorClassification,
    ProviderRequest,
    ProviderResponse,
)

INDICATOR_KINDS = frozenset({"ipv4", "ipv6", "domain", "url", "md5", "sha1", "sha256"})


def cve_request(cve: str = "CVE-2026-76460") -> ProviderRequest:
    return ProviderRequest(
        entity=EntityReference(
            entity_type=EntityType.VULNERABILITY,
            entity_id=uuid5(NAMESPACE_URL, f"vuln:{cve}"),
        ),
        query_key=cve,
        query_kind="cve",
        requested_at=datetime.now(UTC),
    )


def indicator_request(
    kind: str = "ipv4", value: str = "203.0.113.9"
) -> ProviderRequest:
    return ProviderRequest(
        entity=EntityReference(
            entity_type=EntityType.INDICATOR,
            entity_id=uuid5(NAMESPACE_URL, f"ind:{value}"),
        ),
        query_key=value,
        query_kind=kind,
        requested_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# 1. Capability declaration
# ---------------------------------------------------------------------------


def test_cve_providers_declare_the_cve_query_kind() -> None:
    """KEV, EPSS and NVD serve CVE queries and say so."""

    for cls, url in (
        (CISAKEVProvider, "https://example.test/kev.json"),
        (EPSSProvider, "https://example.test/epss"),
        (NVDProvider, "https://example.test/nvd"),
    ):
        provider = cls(url)
        assert "cve" in provider.query_kinds, f"{cls.__name__} must serve cve"


def test_indicator_providers_declare_indicator_kinds_only() -> None:
    """Indicator providers must not claim to serve CVE queries."""

    for cls, url in (
        (VirusTotalProvider, "https://example.test/vt"),
        (OTXProvider, "https://example.test/otx"),
    ):
        provider = cls(url)
        assert provider.query_kinds == INDICATOR_KINDS
        assert "cve" not in provider.query_kinds, f"{cls.__name__} must not serve cve"

    abuse = AbuseIPDBProvider("https://example.test/abuseipdb")
    assert abuse.query_kinds == frozenset({"ipv4", "ipv6"})
    assert "cve" not in abuse.query_kinds


def test_base_provider_exposes_query_kinds() -> None:
    """The capability is part of the provider contract, not per-subclass trivia."""

    provider = BaseProvider("base")
    assert isinstance(provider.query_kinds, frozenset)
    assert "cve" in provider.query_kinds
    # Declared on the Protocol so the service can filter without duck-typing.
    assert "query_kinds" in EnrichmentProvider.__annotations__


def test_query_kind_error_is_distinct_from_schema_drift() -> None:
    """A kind rejection has its own error type so it cannot masquerade as drift."""

    assert issubclass(ProviderQueryKindError, ValueError)


# ---------------------------------------------------------------------------
# 2. Dispatch filtering
# ---------------------------------------------------------------------------


class RecordingProvider:
    """Minimal provider that records the requests it is asked to serve."""

    def __init__(self, name: str, query_kinds: frozenset[str], enabled=True):
        self.name = name
        self.query_kinds = query_kinds
        self.enabled = enabled
        self.requests: list[ProviderRequest] = []

    async def enrich(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            provider=self.name,
            request=request,
            retrieved_at=request.requested_at,
            status=EnrichmentStatus.SUCCESS,
            retryable=False,
            normalized_result={f"{self.name}_seen": True},
        )

    def health(self, now=None):  # pragma: no cover - unused in these tests
        return None

    async def aclose(self) -> None:
        return None


def test_service_dispatches_only_applicable_providers() -> None:
    """A CVE request must not reach indicator-only providers."""

    cve_provider = RecordingProvider("cve_one", frozenset({"cve"}))
    ioc_provider = RecordingProvider("ioc_one", INDICATOR_KINDS)
    service = EnrichmentService((cve_provider, ioc_provider))

    result = asyncio.run(service.enrich(cve_request()))

    assert isinstance(result, EnrichmentRunResult)
    assert len(cve_provider.requests) == 1
    assert ioc_provider.requests == [], "indicator provider was dispatched for a CVE"


def test_service_dispatches_only_applicable_providers_for_indicators() -> None:
    """An IPv4 request must not reach CVE-only providers."""

    cve_provider = RecordingProvider("cve_one", frozenset({"cve"}))
    ioc_provider = RecordingProvider("ioc_one", INDICATOR_KINDS)
    service = EnrichmentService((cve_provider, ioc_provider))

    asyncio.run(service.enrich(indicator_request("ipv4")))

    assert len(ioc_provider.requests) == 1
    assert cve_provider.requests == [], "cve provider was dispatched for an indicator"


def test_service_records_skipped_providers() -> None:
    """Skipping is reported, never silent: the caller sees what did not run."""

    cve_provider = RecordingProvider("cve_one", frozenset({"cve"}))
    ioc_provider = RecordingProvider("ioc_one", INDICATOR_KINDS)
    service = EnrichmentService((cve_provider, ioc_provider))

    result = asyncio.run(service.enrich(cve_request()))

    assert "ioc_one" in result.skipped_providers
    assert "cve_one" not in result.skipped_providers


def test_disabled_provider_is_still_skipped_by_kind() -> None:
    """A provider that cannot serve the kind is not dispatched even if enabled."""

    service = EnrichmentService(
        (RecordingProvider("ioc_one", INDICATOR_KINDS, enabled=True),)
    )
    result = asyncio.run(service.enrich(cve_request()))

    assert result.skipped_providers == ("ioc_one",)


def test_no_applicable_provider_yields_disabled_status() -> None:
    """With nothing applicable the run reports it honestly rather than empty success."""

    service = EnrichmentService((RecordingProvider("ioc_one", INDICATOR_KINDS),))
    result = asyncio.run(service.enrich(cve_request()))

    assert result.status is EnrichmentStatus.DISABLED
    assert result.provider_results == ()


# ---------------------------------------------------------------------------
# 3. Classification honesty
# ---------------------------------------------------------------------------


class KindGuardedProvider(BaseProvider):
    """Concrete BaseProvider whose kind guard rejects 'cve'."""

    def __init__(self) -> None:
        super().__init__("guarded", query_kinds=INDICATOR_KINDS)

    async def _retrieve(self, request):
        # Mirrors the real guards in VirusTotal/OTX/AbuseIPDB: reject an
        # unsupported kind before any HTTP request is made.
        if request.query_kind not in self.query_kinds:
            raise ProviderQueryKindError(
                f"provider does not serve query kind {request.query_kind!r}"
            )
        raise AssertionError("unexpected kind reached _retrieve")


def test_kind_rejection_classifies_as_invalid_request() -> None:
    """A kind rejection is an unsupported request, not schema drift."""

    provider = KindGuardedProvider()
    response = asyncio.run(provider.enrich(cve_request()))

    assert response.status is EnrichmentStatus.UNAVAILABLE
    assert response.error_classification is ProviderErrorClassification.INVALID_REQUEST
    assert response.error_classification is not ProviderErrorClassification.SCHEMA_DRIFT


class DriftingProvider(BaseProvider):
    """Concrete BaseProvider that raises on a payload of the wrong shape."""

    def __init__(self) -> None:
        super().__init__("drifting", query_kinds=frozenset({"cve"}))

    async def _retrieve(self, request):
        # Mirrors BaseProvider._fetch_json: valid JSON object, wrong shape for
        # this provider's contract -> ProviderSchemaError -> schema_drift.
        raise ProviderSchemaError("provider root must be an object")


def test_payload_shape_mismatch_still_classifies_as_schema_drift() -> None:
    """Real payload drift keeps its own classification."""

    provider = DriftingProvider()
    response = asyncio.run(provider.enrich(cve_request()))

    assert response.status is EnrichmentStatus.UNAVAILABLE
    assert response.error_classification is ProviderErrorClassification.SCHEMA_DRIFT
