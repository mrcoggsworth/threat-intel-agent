"""Provider-level rate limiting: cross-request cooldown and configured pacing.

The HTTP client already honors Retry-After *within* a single fetch
(tests/test_phase5.py::test_rate_limit_honors_retry_after). These tests cover
the provider boundary: once a request exhausts retries and surfaces a 429, the
provider must stop dispatching until the recorded cooldown expires, and
build_providers must configure per-provider minimum spacing from settings.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest

from hermes_cti.core.settings import Settings
from hermes_cti.enrichment.providers import (
    NVDProvider,
    ProviderRuntimeConfig,
    build_providers,
)
from hermes_cti.models.contracts import (
    EnrichmentStatus,
    EntityReference,
    ProviderRequest,
)

NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)

NVD_FIXTURE = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2021-40438",
                "descriptions": [
                    {"lang": "en", "value": "fixture description for the test."}
                ],
                "metrics": {
                    "cvssMetricV31": [
                        {
                            "cvssData": {
                                "baseScore": 7.8,
                                "vectorString": "CVSS:3.1/AV:L",
                            }
                        }
                    ]
                },
            }
        }
    ]
}


def make_request(
    cve_id: str = "CVE-2021-40438",
    *,
    requested_at: datetime = NOW,
) -> ProviderRequest:
    return ProviderRequest(
        entity=EntityReference(
            entity_type="vulnerability",
            entity_id=UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"),
        ),
        query_key=cve_id,
        query_kind="cve",
        requested_at=requested_at,
    )


def nvd_handler(state: dict[str, int]):
    """429 while state['allow'] is False, then successful NVD payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        state["calls"] = state.get("calls", 0) + 1
        if not state.get("allow"):
            return httpx.Response(
                429,
                headers={"retry-after": "30"},
                content=json.dumps({"code": 503, "message": "rate"}).encode(),
            )
        return httpx.Response(
            200,
            json=NVD_FIXTURE,
            headers={"content-type": "application/json"},
        )

    return handler


def make_provider(state: dict[str, int], **config_overrides: object) -> NVDProvider:
    config = ProviderRuntimeConfig(
        max_retries=0,
        **config_overrides,  # type: ignore[arg-type]
    )
    return NVDProvider(
        "https://fixture/nvd",
        config=config,
        transport=httpx.MockTransport(nvd_handler(state)),
    )


@pytest.mark.asyncio
async def test_rate_limited_provider_cools_down_before_next_dispatch() -> None:
    """A 429 must stop further HTTP dispatch until the cooldown expires."""
    state: dict[str, int] = {"allow": 0}
    provider = make_provider(state)
    try:
        first = await provider.enrich(make_request())
        assert first.status is EnrichmentStatus.UNAVAILABLE
        assert first.error_classification.value == "rate_limit"
        assert first.retryable is True
        assert state.get("calls", 0) == 1

        # 10s later: still inside the recorded 30s cooldown. The provider must
        # answer from cooldown state without touching the transport at all.
        second = await provider.enrich(
            make_request(requested_at=NOW + timedelta(seconds=10))
        )
        assert state.get("calls", 0) == 1, "cooldown must not issue HTTP requests"
        assert second.status is EnrichmentStatus.UNAVAILABLE
        assert second.error_classification.value == "rate_limit"
        assert second.retryable is True

        # Past the cooldown: dispatch proceeds and the success clears the gate.
        state["allow"] = 1
        third = await provider.enrich(
            make_request(requested_at=NOW + timedelta(seconds=31))
        )
        assert state.get("calls", 0) == 2
        assert third.status is EnrichmentStatus.SUCCESS
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_cooldown_rejection_does_not_extend_its_own_window() -> None:
    """Repeated checks inside the window must not re-arm (infinite cooldown)."""
    state: dict[str, int] = {"allow": 0}
    provider = make_provider(state)
    try:
        await provider.enrich(make_request())  # 429 -> cooldown to NOW+30
        for offset in (5, 10, 15, 20, 25):
            response = await provider.enrich(
                make_request(requested_at=NOW + timedelta(seconds=offset))
            )
            assert response.error_classification.value == "rate_limit"
        state["allow"] = 1
        released = await provider.enrich(
            make_request(requested_at=NOW + timedelta(seconds=31))
        )
        assert released.status is EnrichmentStatus.SUCCESS
        assert state.get("calls", 0) == 2
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_min_interval_seconds_paces_successive_requests() -> None:
    """Configured minimum spacing must be enforced between provider calls."""
    state: dict[str, int] = {"allow": 1}
    provider = make_provider(state, min_interval_seconds=0.25)
    try:
        started = time.monotonic()
        first = await provider.enrich(make_request())
        second = await provider.enrich(
            make_request(requested_at=NOW + timedelta(seconds=1))
        )
        elapsed = time.monotonic() - started
    finally:
        await provider.aclose()
    assert first.status is EnrichmentStatus.SUCCESS
    assert second.status is EnrichmentStatus.SUCCESS
    assert state.get("calls", 0) == 2
    assert elapsed >= 0.2, f"expected >=0.25s pacing, measured {elapsed:.3f}s"


def test_build_providers_configures_nvd_min_interval() -> None:
    settings = Settings(database_required=False)
    providers = build_providers(settings)
    nvd = next(provider for provider in providers if provider.name == "nvd")
    assert nvd._config.min_interval_seconds == pytest.approx(6.0)


@pytest.mark.asyncio
async def test_success_leaves_no_lingering_cooldown() -> None:
    """Health reporting must not show a gate the provider already cleared."""
    state: dict[str, int] = {"allow": 1}
    provider = make_provider(state)
    try:
        ok = await provider.enrich(make_request())
        assert ok.status is EnrichmentStatus.SUCCESS
        health = provider.health(NOW)
        assert health.rate_limited_until is None
        assert provider._rate_limited_until is None
    finally:
        await provider.aclose()
