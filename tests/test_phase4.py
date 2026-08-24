"""PostgreSQL integration coverage for the Phase 4 persistence boundary."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg
import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.core.settings import Settings
from hermes_cti.db.migrations import run_migrations
from hermes_cti.db.models import (
    IndicatorObservation,
    IngestionRun,
    RawArtifact,
    Report,
    SourceRun,
    Vulnerability,
)
from hermes_cti.db.models import (
    SourceDocument as SourceDocumentRecord,
)
from hermes_cti.db.repositories import PersistenceRepository, RunRepository
from hermes_cti.db.scheduler import DailyScheduler
from hermes_cti.db.session import Database
from hermes_cti.extraction import ExtractionConfig, extract_document
from hermes_cti.ingestion.service import CollectionResult
from hermes_cti.models.contracts import (
    CacheState,
    DocumentType,
    IngestionRunManifest,
    RawArtifactMetadata,
    ReliabilityClassification,
    RunStatus,
    SourceCategory,
    SourceConfig,
    SourceDocument,
    SourceRegistry,
    SourceRunResult,
    SourceType,
    sha256_text,
)


def _start_postgres() -> tuple[str, str]:
    if not shutil.which("docker"):
        pytest.fail("Docker is required for PostgreSQL integration tests")
    result = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--env",
            "POSTGRES_DB=hermes_test",
            "--env",
            "POSTGRES_USER=hermes",
            "--env",
            "POSTGRES_PASSWORD=hermes",
            "--publish",
            "127.0.0.1::5432",
            "postgres:16-alpine",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    container = result.stdout.strip()
    port_result = subprocess.run(
        ["docker", "port", container, "5432/tcp"],
        check=True,
        capture_output=True,
        text=True,
    )
    port = port_result.stdout.rsplit(":", 1)[-1].strip()
    url = f"postgresql+asyncpg://hermes:hermes@127.0.0.1:{port}/hermes_test"

    async def check_connection() -> None:
        connection = await asyncpg.connect(
            user="hermes",
            password="hermes",
            database="hermes_test",
            host="127.0.0.1",
            port=int(port),
        )
        await connection.close()

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            asyncio.run(check_connection())
            return url, container
        except (ConnectionRefusedError, OSError, asyncpg.PostgresError):
            time.sleep(0.25)
    subprocess.run(["docker", "stop", container], check=False)
    pytest.fail("Ephemeral PostgreSQL did not become ready")


@pytest.fixture(scope="session")
def postgres_settings() -> Settings:
    configured = os.getenv("HERMES_TEST_DATABASE_URL")
    container = ""
    if configured:
        url = configured
    else:
        url, container = _start_postgres()
    settings = Settings(database_url=url)
    run_migrations(settings, "head")
    run_migrations(settings, "base")
    run_migrations(settings, "head")
    yield settings
    run_migrations(settings, "base")
    if container:
        subprocess.run(["docker", "stop", container], check=False)


@pytest.fixture
async def database(postgres_settings: Settings):
    database = Database(postgres_settings)
    yield database
    await database.dispose()


def _source(source_id: str, url: str) -> SourceConfig:
    return SourceConfig(
        source_id=source_id,
        name=source_id,
        url=url,
        source_type=SourceType.RSS,
        category=SourceCategory.THREAT_RESEARCH,
        reliability=ReliabilityClassification.PRIMARY_RESEARCH,
        polling_interval_seconds=86_400,
        timeout_seconds=5.0,
        max_response_bytes=100_000,
    )


def _collection(
    *,
    run_id: UUID,
    source: SourceConfig,
    content: str,
    status: RunStatus = RunStatus.COMPLETED,
    external_id: str = "article-1",
) -> CollectionResult:
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    artifact_id = uuid5(NAMESPACE_URL, f"artifact:{run_id}:{content}")
    document_id = uuid5(NAMESPACE_URL, f"document:{run_id}:{content}")
    artifact = RawArtifactMetadata(
        raw_artifact_id=artifact_id,
        source_id=source.source_id,
        retrieval_url=source.url,
        canonical_url="https://research.example/article-1",
        retrieved_at=now,
        response_status=200,
        content_type="application/rss+xml",
        content_hash=sha256_text(content),
        byte_length=len(content),
        ingestion_run_id=run_id,
    )
    document = SourceDocument(
        source_document_id=document_id,
        source_id=source.source_id,
        raw_artifact_id=artifact_id,
        external_source_id=external_id,
        canonical_url="https://research.example/article-1",
        title="Public research article",
        retrieved_at=now,
        normalized_text=content,
        document_type=DocumentType.ARTICLE,
        normalized_content_hash=sha256_text(content),
        parse_version="test-1",
    )
    result = SourceRunResult(
        source_id=source.source_id,
        started_at=now,
        completed_at=now,
        status=status,
        http_status=200 if status is RunStatus.COMPLETED else None,
        item_count=1 if status is RunStatus.COMPLETED else 0,
        cache_state=CacheState.MISS,
        error_classification=None if status is RunStatus.COMPLETED else "test",
        error_detail=None if status is RunStatus.COMPLETED else "fixture failure",
    )
    manifest = IngestionRunManifest(
        ingestion_run_id=run_id,
        run_type="daily",
        idempotency_key=f"fixture:{run_id}",
        scheduled_for=now,
        started_at=now,
        completed_at=now,
        status=status,
        triggering_origin="test",
        application_version="test",
        configuration_hash=sha256_text(source.source_id),
        total_sources=1,
        successful_sources=1 if status is RunStatus.COMPLETED else 0,
        failed_sources=0 if status is RunStatus.COMPLETED else 1,
        new_documents=1 if status is RunStatus.COMPLETED else 0,
        source_results=(result,),
    )
    return CollectionResult(
        manifest=manifest,
        raw_artifacts=(artifact,) if status is RunStatus.COMPLETED else (),
        source_documents=(document,) if status is RunStatus.COMPLETED else (),
    )


@pytest.mark.asyncio
async def test_migrations_and_immutable_artifacts(
    database: Database, postgres_settings: Settings
) -> None:
    async with database.session() as session:
        tables = await session.scalars(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        names = set(tables)
        assert {"ingestion_run", "raw_artifact", "report", "model_run"} <= names

        source = _source("migration-source", "https://research.example/feed")
        repository = PersistenceRepository()
        run_id = uuid4()
        collection = _collection(run_id=run_id, source=source, content="8.8.8.8")
        await repository.persist_collection(
            session, SourceRegistry(sources=(source,)), collection
        )
        await session.commit()
        with pytest.raises(DBAPIError):
            await session.execute(
                update(RawArtifact)
                .where(RawArtifact.id == collection.raw_artifacts[0].raw_artifact_id)
                .values(byte_length=999)
            )
            await session.commit()
        await session.rollback()

    assert postgres_settings.database_url is not None


@pytest.mark.asyncio
async def test_idempotency_and_changed_document_version(
    database: Database,
) -> None:
    source = _source("version-source", "https://research.example/feed")
    repository = PersistenceRepository()
    first = _collection(run_id=uuid4(), source=source, content="198.51.100.10")
    async with database.transaction() as session:
        await repository.persist_collection(
            session, SourceRegistry(sources=(source,)), first
        )
    async with database.transaction() as session:
        await repository.persist_collection(
            session, SourceRegistry(sources=(source,)), first
        )
    changed = _collection(
        run_id=uuid4(), source=source, content="203.0.113.20", external_id="article-1"
    )
    async with database.transaction() as session:
        await repository.persist_collection(
            session, SourceRegistry(sources=(source,)), changed
        )
    async with database.session() as session:
        records = await session.scalars(
            select(SourceDocumentRecord)
            .where(SourceDocumentRecord.source_id == source.source_id)
            .order_by(SourceDocumentRecord.document_version)
        )
        versions = list(records)
        runs = await session.scalars(
            select(IngestionRun).where(
                IngestionRun.id == first.manifest.ingestion_run_id
            )
        )
        assert len(list(runs)) == 1
        assert [record.document_version for record in versions] == [1, 2]
        assert versions[1].supersedes_id == versions[0].id


@pytest.mark.asyncio
async def test_persists_complete_deterministic_extraction(database: Database) -> None:
    source = _source("indicator-source", "https://research.example/feed")
    collection = _collection(
        run_id=uuid4(),
        source=source,
        content="Public indicator 8.8.8.8 and CVE-2026-1234",
    )
    repository = PersistenceRepository()
    async with database.transaction() as session:
        await repository.persist_collection(
            session, SourceRegistry(sources=(source,)), collection
        )
        extraction = extract_document(
            collection.source_documents[0], ExtractionConfig()
        )
        await repository.persist_extraction(
            session,
            extraction,
            collection.manifest.ingestion_run_id,
            collection.manifest.started_at,
        )
    async with database.session() as session:
        observations = await session.scalars(select(IndicatorObservation))
        vulnerabilities = await session.scalars(select(Vulnerability))
        assert len(list(observations)) == 1
        assert [record.cve_id for record in vulnerabilities] == ["CVE-2026-1234"]


@pytest.mark.asyncio
async def test_advisory_lock_is_single_holder(database: Database) -> None:
    async with (
        database.engine.connect() as first_connection,
        database.engine.connect() as second_connection,
    ):
        first_session = AsyncSession(bind=first_connection, expire_on_commit=False)
        second_session = AsyncSession(bind=second_connection, expire_on_commit=False)
        async with first_session, second_session:
            repository = RunRepository()
            assert await repository.try_daily_lock(first_session, 991_337)
            await first_session.commit()
            assert not await repository.try_daily_lock(second_session, 991_337)
            await second_session.rollback()
            await repository.release_daily_lock(first_session, 991_337)
            await first_session.commit()


@pytest.mark.asyncio
async def test_transaction_failure_does_not_persist_success(database: Database) -> None:
    run_id = uuid4()
    with pytest.raises(RuntimeError):
        async with database.transaction() as session:
            session.add(
                IngestionRun(
                    id=run_id,
                    run_type="daily",
                    idempotency_key=f"failure:{run_id}",
                    status=RunStatus.RUNNING.value,
                    triggering_origin="test",
                    application_version="test",
                    configuration_hash=sha256_text("failure"),
                )
            )
            await session.flush()
            raise RuntimeError("fixture transaction failure")
    async with database.session() as session:
        assert await session.get(IngestionRun, run_id) is None


@pytest.mark.asyncio
async def test_partial_source_outcomes_remain_attributable(database: Database) -> None:
    good = _source("good-source", "https://good.example/feed")
    failed = _source("failed-source", "https://failed.example/feed")
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    collection = _collection(run_id=uuid4(), source=good, content="good")
    failed_result = SourceRunResult(
        source_id=failed.source_id,
        started_at=now,
        completed_at=now,
        status=RunStatus.FAILED,
        cache_state=CacheState.MISS,
        error_classification="timeout",
        error_detail="fixture timeout",
    )
    manifest = collection.manifest.model_copy(
        update={
            "total_sources": 2,
            "failed_sources": 1,
            "status": RunStatus.FAILED,
            "source_results": collection.manifest.source_results + (failed_result,),
        }
    )
    partial = CollectionResult(
        manifest=manifest,
        raw_artifacts=collection.raw_artifacts,
        source_documents=collection.source_documents,
    )
    async with database.transaction() as session:
        await PersistenceRepository().persist_collection(
            session, SourceRegistry(sources=(good, failed)), partial
        )
    async with database.session() as session:
        source_runs = await session.scalars(
            select(SourceRun).where(
                SourceRun.ingestion_run_id == manifest.ingestion_run_id
            )
        )
        statuses = {record.source_id: record.status for record in source_runs}
        assert statuses == {"good-source": "completed", "failed-source": "failed"}


@pytest.mark.asyncio
async def test_public_repository_excludes_drafts_and_reports_staleness(
    database: Database,
) -> None:
    now = datetime.now(UTC)
    published = Report(
        id=uuid4(),
        public_id="published-1",
        slug="published-1",
        headline="Public report",
        report_type="threat",
        severity="medium",
        confidence=0.8,
        state="published",
        last_updated_at=now,
    )
    draft = Report(
        id=uuid4(),
        public_id="draft-1",
        slug="draft-1",
        headline="Draft report",
        report_type="threat",
        severity="medium",
        confidence=0.8,
        state="draft",
        last_updated_at=now,
    )
    stale_id = uuid4()
    async with database.transaction() as session:
        session.add_all([published, draft])
        session.add(
            IngestionRun(
                id=stale_id,
                run_type="daily",
                idempotency_key=f"stale:{stale_id}",
                started_at=now - timedelta(days=2),
                status=RunStatus.RUNNING.value,
                triggering_origin="test",
                application_version="test",
                configuration_hash=sha256_text("stale"),
            )
        )
    async with database.session() as session:
        reports = await RunRepository().public_reports(session)
        stale = await RunRepository().stale_runs(
            session, older_than=now - timedelta(days=1)
        )
        assert [report.public_id for report in reports] == ["published-1"]
        assert [run.id for run in stale] == [stale_id]


def test_scheduler_uses_explicit_timezone() -> None:
    settings = Settings(schedule_timezone="America/Chicago", schedule_hour=2)
    registry = SourceRegistry(sources=(_source("scheduler", "https://example.org"),))

    class NoopPipeline:
        async def run_once(self, *_args: object, **_kwargs: object) -> None:
            return None

    scheduler = DailyScheduler(settings, NoopPipeline(), registry)  # type: ignore[arg-type]
    instant = datetime(2026, 8, 22, 8, 30, tzinfo=UTC)
    assert scheduler.scheduled_for(instant).isoformat() == "2026-08-22T07:00:00+00:00"
