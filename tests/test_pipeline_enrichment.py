"""RED tests for the daily-pipeline enrichment stage.

Context
-------
Enrichment is fully implemented (``EnrichmentService``, three CVE providers,
cache, canonical selection, provenance tables) but **nothing in the automated
pipeline ever calls it**. ``grep -n "enrich" src/hermes_cti/db/scheduler.py``
and the same against ``src/hermes_cti/db/pipeline.py`` both return zero
matches; only the manual ``db enrich`` CLI and on-demand portal routes reach
it. The result is that every enrichment table in production is empty:

    vulnerability rows            16,831
    with cvss_score populated          0
    with epss_score populated          0
    with known_exploited populated     0
    vulnerability_provider_observation 0
    vulnerability_attribute_selection  0
    enrichment_result                  0

A manual ``db enrich --cve CVE-2026-76460`` proved the whole chain works
(CVSS 10.0 / KEV-listed / Cisco ISE, six provider observations with correct
per-provider provenance). The defect is therefore invocation, not mapping.

These tests pin the invocation contract that ``DailyPipeline.run_once`` must
satisfy. They use an injected fake enrichment service so they exercise the
pipeline's orchestration without any network access.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

from hermes_cti.core.settings import Settings
from hermes_cti.db.pipeline import DailyPipeline
from hermes_cti.models.contracts import (
    EnrichmentRunResult,
    EnrichmentStatus,
    EntityReference,
    EntityType,
    ProviderRequest,
    ProviderResponse,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRunRepository:
    """Stands in for RunRepository().vulnerability_ids_for_run."""

    def __init__(self, pairs: tuple[tuple[object, str], ...]) -> None:
        self._pairs = pairs
        self.calls: list[object] = []

    async def vulnerability_ids_for_run(self, session: object, run_id: object):
        self.calls.append(run_id)
        return self._pairs


class FakeDatabase:
    """Minimal stand-in providing session()/transaction() context managers."""

    class _Ctx:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_exc):
            return False

    def session(self):
        return self._Ctx()

    def transaction(self):
        return self._Ctx()


class FakePersistence:
    """Records persisted enrichment runs without touching a database."""

    def __init__(self) -> None:
        self.persisted: list[tuple[object, str]] = []

    async def persist_enrichment_run(
        self,
        session: object,
        *,
        provider_responses,
        entity_type,
        entity_id,
        priority=None,
    ):
        self.persisted.append((entity_id, entity_type))
        return (), None


def pipeline_with(settings: Settings) -> DailyPipeline:
    """Build a DailyPipeline wired with fakes and no real providers."""

    pipeline = DailyPipeline.__new__(DailyPipeline)
    pipeline.settings = settings
    pipeline.database = FakeDatabase()  # type: ignore[assignment]
    pipeline.runs = FakeRunRepository(())  # type: ignore[assignment]
    pipeline.repository = object()  # type: ignore[assignment]
    pipeline.ingestion_service = object()  # type: ignore[assignment]
    pipeline._clock = lambda: datetime.now(UTC)  # type: ignore[assignment]
    return pipeline


class FakeEnrichmentService:
    """Records enrichment invocations and can be told to fail per CVE."""

    def __init__(self, fail_for: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.fail_for = fail_for or set()

    async def enrich_cve(self, cve_id: str, entity_id: object, **_kwargs):
        self.calls.append(cve_id)
        if cve_id in self.fail_for:
            raise RuntimeError(f"provider exploded for {cve_id}")
        requested_at = datetime.now(UTC)
        response = ProviderResponse(
            provider="epss",
            request=ProviderRequest(
                entity=EntityReference(
                    entity_type=EntityType.VULNERABILITY, entity_id=entity_id
                ),
                query_key=cve_id,
                query_kind="cve",
                requested_at=requested_at,
            ),
            retrieved_at=requested_at,
            status=EnrichmentStatus.SUCCESS,
            retryable=False,
            normalized_result={"epss_score": 0.5},
        )
        return EnrichmentRunResult(
            entity=response.request.entity,
            status=EnrichmentStatus.SUCCESS,
            provider_results=(response,),
            normalized_result={"epss_score": 0.5},
            conflicts={},
            priority=None,
        )


def settings_with(**overrides: object) -> Settings:
    base = {
        "enrichment_pipeline_enabled": True,
        "enrichment_max_cves_per_run": 500,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


CVE_PAIRS = tuple(
    (uuid5(NAMESPACE_URL, f"vuln:{i}"), f"CVE-2026-{10000 + i}") for i in range(10)
)


# ---------------------------------------------------------------------------
# RED: the pipeline must invoke enrichment at all
# ---------------------------------------------------------------------------


def test_pipeline_invokes_enrichment_for_run_evidenced_cves() -> None:
    """``run_once`` enriches the CVEs evidenced by the run it just persisted.

    RED today: the pipeline never constructs or calls an enrichment service,
    so no CVE is ever enriched automatically.
    """

    pipeline = pipeline_with(settings_with())
    enrichment = FakeEnrichmentService()
    runs = FakeRunRepository(CVE_PAIRS)

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=runs,  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    assert enrichment.calls, "pipeline did not invoke enrichment at all"
    assert summary.attempted == len(CVE_PAIRS)
    assert summary.enriched == len(CVE_PAIRS)
    assert summary.failures == 0
    assert summary.truncated is False


def test_pipeline_enrichment_is_not_invoked_when_disabled() -> None:
    """The stage is inert unless explicitly enabled in configuration."""

    pipeline = pipeline_with(settings_with(enrichment_pipeline_enabled=False))
    enrichment = FakeEnrichmentService()

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=FakeRunRepository(CVE_PAIRS),  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    assert enrichment.calls == []
    assert summary.attempted == 0
    assert summary.enriched == 0


# ---------------------------------------------------------------------------
# Bounded work
# ---------------------------------------------------------------------------


def test_pipeline_enrichment_respects_configured_cap() -> None:
    """The per-run cap bounds provider traffic and is reported when hit."""

    pipeline = pipeline_with(settings_with(enrichment_max_cves_per_run=4))
    enrichment = FakeEnrichmentService()

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=FakeRunRepository(CVE_PAIRS),  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    assert len(enrichment.calls) == 4, "cap was not enforced"
    assert summary.attempted == len(CVE_PAIRS)
    assert summary.enriched == 4
    assert summary.truncated is True, "truncation must be surfaced, never silent"


# ---------------------------------------------------------------------------
# Degrade and continue
# ---------------------------------------------------------------------------


def test_pipeline_enrichment_continues_after_a_cve_fails() -> None:
    """One failing CVE must not abort the batch or its siblings."""

    pipeline = pipeline_with(settings_with())
    failing = {"CVE-2026-10003", "CVE-2026-10007"}
    enrichment = FakeEnrichmentService(fail_for=failing)

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=FakeRunRepository(CVE_PAIRS),  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    # Every CVE was still attempted.
    assert len(enrichment.calls) == len(CVE_PAIRS)
    assert summary.failures == len(failing)
    assert summary.enriched == len(CVE_PAIRS) - len(failing)
    # Failures are recorded with their reason, never swallowed.
    assert failing.issubset({item.cve_id for item in summary.failed})


def test_pipeline_enrichment_reports_counts_that_match_invocations() -> None:
    """Reported counts must be derived from real work, not asserted totals."""

    pipeline = pipeline_with(settings_with())
    enrichment = FakeEnrichmentService(fail_for={"CVE-2026-10000"})

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=FakeRunRepository(CVE_PAIRS),  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    assert summary.enriched + summary.failures == len(enrichment.calls)
    assert summary.enriched == len(enrichment.calls) - 1


# ---------------------------------------------------------------------------
# Empty and idempotent edge cases
# ---------------------------------------------------------------------------


def test_pipeline_enrichment_handles_no_run_evidence() -> None:
    """A run with no evidenced CVEs is a clean no-op."""

    pipeline = pipeline_with(settings_with())
    enrichment = FakeEnrichmentService()

    summary = asyncio.run(
        pipeline._enrich_run_cves(
            run_id=uuid4(),
            runs=FakeRunRepository(()),  # type: ignore[arg-type]
            enrichment=enrichment,  # type: ignore[arg-type]
            persist=FakePersistence(),  # type: ignore[arg-type]
        )
    )

    assert enrichment.calls == []
    assert summary.attempted == 0
    assert summary.failures == 0
    assert summary.truncated is False
