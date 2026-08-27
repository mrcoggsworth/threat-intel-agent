"""Bounded public enrichment provider clients for Phase 5."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import quote, urlencode

import httpx

from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    FetchResult,
    HTTPClientConfig,
)
from hermes_cti.models.contracts import (
    EnrichmentStatus,
    ProviderErrorClassification,
    ProviderHealth,
    ProviderRawMetadata,
    ProviderRequest,
    ProviderResponse,
    sha256_text,
)


class ProviderSchemaError(ValueError):
    """Provider payload is valid JSON but not the approved shape."""


class EnrichmentProvider(Protocol):
    name: str
    enabled: bool

    async def enrich(self, request: ProviderRequest) -> ProviderResponse: ...

    def health(self, now: datetime | None = None) -> ProviderHealth: ...

    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderRuntimeConfig:
    timeout_seconds: float = 20.0
    max_retries: int = 2
    max_response_bytes: int = 20_971_520
    concurrency: int = 2
    min_interval_seconds: float = 0.0
    ttl_seconds: int = 86_400


def _safe_headers(fetch: FetchResult) -> ProviderRawMetadata:
    retry_after = fetch.header("retry-after")
    retry_seconds: float | None = None
    if retry_after:
        try:
            retry_seconds = max(0.0, float(retry_after))
        except ValueError:
            retry_seconds = None
    remaining = fetch.header("x-ratelimit-remaining") or fetch.header(
        "x-rate-limit-remaining"
    )
    try:
        quota_remaining = int(remaining) if remaining is not None else None
    except ValueError:
        quota_remaining = None
    return ProviderRawMetadata(
        http_status=fetch.status_code,
        content_type=fetch.content_type,
        response_bytes=len(fetch.body),
        etag=fetch.header("etag"),
        last_modified=fetch.header("last-modified"),
        retry_after_seconds=retry_seconds,
        quota_remaining=quota_remaining,
    )


def _classification(value: str) -> ProviderErrorClassification:
    return {
        "timeout": ProviderErrorClassification.TIMEOUT,
        "rate_limited": ProviderErrorClassification.RATE_LIMIT,
        "transient_http_error": ProviderErrorClassification.RETRYABLE_HTTP,
        "http_error": ProviderErrorClassification.HTTP_ERROR,
        "authentication": ProviderErrorClassification.AUTHENTICATION,
    }.get(value, ProviderErrorClassification.UNAVAILABLE)


class BaseProvider:
    """Shared bounded request, retry, rate, concurrency, and health behavior."""

    def __init__(
        self,
        name: str,
        *,
        enabled: bool = True,
        config: ProviderRuntimeConfig | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        api_key: Any = None,
    ) -> None:
        self.name = name
        self.enabled = enabled
        self._config = config or ProviderRuntimeConfig()
        if api_key is not None and hasattr(api_key, "get_secret_value"):
            self._api_key = api_key.get_secret_value()
        elif api_key is not None:
            self._api_key = str(api_key)
        else:
            self._api_key = None
        self._transport = transport
        self._client: AsyncHTTPClient | None = None
        self._semaphore = asyncio.Semaphore(max(1, self._config.concurrency))
        self._rate_lock = asyncio.Lock()
        self._last_request = 0.0
        self._last_attempt_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._last_error: ProviderErrorClassification | None = None
        self._failures = 0
        self._rate_limited_until: datetime | None = None
        self._quota_remaining: int | None = None

    async def _open(self) -> AsyncHTTPClient:
        if self._client is None:
            self._client = AsyncHTTPClient(
                HTTPClientConfig(
                    max_retries=self._config.max_retries,
                    retry_backoff_seconds=0.2,
                    retry_max_delay_seconds=30.0,
                    retry_jitter_seconds=0.0,
                    user_agent="CTI-Hermes/0.1.0",
                ),
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _wait_rate_limit(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            wait = self._config.min_interval_seconds - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        raise NotImplementedError

    async def enrich(self, request: ProviderRequest) -> ProviderResponse:
        now = request.requested_at
        if not self.enabled:
            return self._response(
                request,
                now,
                EnrichmentStatus.DISABLED,
                retryable=False,
                error=ProviderErrorClassification.DISABLED,
                detail="provider disabled by configuration",
            )
        async with self._semaphore:
            await self._wait_rate_limit()
            self._last_attempt_at = now
            try:
                payload, fetch = await self._retrieve(request)
                self._last_success_at = now
                self._last_error = None
                self._failures = 0
                metadata = _safe_headers(fetch)
                self._quota_remaining = metadata.quota_remaining
                return self._response(
                    request,
                    now,
                    EnrichmentStatus.SUCCESS,
                    normalized=payload,
                    metadata=metadata,
                    payload=fetch.body,
                    retryable=False,
                )
            except ProviderSchemaError as exc:
                return self._failure(
                    request,
                    now,
                    ProviderErrorClassification.SCHEMA_DRIFT,
                    str(exc),
                    False,
                )
            except json.JSONDecodeError:
                return self._failure(
                    request,
                    now,
                    ProviderErrorClassification.MALFORMED_PAYLOAD,
                    "provider returned invalid JSON",
                    False,
                )
            except FetchError as exc:
                classification = _classification(exc.classification)
                metadata = ProviderRawMetadata(
                    http_status=exc.status_code,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                return self._failure(
                    request,
                    now,
                    classification,
                    exc.detail,
                    classification
                    in {
                        ProviderErrorClassification.TIMEOUT,
                        ProviderErrorClassification.RATE_LIMIT,
                        ProviderErrorClassification.RETRYABLE_HTTP,
                        ProviderErrorClassification.UNAVAILABLE,
                    },
                    metadata=metadata,
                    rate_limit_seconds=exc.retry_after_seconds,
                )
            except (httpx.HTTPError, OSError) as exc:
                return self._failure(
                    request,
                    now,
                    ProviderErrorClassification.UNAVAILABLE,
                    type(exc).__name__,
                    True,
                )

    def _failure(
        self,
        request: ProviderRequest,
        now: datetime,
        error: ProviderErrorClassification,
        detail: str,
        retryable: bool,
        metadata: ProviderRawMetadata | None = None,
        rate_limit_seconds: float | None = None,
    ) -> ProviderResponse:
        self._last_error = error
        self._failures += 1
        if error is ProviderErrorClassification.RATE_LIMIT:
            self._rate_limited_until = now + timedelta(seconds=rate_limit_seconds or 30)
        return self._response(
            request,
            now,
            EnrichmentStatus.UNAVAILABLE,
            retryable=retryable,
            error=error,
            detail=detail[:255],
            metadata=metadata,
        )

    def _response(
        self,
        request: ProviderRequest,
        now: datetime,
        status: EnrichmentStatus,
        *,
        normalized: dict[str, Any] | None = None,
        metadata: ProviderRawMetadata | None = None,
        payload: bytes | None = None,
        retryable: bool,
        error: ProviderErrorClassification | None = None,
        detail: str | None = None,
    ) -> ProviderResponse:
        expires = now + timedelta(seconds=self._config.ttl_seconds)
        return ProviderResponse(
            provider=self.name,
            request=request,
            retrieved_at=now,
            expires_at=expires,
            status=status,
            retryable=retryable,
            normalized_result=normalized or {},
            raw_metadata=metadata or ProviderRawMetadata(),
            payload_hash=sha256_text(payload.decode("utf-8", errors="replace"))
            if payload is not None
            else None,
            error_classification=error,
            error_detail=detail,
        )

    async def _fetch_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], FetchResult]:
        query = f"?{urlencode(params)}" if params else ""
        client = await self._open()
        result = await client.fetch(
            url + query,
            headers=headers,
            timeout_seconds=self._config.timeout_seconds,
            max_response_bytes=self._config.max_response_bytes,
        )
        loaded = json.loads(result.body)
        if not isinstance(loaded, dict):
            raise ProviderSchemaError("provider root must be an object")
        return loaded, result

    def health(self, now: datetime | None = None) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            enabled=self.enabled,
            state=(
                EnrichmentStatus.DISABLED
                if not self.enabled
                else (
                    EnrichmentStatus.DEGRADED
                    if self._failures
                    else EnrichmentStatus.SUCCESS
                )
            ),
            last_attempt_at=self._last_attempt_at,
            last_success_at=self._last_success_at,
            consecutive_failures=self._failures,
            rate_limited_until=self._rate_limited_until,
            quota_remaining=self._quota_remaining,
            last_error_classification=self._last_error,
        )


class CISAKEVProvider(BaseProvider):
    """CISA Known Exploited Vulnerabilities catalog client."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("cisa_kev", **kwargs)
        self.url = url

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        payload, fetch = await self._fetch_json(self.url)
        entries = payload.get("vulnerabilities")
        if not isinstance(entries, list):
            raise ProviderSchemaError("KEV vulnerabilities list missing")
        match = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict)
                and str(entry.get("cveID", "")).upper() == request.query_key.upper()
            ),
            None,
        )
        if match is None:
            return {
                "cve_id": request.query_key.upper(),
                "known_exploited": False,
                "matched": False,
            }, fetch
        return {
            "cve_id": request.query_key.upper(),
            "known_exploited": True,
            "matched": True,
            "date_added": match.get("dateAdded"),
            "due_date": match.get("dueDate"),
            "required_action": match.get("requiredAction"),
            "vulnerability_name": match.get("vulnerabilityName"),
            "vendor_project": match.get("vendorProject"),
            "product": match.get("product"),
        }, fetch


class EPSSProvider(BaseProvider):
    """FIRST EPSS probability client."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("epss", **kwargs)
        self.url = url

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        payload, fetch = await self._fetch_json(
            self.url, params={"cve": request.query_key.upper()}
        )
        entries = payload.get("data")
        if not isinstance(entries, list):
            raise ProviderSchemaError("EPSS data list missing")
        match = next(
            (
                entry
                for entry in entries
                if isinstance(entry, dict)
                and str(entry.get("cve", "")).upper() == request.query_key.upper()
            ),
            None,
        )
        if match is None:
            return {"cve_id": request.query_key.upper(), "found": False}, fetch
        try:
            epss = float(match["epss"])
            percentile = float(match["percentile"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderSchemaError("EPSS score fields malformed") from exc
        if not 0 <= epss <= 1 or not 0 <= percentile <= 1:
            raise ProviderSchemaError("EPSS values outside [0,1]")
        return {
            "cve_id": request.query_key.upper(),
            "found": True,
            "epss_score": epss,
            "epss_percentile": percentile,
            "epss_date": match.get("date"),
        }, fetch


class NVDProvider(BaseProvider):
    """NVD CVE API 2.0 client; API keys are optional and runtime-only."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("nvd", **kwargs)
        self.url = url

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        headers = {"apiKey": self._api_key} if self._api_key else None
        payload, fetch = await self._fetch_json(
            self.url,
            headers=headers,
            params={"cveId": request.query_key.upper()},
        )
        vulnerabilities = payload.get("vulnerabilities")
        if not isinstance(vulnerabilities, list):
            raise ProviderSchemaError("NVD vulnerabilities list missing")
        if not vulnerabilities:
            return {"cve_id": request.query_key.upper(), "found": False}, fetch
        item = vulnerabilities[0]
        if not isinstance(item, dict) or not isinstance(item.get("cve"), dict):
            raise ProviderSchemaError("NVD vulnerability entry malformed")
        cve = item["cve"]
        descriptions = cve.get("descriptions", [])
        description = (
            next(
                (
                    str(row.get("value"))
                    for row in descriptions
                    if isinstance(row, dict)
                    and row.get("lang") == "en"
                    and row.get("value")
                ),
                None,
            )
            if isinstance(descriptions, list)
            else None
        )
        cvss_score: float | None = None
        cvss_version: str | None = None
        vector: str | None = None
        metrics = cve.get("metrics", {})
        if isinstance(metrics, dict):
            for key in (
                "cvssMetricV40",
                "cvssMetricV31",
                "cvssMetricV30",
                "cvssMetricV2",
            ):
                candidates = metrics.get(key)
                if (
                    isinstance(candidates, list)
                    and candidates
                    and isinstance(candidates[0], dict)
                ):
                    data = candidates[0].get("cvssData")
                    if isinstance(data, dict):
                        try:
                            cvss_score = float(data["baseScore"])
                        except (KeyError, TypeError, ValueError):
                            continue
                        vector = (
                            str(data.get("vectorString"))
                            if data.get("vectorString")
                            else None
                        )
                        break
        weaknesses = cve.get("weaknesses", [])
        cwes = (
            sorted(
                {
                    str(description_row.get("value"))
                    for weakness in weaknesses
                    if isinstance(weakness, dict)
                    for description_row in (weakness.get("description") or [])
                    if isinstance(description_row, dict)
                    and description_row.get("value")
                }
            )
            if isinstance(weaknesses, list)
            else []
        )
        cve_data = {
            "cve_id": str(cve.get("id", request.query_key.upper())),
            "found": True,
            "description": description,
            "published_at": cve.get("published"),
            "modified_at": cve.get("lastModified"),
            "cvss_score": cvss_score,
            "cvss_version": cvss_version,
            "cvss_vector": vector,
            "cwe_ids": cwes,
            "known_exploited": bool(
                cve.get("cisaExploitAdd") or cve.get("cisaActionDue")
            ),
        }
        return cve_data, fetch


class VirusTotalProvider(BaseProvider):
    """Optional VirusTotal indicator client with a narrow normalized projection."""

    _kinds = frozenset({"ipv4", "ipv6", "domain", "url", "md5", "sha1", "sha256"})
    _kind_map = {
        "ipv4": "ip_addresses",
        "ipv6": "ip_addresses",
        "domain": "domains",
        "url": "urls",
        "md5": "files",
        "sha1": "files",
        "sha256": "files",
    }

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("virustotal", **kwargs)
        self.url = url.rstrip("/")

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        if request.query_kind not in self._kinds:
            raise ProviderSchemaError("VirusTotal requires an approved indicator kind")
        vt_kind = self._kind_map.get(request.query_kind, request.query_kind)
        if request.query_kind == "url":
            target = base64.urlsafe_b64encode(request.query_key.encode()).decode().rstrip("=")
        else:
            target = quote(request.query_key, safe="")
        try:
            payload, fetch = await self._fetch_json(
                f"{self.url}/{vt_kind}/{target}",
                headers={"x-apikey": self._api_key or ""},
            )
        except FetchError as exc:
            if exc.status_code == 404:
                return {
                    "indicator": request.query_key,
                    "not_found": True,
                    "reputation": 0,
                    "last_analysis_stats": {
                        "malicious": 0,
                        "suspicious": 0,
                        "harmless": 0,
                        "undetected": 0,
                    },
                    "tags": [],
                    "popular_threat_classification": None,
                    "graph_url": f"https://www.virustotal.com/gui/{request.query_kind}/{target}",
                    "hunting_available": False,
                }, FetchResult(
                    url=f"{self.url}/{vt_kind}/{target}",
                    status_code=404,
                    body=b'{"error": {"code": "NotFoundError"}}',
                    headers=(("content-type", "application/json"),),
                    retry_count=0,
                )
            raise
        data = payload.get("data")
        attrs = data.get("attributes") if isinstance(data, dict) else None
        if not isinstance(attrs, dict):
            raise ProviderSchemaError("VirusTotal data attributes missing")
        return {
            "indicator": request.query_key,
            "not_found": False,
            "reputation": attrs.get("reputation"),
            "last_analysis_stats": attrs.get("last_analysis_stats"),
            "tags": sorted(
                str(tag) for tag in attrs.get("tags", []) if isinstance(tag, str)
            ),
            "popular_threat_classification": attrs.get("popular_threat_classification"),
            "graph_url": f"https://www.virustotal.com/gui/{request.query_kind}/{target}",
            "hunting_available": True,
        }, fetch


class OTXProvider(BaseProvider):
    """Optional AlienVault OTX indicator client."""

    _kinds = frozenset({"ipv4", "ipv6", "domain", "url", "md5", "sha1", "sha256"})
    _kind_map = {
        "ipv4": "IPv4",
        "ipv6": "IPv6",
        "domain": "domain",
        "url": "url",
        "md5": "file",
        "sha1": "file",
        "sha256": "file",
    }

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("otx", **kwargs)
        self.url = url.rstrip("/")

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        if request.query_kind not in self._kinds:
            raise ProviderSchemaError("OTX requires an approved indicator kind")
        otx_kind = self._kind_map.get(request.query_kind, request.query_kind)
        target = quote(request.query_key, safe="")
        try:
            payload, fetch = await self._fetch_json(
                f"{self.url}/indicators/{otx_kind}/{target}/general",
                headers={"X-OTX-API-KEY": self._api_key or ""},
            )
        except FetchError as exc:
            if exc.status_code == 404:
                return {
                    "indicator": request.query_key,
                    "not_found": True,
                    "pulse_count": 0,
                    "pulse_names": [],
                    "sections": [],
                }, FetchResult(
                    url=f"{self.url}/indicators/{otx_kind}/{target}/general",
                    status_code=404,
                    body=b'{"pulse_info": {"count": 0}}',
                    headers=(("content-type", "application/json"),),
                    retry_count=0,
                )
            raise
        pulses = payload.get("pulse_info")
        if not isinstance(pulses, dict):
            raise ProviderSchemaError("OTX pulse_info missing")
        return {
            "indicator": request.query_key,
            "not_found": False,
            "pulse_count": pulses.get("count"),
            "pulse_names": sorted(
                str(item.get("name"))
                for item in pulses.get("pulses", [])
                if isinstance(item, dict) and item.get("name")
            ),
            "sections": sorted(
                str(item)
                for item in payload.get("sections", [])
                if isinstance(item, str)
            ),
        }, fetch


class AbuseIPDBProvider(BaseProvider):
    """Optional AbuseIPDB client for IP indicators only."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__("abuseipdb", **kwargs)
        self.url = url.rstrip("/")

    async def _retrieve(
        self, request: ProviderRequest
    ) -> tuple[dict[str, Any], FetchResult]:
        if request.query_kind not in {"ipv4", "ipv6"}:
            raise ProviderSchemaError("AbuseIPDB requires an IP indicator kind")
        payload, fetch = await self._fetch_json(
            f"{self.url}/check",
            headers={"Key": self._api_key or "", "Accept": "application/json"},
            params={"ipAddress": request.query_key, "maxAgeInDays": "90"},
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderSchemaError("AbuseIPDB data object missing")
        return {
            "indicator": request.query_key,
            "abuse_confidence_score": data.get("abuseConfidenceScore"),
            "country_code": data.get("countryCode"),
            "usage_type": data.get("usageType"),
            "total_reports": data.get("totalReports"),
            "last_reported_at": data.get("lastReportedAt"),
        }, fetch


def _secret(settings: Any, field: str) -> str | None:
    value = getattr(settings, field, None)
    if value is None:
        return None
    if hasattr(value, "get_secret_value"):
        raw = value.get_secret_value()
        return raw if raw else None
    s = str(value).strip()
    return s if s else None


def build_providers(
    settings: Any,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[EnrichmentProvider, ...]:
    """Build providers in the approved order without requiring optional keys."""

    common = dict(
        config=ProviderRuntimeConfig(
            timeout_seconds=float(settings.provider_timeout_seconds),
            max_retries=int(settings.provider_max_retries),
            max_response_bytes=int(settings.provider_max_response_bytes),
            concurrency=int(settings.provider_concurrency),
            ttl_seconds=int(settings.enrichment_cache_ttl_seconds),
        ),
        transport=transport,
    )
    core_enabled = bool(settings.enrichment_enabled)
    providers: list[EnrichmentProvider] = [
        CISAKEVProvider(str(settings.cisa_kev_url), enabled=core_enabled, **common),
        EPSSProvider(str(settings.epss_url), enabled=core_enabled, **common),
        NVDProvider(
            str(settings.nvd_url),
            enabled=core_enabled,
            api_key=_secret(settings, "nvd_api_key"),
            **common,
        ),
    ]
    providers.append(
        VirusTotalProvider(
            str(settings.virustotal_url),
            enabled=bool(
                (settings.virustotal_enabled or _secret(settings, "virustotal_api_key"))
                and _secret(settings, "virustotal_api_key")
            ),
            api_key=_secret(settings, "virustotal_api_key"),
            **common,
        )
    )
    providers.append(
        OTXProvider(
            str(settings.otx_url),
            enabled=bool(
                (settings.otx_enabled or _secret(settings, "otx_api_key"))
                and _secret(settings, "otx_api_key")
            ),
            api_key=_secret(settings, "otx_api_key"),
            **common,
        )
    )
    providers.append(
        AbuseIPDBProvider(
            str(settings.abuseipdb_url),
            enabled=bool(
                (settings.abuseipdb_enabled or _secret(settings, "abuseipdb_api_key"))
                and _secret(settings, "abuseipdb_api_key")
            ),
            api_key=_secret(settings, "abuseipdb_api_key"),
            **common,
        )
    )
    return tuple(providers)
