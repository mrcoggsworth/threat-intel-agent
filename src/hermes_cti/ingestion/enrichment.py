"""OSINT telemetry enrichment clients.

Supports CISA KEV, FIRST EPSS, AbuseIPDB, and VirusTotal.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import httpx

from hermes_cti.models.contracts import (
    EnrichmentRunResult,
    EnrichmentStatus,
    EntityReference,
    EntityType,
    ProviderRequest,
)

if TYPE_CHECKING:
    from hermes_cti.enrichment.cache import EnrichmentCache
    from hermes_cti.enrichment.providers import (
        AbuseIPDBProvider,
        CISAKEVProvider,
        EnrichmentProvider,
        EPSSProvider,
        VirusTotalProvider,
    )


def _float_value(value: object, default: float = 0.0) -> float:
    """Convert a provider value to a float without trusting its shape."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
    return default


def _int_value(value: object, default: int = 0) -> int:
    """Convert a provider value to an integer without trusting its shape."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    return default


class KEVEnricher:
    """Convenience client for querying CISA Known Exploited Vulnerabilities."""

    def __init__(
        self,
        url: str = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        *,
        ttl_seconds: int = 43_200,  # 12 hours
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from hermes_cti.enrichment.cache import EnrichmentCache
        from hermes_cti.enrichment.providers import (
            CISAKEVProvider,
            ProviderRuntimeConfig,
        )

        self.url = url
        self._provider: CISAKEVProvider = CISAKEVProvider(
            url,
            config=ProviderRuntimeConfig(ttl_seconds=ttl_seconds),
            transport=transport,
        )
        self._cache: EnrichmentCache = EnrichmentCache()

    async def get_kev_details(self, cve_id: str) -> dict[str, Any] | None:
        """Lookup CVE in CISA KEV catalog."""
        req = ProviderRequest(
            entity=EntityReference(
                entity_type=EntityType.VULNERABILITY,
                entity_id=uuid4(),
            ),
            query_key=cve_id.strip().upper(),
            query_kind="cve",
            requested_at=datetime.now(UTC),
        )
        lookup = self._cache.get("cisa_kev", req.query_key, now=req.requested_at)
        if lookup.fresh and lookup.response:
            res = lookup.response
        else:
            res = await self._provider.enrich(req)
            if res.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}:
                self._cache.put(res)

        if res.status is EnrichmentStatus.SUCCESS and res.normalized_result.get(
            "matched"
        ):
            return res.normalized_result
        return None

    async def is_known_exploited(self, cve_id: str) -> bool:
        """Check if CVE is in CISA KEV catalog."""
        details = await self.get_kev_details(cve_id)
        return details is not None and bool(details.get("known_exploited"))

    async def aclose(self) -> None:
        await self._provider.aclose()


class EPSSEnricher:
    """Client for FIRST EPSS API with bulk querying capability."""

    def __init__(
        self,
        url: str = "https://api.first.org/data/v1/epss",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from hermes_cti.enrichment.cache import EnrichmentCache
        from hermes_cti.enrichment.providers import EPSSProvider

        self.url = url.rstrip("/")
        self._provider: EPSSProvider = EPSSProvider(url, transport=transport)
        self._cache: EnrichmentCache = EnrichmentCache()

    @staticmethod
    def _score_from_normalized(
        normalized: object,
    ) -> tuple[float, float] | None:
        if not isinstance(normalized, dict) or not normalized.get("found"):
            return None
        return (
            _float_value(normalized.get("epss_score")),
            _float_value(normalized.get("epss_percentile")),
        )

    async def get_epss_score(self, cve_id: str) -> tuple[float, float] | None:
        """Query EPSS score and percentile for a single CVE."""
        req = ProviderRequest(
            entity=EntityReference(
                entity_type=EntityType.VULNERABILITY,
                entity_id=uuid4(),
            ),
            query_key=cve_id.strip().upper(),
            query_kind="cve",
            requested_at=datetime.now(UTC),
        )
        lookup = self._cache.get("epss", req.query_key, now=req.requested_at)
        if lookup.fresh and lookup.response:
            res = lookup.response
        else:
            res = await self._provider.enrich(req)
            if res.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}:
                self._cache.put(res)

        if res.status is not EnrichmentStatus.SUCCESS:
            return None
        return self._score_from_normalized(res.normalized_result)

    async def get_epss_batch(
        self, cve_ids: Sequence[str]
    ) -> dict[str, tuple[float, float] | None]:
        """Query EPSS scores using one request for uncached CVEs."""
        requested = tuple(
            dict.fromkeys(cve.strip().upper() for cve in cve_ids if cve.strip())
        )
        batch_out: dict[str, tuple[float, float] | None] = {
            cve: None for cve in requested
        }
        pending: list[str] = []
        for cve in requested:
            lookup = self._cache.get("epss", cve)
            if lookup.fresh and lookup.response is not None:
                batch_out[cve] = self._score_from_normalized(
                    lookup.response.normalized_result
                )
            else:
                pending.append(cve)

        if not pending:
            return batch_out
        if len(pending) == 1:
            batch_out[pending[0]] = await self.get_epss_score(pending[0])
            return batch_out

        requested_at = datetime.now(UTC)
        request = ProviderRequest(
            entity=EntityReference(
                entity_type=EntityType.VULNERABILITY,
                entity_id=uuid4(),
            ),
            query_key=",".join(pending),
            query_kind="cve",
            requested_at=requested_at,
        )
        response = await self._provider.enrich(request)
        if response.status is not EnrichmentStatus.SUCCESS:
            return batch_out
        scores = response.normalized_result.get("scores")
        if not isinstance(scores, dict):
            return batch_out

        for cve in pending:
            score_fields = scores.get(cve)
            if not isinstance(score_fields, dict):
                continue
            normalized = {"cve_id": cve, "found": True, **score_fields}
            single_request = request.model_copy(update={"query_key": cve})
            cached_response = response.model_copy(
                update={
                    "request": single_request,
                    "normalized_result": normalized,
                }
            )
            self._cache.put(cached_response)
            batch_out[cve] = self._score_from_normalized(normalized)
        return batch_out

    async def aclose(self) -> None:
        await self._provider.aclose()


class AbuseIPDBEnricher:
    """Client for AbuseIPDB v2 check API."""

    def __init__(
        self,
        url: str = "https://api.abuseipdb.com/api/v2",
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from hermes_cti.enrichment.cache import EnrichmentCache
        from hermes_cti.enrichment.providers import AbuseIPDBProvider

        self.url = url.rstrip("/")
        self.api_key = api_key or os.environ.get("ABUSEIPDB_API_KEY")
        self._provider: AbuseIPDBProvider = AbuseIPDBProvider(
            url,
            api_key=self.api_key,
            enabled=bool(self.api_key),
            transport=transport,
        )
        self._cache: EnrichmentCache = EnrichmentCache()

    async def check_ip(self, ip_address: str) -> dict[str, Any] | None:
        """Lookup IP address in AbuseIPDB."""
        req = ProviderRequest(
            entity=EntityReference(
                entity_type=EntityType.INDICATOR,
                entity_id=uuid4(),
            ),
            query_key=ip_address.strip(),
            query_kind="ipv4" if ":" not in ip_address else "ipv6",
            requested_at=datetime.now(UTC),
        )
        if not self._provider.enabled:
            return None

        lookup = self._cache.get("abuseipdb", req.query_key, now=req.requested_at)
        if lookup.fresh and lookup.response:
            res = lookup.response
        else:
            res = await self._provider.enrich(req)
            if res.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}:
                self._cache.put(res)

        if res.status is EnrichmentStatus.SUCCESS:
            return {
                "abuse_confidence_score": res.normalized_result.get(
                    "abuse_confidence_score"
                ),
                "country_code": res.normalized_result.get("country_code"),
                "isp": res.normalized_result.get("usage_type"),
                "total_reports": res.normalized_result.get("total_reports"),
                "last_reported_at": res.normalized_result.get("last_reported_at"),
            }
        return None

    async def aclose(self) -> None:
        await self._provider.aclose()


class VirusTotalEnricher:
    """Client for VirusTotal v3 IP/domain/hash API."""

    def __init__(
        self,
        url: str = "https://www.virustotal.com/api/v3",
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from hermes_cti.enrichment.cache import EnrichmentCache
        from hermes_cti.enrichment.providers import VirusTotalProvider

        self.url = url.rstrip("/")
        self.api_key = api_key or os.environ.get("VIRUSTOTAL_API_KEY")
        self._provider: VirusTotalProvider = VirusTotalProvider(
            url,
            api_key=self.api_key,
            enabled=bool(self.api_key),
            transport=transport,
        )
        self._cache: EnrichmentCache = EnrichmentCache()

    async def enrich_indicator(self, kind: str, value: str) -> dict[str, Any] | None:
        """Query VirusTotal for an indicator (ip, domain, url, hash)."""
        req = ProviderRequest(
            entity=EntityReference(
                entity_type=EntityType.INDICATOR,
                entity_id=uuid4(),
            ),
            query_key=value.strip(),
            query_kind=kind.lower().strip(),
            requested_at=datetime.now(UTC),
        )
        if not self._provider.enabled:
            return None

        lookup = self._cache.get("virustotal", req.query_key, now=req.requested_at)
        if lookup.fresh and lookup.response:
            res = lookup.response
        else:
            res = await self._provider.enrich(req)
            if res.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}:
                self._cache.put(res)

        if res.status is EnrichmentStatus.SUCCESS and not res.normalized_result.get(
            "not_found"
        ):
            stats = res.normalized_result.get("last_analysis_stats")
            stats_dict: dict[str, Any] = stats if isinstance(stats, dict) else {}
            return {
                "malicious_count": _int_value(stats_dict.get("malicious")),
                "suspicious_count": _int_value(stats_dict.get("suspicious")),
                "harmless_count": _int_value(stats_dict.get("harmless")),
                "reputation": res.normalized_result.get("reputation"),
                "tags": res.normalized_result.get("tags", []),
                "graph_url": res.normalized_result.get("graph_url"),
            }
        return None

    async def aclose(self) -> None:
        await self._provider.aclose()


class IngestionEnrichmentService:
    """Enrichment coordinator with concurrency limiting, cache, and retry backoff."""

    def __init__(
        self,
        *,
        providers: Sequence[EnrichmentProvider] | None = None,
        max_concurrency: int = 5,
        cache: EnrichmentCache | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from hermes_cti.enrichment.cache import EnrichmentCache
        from hermes_cti.enrichment.providers import (
            AbuseIPDBProvider,
            CISAKEVProvider,
            EPSSProvider,
            VirusTotalProvider,
        )
        from hermes_cti.enrichment.service import EnrichmentService

        self.cache: EnrichmentCache = cache or EnrichmentCache()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        if providers is not None:
            self._service = EnrichmentService(providers, cache=self.cache)
        else:
            default_providers: list[EnrichmentProvider] = [
                CISAKEVProvider(
                    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                    transport=transport,
                ),
                EPSSProvider(
                    "https://api.first.org/data/v1/epss",
                    transport=transport,
                ),
            ]
            vt_key = os.environ.get("VIRUSTOTAL_API_KEY")
            default_providers.append(
                VirusTotalProvider(
                    "https://www.virustotal.com/api/v3",
                    api_key=vt_key,
                    enabled=bool(vt_key),
                    transport=transport,
                )
            )
            abuse_key = os.environ.get("ABUSEIPDB_API_KEY")
            default_providers.append(
                AbuseIPDBProvider(
                    "https://api.abuseipdb.com/api/v2",
                    api_key=abuse_key,
                    enabled=bool(abuse_key),
                    transport=transport,
                )
            )
            self._service = EnrichmentService(default_providers, cache=self.cache)

    async def enrich_cve(self, cve_id: str) -> EnrichmentRunResult:
        """Enrich a CVE using configured providers."""
        async with self.semaphore:
            return await self._service.enrich_cve(cve_id, uuid4())

    async def enrich_indicator(self, kind: str, value: str) -> EnrichmentRunResult:
        """Enrich an IOC using configured providers."""
        async with self.semaphore:
            return await self._service.enrich_indicator(kind, value)

    async def aclose(self) -> None:
        for provider in self._service.providers:
            await provider.aclose()
