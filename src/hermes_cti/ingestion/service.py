"""Async collection orchestration with partial-failure manifests."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import ValidationError

from hermes_cti import __version__
from hermes_cti.core.logging import reset_run_id, set_run_id
from hermes_cti.core.settings import Settings
from hermes_cti.ingestion.http_client import (
    AsyncHTTPClient,
    FetchError,
    FetchResult,
    HTTPClientConfig,
)
from hermes_cti.ingestion.normalization import (
    NormalizationError,
    normalize_feed,
    normalize_kev,
)
from hermes_cti.ingestion.source_config import source_configuration_hash
from hermes_cti.models.contracts import (
    CacheState,
    IngestionRunManifest,
    RawArtifactMetadata,
    RunStatus,
    SourceConfig,
    SourceDocument,
    SourceRegistry,
    SourceRunResult,
)

logger = logging.getLogger(__name__)
Clock = Callable[[], datetime]
_DEFAULT_ORIGIN: Final = "hermes-cti"


@dataclass(frozen=True, slots=True)
class ConditionalValidators:
    """Validators retained in memory until Phase 4 persistence exists."""

    etag: str | None = None
    last_modified: str | None = None

    @property
    def headers(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self.etag:
            values["If-None-Match"] = self.etag
        if self.last_modified:
            values["If-Modified-Since"] = self.last_modified
        return values


@dataclass(slots=True)
class SourceCollection:
    """Internal successful or failed source outcome before manifest assembly."""

    result: SourceRunResult
    raw_artifact: RawArtifactMetadata | None = None
    documents: tuple[SourceDocument, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """Complete in-memory vertical-slice result for one ingestion run."""

    manifest: IngestionRunManifest
    raw_artifacts: tuple[RawArtifactMetadata, ...]
    source_documents: tuple[SourceDocument, ...]

    def manifest_json(self) -> str:
        """Return the deterministic diagnostic manifest JSON."""

        return self.manifest.stable_json()


class IngestionService:
    """Collect configured sources concurrently with bounded source work."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: AsyncHTTPClient | None = None,
        clock: Clock | None = None,
        origin: str = _DEFAULT_ORIGIN,
    ) -> None:
        self.settings = settings or Settings()
        self._http_client = http_client
        self._clock = clock or (lambda: datetime.now(UTC))
        self._origin = origin
        self._validators: dict[str, ConditionalValidators] = {}

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("collection clock must return an aware datetime")
        return value.astimezone(UTC)

    def _client(self) -> AsyncHTTPClient:
        return AsyncHTTPClient(
            HTTPClientConfig.from_settings(self.settings),
        )

    async def _collect_source(
        self,
        client: AsyncHTTPClient,
        source: SourceConfig,
        run_id: UUID,
        semaphore: asyncio.Semaphore,
    ) -> SourceCollection:
        async with semaphore:
            started_at = self._now()
            logger.info(
                "source collection started",
                extra={
                    "event": "source_collection_started",
                    "component": "ingestion",
                    "source_id": source.source_id,
                    "status": "running",
                },
            )
            if not source.enabled:
                result = SourceRunResult(
                    source_id=source.source_id,
                    started_at=started_at,
                    completed_at=self._now(),
                    status=RunStatus.SKIPPED,
                    cache_state=CacheState.NOT_APPLICABLE,
                    error_classification="disabled",
                    error_detail="source is disabled",
                )
                return SourceCollection(result=result)

            cached = self._validators.get(source.source_id, ConditionalValidators())
            try:
                fetch = await client.fetch(
                    str(source.url),
                    headers=cached.headers,
                    timeout_seconds=source.timeout_seconds,
                    max_response_bytes=source.max_response_bytes,
                )
                cache_state = (
                    CacheState.NOT_MODIFIED
                    if fetch.status_code == 304
                    else (
                        CacheState.HIT
                        if cached.etag or cached.last_modified
                        else CacheState.MISS
                    )
                )
                if fetch.status_code == 304:
                    result = SourceRunResult(
                        source_id=source.source_id,
                        started_at=started_at,
                        completed_at=self._now(),
                        status=RunStatus.COMPLETED,
                        http_status=304,
                        retry_count=fetch.retry_count,
                        cache_state=cache_state,
                    )
                    return SourceCollection(result=result)

                artifact = self._artifact(source, fetch, run_id, self._now())
                if source.source_type.value == "json":
                    documents = normalize_kev(source, fetch, artifact)
                else:
                    documents = normalize_feed(source, fetch, artifact)
                self._validators[source.source_id] = ConditionalValidators(
                    etag=fetch.header("etag"),
                    last_modified=fetch.header("last-modified"),
                )
                result = SourceRunResult(
                    source_id=source.source_id,
                    started_at=started_at,
                    completed_at=self._now(),
                    status=RunStatus.COMPLETED,
                    http_status=fetch.status_code,
                    item_count=len(documents),
                    retry_count=fetch.retry_count,
                    cache_state=cache_state,
                )
                logger.info(
                    "source collection completed",
                    extra={
                        "event": "source_collection_completed",
                        "component": "ingestion",
                        "source_id": source.source_id,
                        "status": "completed",
                        "retry_count": fetch.retry_count,
                    },
                )
                return SourceCollection(
                    result=result, raw_artifact=artifact, documents=documents
                )
            except FetchError as exc:
                return self._failed_source(
                    source,
                    started_at,
                    exc.classification,
                    exc.detail,
                    exc.retry_count,
                )
            except NormalizationError as exc:
                return self._failed_source(
                    source, started_at, exc.classification, exc.detail, 0
                )
            except ValidationError:
                return self._failed_source(
                    source,
                    started_at,
                    "schema_error",
                    "normalized document was invalid",
                    0,
                )
            except Exception:
                return self._failed_source(
                    source,
                    started_at,
                    "unexpected_error",
                    "source processing failed",
                    0,
                )

    def _failed_source(
        self,
        source: SourceConfig,
        started_at: datetime,
        classification: str,
        detail: str,
        retry_count: int,
    ) -> SourceCollection:
        logger.error(
            "source collection failed",
            extra={
                "event": "source_collection_failed",
                "component": "ingestion",
                "source_id": source.source_id,
                "status": "failed",
                "error_classification": classification,
                "retry_count": retry_count,
            },
        )
        return SourceCollection(
            result=SourceRunResult(
                source_id=source.source_id,
                started_at=started_at,
                completed_at=self._now(),
                status=RunStatus.FAILED,
                retry_count=retry_count,
                cache_state=CacheState.MISS,
                error_classification=classification,
                error_detail=detail,
            )
        )

    @staticmethod
    def _artifact(
        source: SourceConfig,
        fetch: FetchResult,
        run_id: UUID,
        retrieved_at: datetime,
    ) -> RawArtifactMetadata:
        body = fetch.body
        digest = hashlib.sha256(body).hexdigest()
        artifact_id = uuid5(
            NAMESPACE_URL,
            f"raw-artifact:{source.source_id}:{fetch.url}:{digest}",
        )
        return RawArtifactMetadata(
            raw_artifact_id=artifact_id,
            source_id=source.source_id,
            retrieval_url=fetch.url,
            canonical_url=source.url,
            retrieved_at=retrieved_at,
            response_status=fetch.status_code,
            content_type=fetch.content_type,
            encoding=fetch.encoding,
            etag=fetch.header("etag"),
            last_modified=fetch.header("last-modified"),
            content_hash=digest,
            byte_length=len(body),
            ingestion_run_id=run_id,
        )

    async def collect_once(
        self,
        registry: SourceRegistry,
        *,
        ingestion_run_id: UUID | None = None,
        idempotency_key: str | None = None,
        scheduled_for: datetime | None = None,
    ) -> CollectionResult:
        """Collect all sources and return successful evidence despite failures."""

        run_id = ingestion_run_id or uuid4()
        started_at = self._now()
        token = set_run_id(str(run_id))
        logger.info(
            "ingestion run started",
            extra={
                "event": "ingestion_run_started",
                "component": "ingestion",
                "status": "running",
            },
        )
        try:
            client = self._http_client or self._client()
            semaphore = asyncio.Semaphore(max(1, self.settings.max_concurrency))
            outcomes = await asyncio.gather(
                *(
                    self._collect_source(client, source, run_id, semaphore)
                    for source in registry.sources
                )
            )
            results = tuple(
                sorted(
                    (outcome.result for outcome in outcomes),
                    key=lambda item: item.source_id,
                )
            )
            artifacts = tuple(
                sorted(
                    (
                        outcome.raw_artifact
                        for outcome in outcomes
                        if outcome.raw_artifact is not None
                    ),
                    key=lambda item: (
                        item.source_id,
                        str(item.canonical_url),
                        item.content_hash,
                    ),
                )
            )
            documents = tuple(
                sorted(
                    (
                        document
                        for outcome in outcomes
                        for document in outcome.documents
                    ),
                    key=lambda item: (
                        item.source_id,
                        item.published_at is None,
                        -(item.published_at.timestamp() if item.published_at else 0.0),
                        str(item.canonical_url),
                        item.external_source_id or "",
                    ),
                )
            )
            failed = sum(result.status is RunStatus.FAILED for result in results)
            successful = sum(result.status is RunStatus.COMPLETED for result in results)
            status = RunStatus.FAILED if failed else RunStatus.COMPLETED
            completed_at = self._now()
            manifest = IngestionRunManifest(
                ingestion_run_id=run_id,
                run_type="collect_once",
                idempotency_key=idempotency_key or f"collect-once:{run_id}",
                scheduled_for=scheduled_for,
                started_at=started_at,
                completed_at=completed_at,
                status=status,
                triggering_origin=self._origin,
                application_version=self.settings.app_version or __version__,
                configuration_hash=source_configuration_hash(registry),
                total_sources=len(results),
                successful_sources=successful,
                failed_sources=failed,
                new_documents=len(documents),
                source_results=results,
                error_summary=f"{failed} source(s) failed" if failed else None,
            )
            logger.info(
                "ingestion run completed",
                extra={
                    "event": "ingestion_run_completed",
                    "component": "ingestion",
                    "status": status.value,
                },
            )
            return CollectionResult(manifest, artifacts, documents)
        finally:
            reset_run_id(token)
            if self._http_client is None:
                await client.aclose()
