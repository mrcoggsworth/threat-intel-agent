"""Provider-neutral bounded asynchronous HTTP retrieval for public sources."""

from __future__ import annotations

import asyncio
import email.utils
import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

import httpx

Sleep = Callable[[float], Awaitable[None]]
TransientStatus: Final = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class HTTPClientConfig:
    """Transport policy shared by source adapters."""

    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    write_timeout_seconds: float = 10.0
    pool_timeout_seconds: float = 10.0
    max_redirects: int = 5
    verify_tls: bool = True
    user_agent: str = "CTI-Hermes/0.1.0"
    max_retries: int = 3
    retry_backoff_seconds: float = 0.5
    retry_max_delay_seconds: float = 30.0
    retry_jitter_seconds: float = 0.25

    @classmethod
    def from_settings(cls, settings: object) -> HTTPClientConfig:
        """Build a transport policy from the typed application settings."""

        return cls(
            connect_timeout_seconds=float(settings.http_connect_timeout_seconds),  # type: ignore[attr-defined]
            read_timeout_seconds=float(settings.http_read_timeout_seconds),  # type: ignore[attr-defined]
            write_timeout_seconds=float(settings.http_write_timeout_seconds),  # type: ignore[attr-defined]
            pool_timeout_seconds=float(settings.http_pool_timeout_seconds),  # type: ignore[attr-defined]
            max_redirects=int(settings.http_max_redirects),  # type: ignore[attr-defined]
            verify_tls=bool(settings.http_verify_tls),  # type: ignore[attr-defined]
            user_agent=str(settings.http_user_agent),  # type: ignore[attr-defined]
            max_retries=int(settings.http_max_retries),  # type: ignore[attr-defined]
            retry_backoff_seconds=float(settings.http_retry_backoff_seconds),  # type: ignore[attr-defined]
            retry_max_delay_seconds=float(settings.http_retry_max_delay_seconds),  # type: ignore[attr-defined]
            retry_jitter_seconds=float(settings.http_retry_jitter_seconds),  # type: ignore[attr-defined]
        )


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Bounded response data and metadata returned by the transport."""

    url: str
    status_code: int
    body: bytes
    headers: tuple[tuple[str, str], ...]
    retry_count: int

    def header(self, name: str) -> str | None:
        """Return one case-insensitive response header."""

        wanted = name.casefold()
        for key, value in self.headers:
            if key.casefold() == wanted:
                return value
        return None

    @property
    def content_type(self) -> str | None:
        return self.header("content-type")

    @property
    def encoding(self) -> str | None:
        """Return a declared response charset, if present."""

        value = self.content_type or ""
        for part in value.split(";")[1:]:
            key, separator, candidate = part.strip().partition("=")
            if key.casefold() == "charset" and separator:
                return candidate.strip().strip('"').strip("'") or None
        return None


class FetchError(Exception):
    """Safe, classified fetch failure without response-body disclosure."""

    def __init__(
        self,
        classification: str,
        detail: str,
        retry_count: int = 0,
        *,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        self.classification = classification
        self.detail = detail
        self.retry_count = retry_count
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(detail)


class AsyncHTTPClient:
    """HTTPX client with bounded reads, redirects, retries, and conditional headers."""

    def __init__(
        self,
        config: HTTPClientConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        random_value: Callable[[], float] | None = None,
    ) -> None:
        self.config = config or HTTPClientConfig()
        self._transport = transport
        self._sleep = sleep
        self._random_value = random_value or random.random
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> AsyncHTTPClient:
        await self._open()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=self.config.max_redirects,
                verify=self.config.verify_tls,
                headers={"User-Agent": self.config.user_agent},
                transport=self._transport,
            )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _timeout(self, source_timeout_seconds: float) -> httpx.Timeout:
        return httpx.Timeout(
            connect=min(self.config.connect_timeout_seconds, source_timeout_seconds),
            read=min(self.config.read_timeout_seconds, source_timeout_seconds),
            write=min(self.config.write_timeout_seconds, source_timeout_seconds),
            pool=min(self.config.pool_timeout_seconds, source_timeout_seconds),
        )

    def _retry_delay(self, attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                requested = max(0.0, float(retry_after))
            except ValueError:
                try:
                    parsed = email.utils.parsedate_to_datetime(retry_after)
                except (TypeError, ValueError, IndexError, OverflowError):
                    parsed = None
                if parsed is None:
                    return min(
                        self.config.retry_backoff_seconds * float(2**attempt),
                        self.config.retry_max_delay_seconds,
                    )
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                requested = max(0.0, (parsed - datetime.now(UTC)).total_seconds())
            return min(requested, self.config.retry_max_delay_seconds)
        exponential: float = self.config.retry_backoff_seconds * float(2**attempt)
        jitter = self.config.retry_jitter_seconds * float(self._random_value())
        return min(exponential + jitter, self.config.retry_max_delay_seconds)

    async def fetch(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 10_485_760,
    ) -> FetchResult:
        """Fetch one URL while never buffering more than the configured limit."""

        await self._open()
        if self._client is None:
            raise RuntimeError("HTTP client failed to initialize")

        request_headers = dict(headers or {})
        for attempt in range(self.config.max_retries + 1):
            try:
                async with self._client.stream(
                    "GET",
                    url,
                    headers=request_headers,
                    timeout=self._timeout(timeout_seconds),
                ) as response:
                    if response.status_code in TransientStatus:
                        if attempt < self.config.max_retries:
                            await self._sleep(
                                self._retry_delay(
                                    attempt, response.headers.get("retry-after")
                                )
                            )
                            continue
                        retry_after = response.headers.get("retry-after")
                        retry_after_seconds: float | None = None
                        if retry_after:
                            try:
                                retry_after_seconds = max(0.0, float(retry_after))
                            except ValueError:
                                retry_after_seconds = None
                        raise FetchError(
                            "rate_limited"
                            if response.status_code == 429
                            else "transient_http_error",
                            f"HTTP {response.status_code} after retries",
                            attempt,
                            status_code=response.status_code,
                            retry_after_seconds=retry_after_seconds,
                        )
                    if response.status_code == 304:
                        return FetchResult(
                            str(response.url),
                            response.status_code,
                            b"",
                            tuple(response.headers.multi_items()),
                            attempt,
                        )
                    if not 200 <= response.status_code < 300:
                        raise FetchError(
                            "http_error",
                            f"HTTP {response.status_code}",
                            attempt,
                        )
                    length = response.headers.get("content-length")
                    if length is not None and int(length) > max_response_bytes:
                        raise FetchError(
                            "oversized_response",
                            f"response exceeds {max_response_bytes} bytes",
                            attempt,
                        )
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_response_bytes:
                            raise FetchError(
                                "oversized_response",
                                f"response exceeds {max_response_bytes} bytes",
                                attempt,
                            )
                        chunks.append(chunk)
                    return FetchResult(
                        str(response.url),
                        response.status_code,
                        b"".join(chunks),
                        tuple(response.headers.multi_items()),
                        attempt,
                    )
            except FetchError:
                raise
            except httpx.TooManyRedirects as exc:
                raise FetchError(
                    "too_many_redirects", "redirect limit exceeded", attempt
                ) from exc
            except httpx.ConnectError as exc:
                detail = str(exc).casefold()
                classification = (
                    "tls_error"
                    if any(word in detail for word in ("certificate", "tls", "ssl"))
                    else "connection_error"
                )
                raise FetchError(
                    classification, "network connection failed", attempt
                ) from exc
            except httpx.TimeoutException as exc:
                if attempt < self.config.max_retries:
                    await self._sleep(self._retry_delay(attempt, None))
                    continue
                raise FetchError("timeout", "request timed out", attempt) from exc
            except httpx.NetworkError as exc:
                if attempt < self.config.max_retries:
                    await self._sleep(self._retry_delay(attempt, None))
                    continue
                raise FetchError(
                    "connection_error", "network connection failed", attempt
                ) from exc
            except ValueError as exc:
                raise FetchError(
                    "invalid_response", "invalid response metadata", attempt
                ) from exc
        raise AssertionError("retry loop did not return or raise")
