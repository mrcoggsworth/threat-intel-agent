"""PostgreSQL integration coverage for the Phase 4 persistence boundary."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
from datetime import UTC, date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import asyncpg
import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.core.settings import Settings
from hermes_cti.db.entity_repositories import EntityRepository
from hermes_cti.db.lifecycle import (
    LIFECYCLE_FIELDS,
    constraint_name,
)
from hermes_cti.db.migrations import run_migrations
from hermes_cti.db.models import (
    Base,
    IndicatorObservation,
    IngestionRun,
    ModelRun,
    RawArtifact,
    Relationship,
    Report,
    ReportEntity,
    ReportVersion,
    SourceConfigurationHistory,
    SourceRun,
    Vulnerability,
)
from hermes_cti.db.models import (
    SourceDocument as SourceDocumentRecord,
)
from hermes_cti.db.query_plans import verify_query_plans
from hermes_cti.db.repositories import PersistenceRepository, RunRepository
from hermes_cti.db.scheduler import DailyScheduler
from hermes_cti.db.session import Database
from hermes_cti.db.vulnerability_models import (
    VulnerabilityAttributeSelection,
    VulnerabilityProviderObservation,
)
from hermes_cti.extraction import ExtractionConfig, extract_document
from hermes_cti.ingestion.service import CollectionResult
from hermes_cti.models.contracts import (
    CacheState,
    DocumentType,
    EnrichmentStatus,
    EntityReference,
    EntityType,
    IngestionRunManifest,
    ProviderRequest,
    ProviderResponse,
    RawArtifactMetadata,
    ReliabilityClassification,
    ReviewState,
    RunStatus,
    SourceCategory,
    SourceConfig,
    SourceDocument,
    SourceRegistry,
    SourceRunResult,
    SourceType,
    sha256_text,
)
from hermes_cti.portal.entity_repository import SqlEntityReadRepository
from hermes_cti.reporting.repository import ReportRepository


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
        columns = await session.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'report_version'"
            )
        )
        assert {
            "structured_content",
            "evidence_ids",
            "artifact_manifest",
            "skill_versions",
            "application_version",
        } <= set(columns)

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


@pytest.mark.asyncio
async def test_report_version_history_is_retained(database: Database) -> None:
    report_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    now = datetime.now(UTC)
    async with database.transaction() as session:
        session.add(
            Report(
                id=report_id,
                public_id=f"history-{report_id}",
                slug=f"history-{report_id}",
                headline="Public report history fixture",
                report_type="threat",
                severity="high",
                confidence=0.8,
                state="published",
                last_updated_at=now,
                current_version_id=second_id,
            )
        )
        session.add_all(
            [
                ReportVersion(
                    id=first_id,
                    report_id=report_id,
                    version=1,
                    executive_summary="first",
                    technical_analysis="first",
                    evidence_summary="first",
                    generated_by="test",
                    validation_status="published",
                    application_version="test",
                ),
                ReportVersion(
                    id=second_id,
                    report_id=report_id,
                    version=2,
                    executive_summary="second",
                    technical_analysis="second",
                    evidence_summary="second",
                    generated_by="test",
                    validation_status="published",
                    supersedes_id=first_id,
                    application_version="test",
                ),
            ]
        )
    async with database.session() as session:
        history = await ReportRepository().version_history(session, report_id)
    assert [item.version for item in history] == [1, 2]
    assert history[1].supersedes_id == first_id


@pytest.mark.asyncio
async def test_persists_normalized_entity_and_model_run(database: Database) -> None:
    from hermes_cti.db.entity_repositories import EntityRepository
    from hermes_cti.db.model_run_repository import ModelRunRepository

    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    actor_id = uuid4()
    model_run_id = uuid4()
    async with database.transaction() as session:
        actor = await EntityRepository().upsert_threat_actor(
            session,
            entity_id=actor_id,
            canonical_name="Example Group",
            normalized_name=f"example-group-{actor_id}",
            aliases=("Example",),
            first_seen_at=now,
            last_seen_at=now,
        )
        model_run = await ModelRunRepository().persist(
            session,
            model_run_id=model_run_id,
            purpose="test_audit",
            model_provider="test-provider",
            prompt_name="test-prompt",
            prompt_version="1",
            system_prompt_hash="a" * 64,
            skill_version_hashes=("b" * 64,),
            output_hash="c" * 64,
            started_at=now,
            completed_at=now,
        )
    assert actor.id == actor_id
    assert model_run.id == model_run_id
    assert model_run.system_prompt_hash == "a" * 64
    assert model_run.skill_version_hashes == ["b" * 64]


@pytest.mark.asyncio
async def test_postgres_enforces_lifecycle_registry(database: Database) -> None:
    expected = {constraint_name(table, column) for table, column in LIFECYCLE_FIELDS}
    expected |= {
        constraint_name(table.name, "record_status")
        for table in Base.metadata.tables.values()
        if "record_status" in table.c
    }
    async with database.session() as session:
        actual = set(
            await session.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname LIKE 'ck\\_%\\_lifecycle' ESCAPE '\\'"
                )
            )
        )
        assert expected <= actual

        from hermes_cti.db.model_run_repository import ModelRunRepository

        with pytest.raises(ValueError, match="model_run.status"):
            await ModelRunRepository().persist(
                session,
                model_run_id=uuid4(),
                purpose="lifecycle-test",
                model_provider="test",
                prompt_name="test",
                prompt_version="1",
                output_hash=None,
                status="__invalid__",
            )
        with pytest.raises(ValueError, match="threat_actor.attribution_state"):
            await EntityRepository().upsert_threat_actor(
                session,
                entity_id=uuid4(),
                canonical_name="Invalid Actor",
                normalized_name=f"invalid-actor-{uuid4()}",
                attribution_state="__invalid__",
            )

        model_run = ModelRun(
            id=uuid4(),
            purpose="lifecycle-test",
            model_provider="test",
            prompt_name="test",
            prompt_version="1",
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            status="completed",
        )
        session.add(model_run)
        await session.flush()
        with pytest.raises(DBAPIError):
            async with session.begin_nested():
                await session.execute(
                    text("UPDATE model_run SET status = '__invalid__' WHERE id = :id"),
                    {"id": model_run.id},
                )
                await session.flush()


@pytest.mark.asyncio
async def test_postgres_public_projection_excludes_draft_and_rejected_rows(
    database: Database,
) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    actor_id, malware_id, draft_product_id = uuid4(), uuid4(), uuid4()
    published_report_id, published_version_id = uuid4(), uuid4()
    draft_report_id, draft_version_id = uuid4(), uuid4()
    reviewed_id, rejected_id = uuid4(), uuid4()
    async with database.transaction() as session:
        await EntityRepository().upsert_threat_actor(
            session,
            entity_id=actor_id,
            canonical_name="Published Actor",
            normalized_name=f"published-actor-{actor_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
        await EntityRepository().upsert_malware(
            session,
            entity_id=malware_id,
            canonical_name="Published Malware",
            normalized_name=f"published-malware-{malware_id}",
            first_seen_at=now,
            last_seen_at=now,
        )
        await EntityRepository().upsert_product(
            session,
            entity_id=draft_product_id,
            vendor="Draft Vendor",
            product="Draft Product",
            normalized_vendor="draft-vendor",
            normalized_product="draft-product",
        )
        session.add_all(
            [
                Report(
                    id=published_report_id,
                    public_id=f"published-projection-{published_report_id}",
                    slug=f"published-projection-{published_report_id}",
                    headline="Published projection",
                    report_type="threat",
                    severity="high",
                    confidence=0.9,
                    state="published",
                    last_updated_at=now,
                ),
                Report(
                    id=draft_report_id,
                    public_id=f"draft-projection-{draft_report_id}",
                    slug=f"draft-projection-{draft_report_id}",
                    headline="Draft projection",
                    report_type="threat",
                    severity="high",
                    confidence=0.9,
                    state="draft",
                    last_updated_at=now,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                ReportVersion(
                    id=published_version_id,
                    report_id=published_report_id,
                    version=1,
                    executive_summary="Published",
                    technical_analysis="Published",
                    evidence_summary="Published",
                    generated_by="test",
                    validation_status="published",
                    application_version="test",
                ),
                ReportVersion(
                    id=draft_version_id,
                    report_id=draft_report_id,
                    version=1,
                    executive_summary="Draft",
                    technical_analysis="Draft",
                    evidence_summary="Draft",
                    generated_by="test",
                    validation_status="draft",
                    application_version="test",
                ),
            ]
        )
        await session.flush()
        await session.execute(
            update(Report)
            .where(Report.id == published_report_id)
            .values(current_version_id=published_version_id)
        )
        await session.execute(
            update(Report)
            .where(Report.id == draft_report_id)
            .values(current_version_id=draft_version_id)
        )
        session.add_all(
            [
                ReportEntity(
                    id=uuid4(),
                    report_version_id=published_version_id,
                    entity_type=EntityType.ACTOR.value,
                    entity_id=actor_id,
                    role="subject",
                ),
                ReportEntity(
                    id=uuid4(),
                    report_version_id=published_version_id,
                    entity_type=EntityType.MALWARE.value,
                    entity_id=malware_id,
                    role="subject",
                ),
                ReportEntity(
                    id=uuid4(),
                    report_version_id=draft_version_id,
                    entity_type=EntityType.PRODUCT.value,
                    entity_id=draft_product_id,
                    role="subject",
                ),
            ]
        )
        session.add_all(
            [
                Relationship(
                    id=reviewed_id,
                    source_entity_type=EntityType.ACTOR.value,
                    source_entity_id=actor_id,
                    relationship_type="uses_malware",
                    target_entity_type=EntityType.MALWARE.value,
                    target_entity_id=malware_id,
                    direction="forward",
                    origin="deterministic",
                    confidence=0.9,
                    first_seen_at=now,
                    last_seen_at=now,
                    active=True,
                    review_state=ReviewState.REVIEWED.value,
                    origin_rule="test",
                    justification="Published fixture",
                ),
                Relationship(
                    id=rejected_id,
                    source_entity_type=EntityType.ACTOR.value,
                    source_entity_id=actor_id,
                    relationship_type="uses_malware",
                    target_entity_type=EntityType.MALWARE.value,
                    target_entity_id=malware_id,
                    direction="forward",
                    origin="model_inference",
                    confidence=0.9,
                    active=True,
                    review_state=ReviewState.REJECTED.value,
                    origin_rule="test-rejected",
                    justification="Rejected fixture",
                ),
            ]
        )
    async with database.session() as session:
        repository = SqlEntityReadRepository()
        actor = await repository.get_public_entity(
            session, EntityType.ACTOR.value, f"published-actor-{actor_id}"
        )
        draft = await repository.get_public_entity(
            session, EntityType.PRODUCT.value, "draft-vendor|draft-product|unknown"
        )
        relationships = await repository.public_relationships(session)
    assert actor is not None
    assert actor.entity_id == actor_id
    assert draft is None
    assert [row.relationship.id for row in relationships] == [reviewed_id]


@pytest.mark.asyncio
async def test_postgres_query_plan_checks_use_declared_indexes(
    database: Database,
) -> None:
    async with database.session() as session:
        await session.execute(text("SET LOCAL enable_seqscan = off"))
        results = await verify_query_plans(session)

    assert results
    assert all(result.passed for result in results), results


@pytest.mark.asyncio
async def test_postgres_persists_typed_vulnerability_enrichment(
    database: Database,
) -> None:
    now = datetime(2026, 8, 24, 12, tzinfo=UTC)
    vulnerability_id = uuid4()
    cve_id = "CVE-2026-4242"

    def response(
        provider: str, values: dict[str, object], payload_hash: str
    ) -> ProviderResponse:
        return ProviderResponse(
            provider=provider,
            request=ProviderRequest(
                entity=EntityReference(
                    entity_type=EntityType.VULNERABILITY, entity_id=vulnerability_id
                ),
                query_key=cve_id,
                query_kind="cve",
                requested_at=now,
            ),
            retrieved_at=now,
            status=EnrichmentStatus.SUCCESS,
            normalized_result=values,
            payload_hash=payload_hash,
        )

    responses = (
        response(
            "cisa_kev",
            {
                "cve_id": cve_id,
                "known_exploited": True,
                "date_added": "2026-08-01",
                "due_date": "2026-08-21",
                "vendor_project": "Example",
                "product": "Example Product",
                "required_action": "Apply the vendor mitigation.",
            },
            "a" * 64,
        ),
        response(
            "epss",
            {
                "cve_id": cve_id,
                "epss_score": 0.91,
                "epss_percentile": 0.99,
                "epss_date": "2026-08-23",
            },
            "b" * 64,
        ),
        response(
            "nvd",
            {
                "cve_id": cve_id,
                "description": "Example vulnerability",
                "published_at": "2026-07-01T00:00:00Z",
                "modified_at": "2026-08-20T00:00:00Z",
                "cvss_score": 9.8,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                "cwe_ids": ["CWE-787"],
            },
            "c" * 64,
        ),
    )

    async with database.transaction() as session:
        await PersistenceRepository().persist_enrichment_run(
            session,
            provider_responses=responses,
            entity_type="vulnerability",
            entity_id=vulnerability_id,
        )

    async with database.session() as session:
        vulnerability = await session.scalar(
            select(Vulnerability).where(Vulnerability.id == vulnerability_id)
        )
        observations = tuple(
            (
                await session.scalars(
                    select(VulnerabilityProviderObservation).where(
                        VulnerabilityProviderObservation.vulnerability_id
                        == vulnerability_id
                    )
                )
            ).all()
        )
        selections = tuple(
            (
                await session.scalars(
                    select(VulnerabilityAttributeSelection).where(
                        VulnerabilityAttributeSelection.vulnerability_id
                        == vulnerability_id
                    )
                )
            ).all()
        )

    assert vulnerability is not None
    assert vulnerability.cvss_score == 9.8
    assert vulnerability.cvss_version == "3.1"
    assert vulnerability.epss_percentile == 0.99
    assert vulnerability.epss_date == date(2026, 8, 23)
    assert vulnerability.cwe_ids == ["CWE-787"]
    assert vulnerability.known_exploited is True
    assert vulnerability.exploitation_state == "known_exploited"
    assert vulnerability.kev_required_action == "Apply the vendor mitigation."
    assert len(observations) == 3
    assert {item.field_name for item in selections} >= {
        "cvss_score",
        "epss_percentile",
        "known_exploited",
    }

    async with database.transaction() as session:
        await PersistenceRepository().persist_enrichment_run(
            session,
            provider_responses=responses,
            entity_type="vulnerability",
            entity_id=vulnerability_id,
        )
    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(VulnerabilityProviderObservation)
            .where(
                VulnerabilityProviderObservation.vulnerability_id == vulnerability_id
            )
        )
    assert count == 3


@pytest.mark.asyncio
async def test_source_configuration_history_is_idempotent_and_versioned(
    database: Database,
) -> None:
    source = _source("history-source", "https://research.example/history")
    repository = PersistenceRepository()

    async with database.transaction() as session:
        await repository.upsert_source(session, source)
    async with database.transaction() as session:
        await repository.upsert_source(session, source)

    changed = source.model_copy(update={"tags": ("changed",)})
    async with database.transaction() as session:
        await repository.upsert_source(session, changed)

    async with database.session() as session:
        history = await session.scalars(
            select(SourceConfigurationHistory)
            .where(SourceConfigurationHistory.source_id == source.source_id)
            .order_by(SourceConfigurationHistory.configuration_version)
        )
        rows = tuple(history)

    assert [row.configuration_version for row in rows] == [1, 2]
    assert rows[0].configuration_hash != rows[1].configuration_hash
    assert rows[1].configuration["tags"] == ["changed"]


@pytest.mark.asyncio
async def test_publish_bundle_with_unmatched_source_document_id(
    database: Database,
) -> None:
    from hermes_cti.reporting import (
        ReportEvidence,
        ReportEvidenceType,
        ReportPipeline,
    )
    from tests.test_phase7 import _fixture, EVIDENCE_ID

    bundle = _fixture()
    evidence_with_unmatched_source = ReportEvidence(
        evidence_id=EVIDENCE_ID,
        evidence_type=ReportEvidenceType.SOURCE_TEXT,
        statement="Public CVE-2027-1234 exploitation observed in a vendor advisory.",
        confidence=0.95,
        source_document_id=UUID("d7a27a68-450a-54b3-968c-183c7d97993a"),
    )
    bundle_with_source_doc = bundle.model_copy(
        update={"evidence": (evidence_with_unmatched_source,)}
    )
    pipeline = ReportPipeline()
    async with database.transaction() as session:
        report = await pipeline.publish(session, bundle_with_source_doc)
        assert getattr(report, "state", None) == "published"


