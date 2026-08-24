"""Enrichment orchestration, conflict preservation, scoring, and health."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from hermes_cti.enrichment.cache import EnrichmentCache
from hermes_cti.enrichment.providers import EnrichmentProvider
from hermes_cti.enrichment.scoring import ScoreInputs, calculate_priority_score
from hermes_cti.models.contracts import (
    EnrichmentRunResult,
    EnrichmentStatus,
    EntityReference,
    JSONValue,
    ProviderErrorClassification,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)


class EnrichmentService:
    """Run providers in fixed order with cache and safe degraded states."""

    def __init__(
        self,
        providers: Sequence[EnrichmentProvider],
        *,
        cache: EnrichmentCache | None = None,
        now: Callable[[], datetime] | None = None,
        score_version: str = "phase5-v1",
    ) -> None:
        self.providers = tuple(providers)
        self.cache = cache if cache is not None else EnrichmentCache()
        self._now = now or (lambda: datetime.now(UTC))
        self.score_version = score_version

    async def enrich(
        self,
        request: ProviderRequest,
        *,
        score_inputs: ScoreInputs | None = None,
    ) -> EnrichmentRunResult:
        responses: list[ProviderResponse] = []
        for provider in self.providers:
            lookup = self.cache.get(
                provider.name, request.query_key, now=request.requested_at
            )
            if lookup.fresh and lookup.response is not None:
                responses.append(lookup.response)
                continue
            response = await provider.enrich(request)
            if response.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.PARTIAL}:
                self.cache.put(response)
            elif lookup.stale and lookup.response is not None:
                response = lookup.response.model_copy(
                    update={
                        "status": EnrichmentStatus.STALE,
                        "cache_hit": True,
                        "error_classification": response.error_classification
                        or ProviderErrorClassification.UNAVAILABLE,
                        "error_detail": response.error_detail
                        or "provider unavailable; stale result served",
                        "retryable": response.retryable,
                    }
                )
            responses.append(response)
        status = self._aggregate_status(responses)
        normalized, conflicts = self._merge_results(responses)
        priority = None
        if request.entity.entity_type.value == "vulnerability":
            values = score_inputs or self._score_inputs(normalized)
            priority = calculate_priority_score(
                values,
                now=request.requested_at,
                score_version=self.score_version,
            )
        return EnrichmentRunResult(
            entity=request.entity,
            status=status,
            provider_results=tuple(responses),
            normalized_result=normalized,
            conflicts=conflicts,
            priority=priority,
        )

    async def enrich_cve(
        self,
        cve_id: str,
        entity_id: Any,
        *,
        now: datetime | None = None,
        score_inputs: ScoreInputs | None = None,
    ) -> EnrichmentRunResult:
        request = ProviderRequest(
            entity=EntityReference(entity_type="vulnerability", entity_id=entity_id),
            query_key=cve_id,
            query_kind="cve",
            requested_at=(now or self._now()).astimezone(UTC),
        )
        return await self.enrich(request, score_inputs=score_inputs)

    def provider_health(self) -> tuple[ProviderHealth, ...]:
        current = self._now()
        return tuple(provider.health(current) for provider in self.providers)

    def _aggregate_status(
        self, responses: Sequence[ProviderResponse]
    ) -> EnrichmentStatus:
        if not responses or all(
            item.status is EnrichmentStatus.DISABLED for item in responses
        ):
            return EnrichmentStatus.DISABLED
        if any(item.status is EnrichmentStatus.SUCCESS for item in responses):
            if all(
                item.status in {EnrichmentStatus.SUCCESS, EnrichmentStatus.DISABLED}
                for item in responses
            ):
                return EnrichmentStatus.SUCCESS
            return EnrichmentStatus.PARTIAL
        if any(item.status is EnrichmentStatus.STALE for item in responses):
            return EnrichmentStatus.STALE
        return EnrichmentStatus.UNAVAILABLE

    @staticmethod
    def _merge_results(
        responses: Sequence[ProviderResponse],
    ) -> tuple[dict[str, JSONValue], dict[str, tuple[JSONValue, ...]]]:
        merged: dict[str, JSONValue] = {}
        observed: dict[str, list[JSONValue]] = {}
        for response in responses:
            if response.status in {
                EnrichmentStatus.DISABLED,
                EnrichmentStatus.UNAVAILABLE,
            }:
                continue
            for key, value in response.normalized_result.items():
                if value is None:
                    continue
                observed.setdefault(key, []).append(value)
                merged.setdefault(key, value)
        conflicts = {
            key: tuple(values)
            for key, values in sorted(observed.items())
            if len({str(value) for value in values}) > 1
        }
        return dict(sorted(merged.items())), conflicts

    @staticmethod
    def _score_inputs(normalized: dict[str, JSONValue]) -> ScoreInputs:
        def number(name: str) -> float | None:
            value = normalized.get(name)
            return (
                float(value)
                if isinstance(value, (int, float, str)) and str(value)
                else None
            )

        published = normalized.get("published_at")
        modified = normalized.get("modified_at")

        def timestamp(value: JSONValue) -> datetime | None:
            if not isinstance(value, str):
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None

        exploited = normalized.get("known_exploited")
        return ScoreInputs(
            known_exploited=exploited if isinstance(exploited, bool) else None,
            cvss_score=number("cvss_score"),
            epss_score=number("epss_score"),
            published_at=timestamp(published),
            modified_at=timestamp(modified),
        )
