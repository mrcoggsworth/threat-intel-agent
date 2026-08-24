"""Bounded in-process enrichment cache with stale-if-error support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from hermes_cti.models.contracts import ProviderResponse


@dataclass(frozen=True, slots=True)
class CacheLookup:
    """Cache lookup outcome, including expired data retained for safe degradation."""

    response: ProviderResponse | None
    fresh: bool
    stale: bool


class EnrichmentCache:
    """Small deterministic cache; durable provider history remains PostgreSQL's job."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] | None = None,
        stale_if_error_seconds: int = 604_800,
    ) -> None:
        self._entries: dict[str, ProviderResponse] = {}
        self._now = now or (lambda: datetime.now(UTC))
        self._stale_if_error_seconds = max(0, stale_if_error_seconds)

    @staticmethod
    def key(provider: str, query_key: str) -> str:
        return f"{provider.casefold()}:{query_key.strip().casefold()}"

    def get(
        self,
        provider: str,
        query_key: str,
        *,
        now: datetime | None = None,
    ) -> CacheLookup:
        response = self._entries.get(self.key(provider, query_key))
        if response is None:
            return CacheLookup(None, False, False)
        current = (now or self._now()).astimezone(UTC)
        if response.expires_at is not None and current < response.expires_at:
            return CacheLookup(
                response.model_copy(update={"cache_hit": True}), True, False
            )
        if response.expires_at is None:
            return CacheLookup(
                response.model_copy(update={"cache_hit": True}), True, False
            )
        stale_limit = response.expires_at.timestamp() + self._stale_if_error_seconds
        if current.timestamp() <= stale_limit:
            return CacheLookup(
                response.model_copy(update={"cache_hit": True}), False, True
            )
        return CacheLookup(None, False, False)

    def put(self, response: ProviderResponse) -> None:
        if response.status.value not in {"success", "partial"}:
            return
        self._entries[self.key(response.provider, response.request.query_key)] = (
            response
        )

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
