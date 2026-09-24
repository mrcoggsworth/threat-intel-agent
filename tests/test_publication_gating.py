"""Publication independence through the authenticated analyst API (Task 2.4).

Gates: a valid candidate publishes even when a sibling candidate fails
validation; duplicate submission of a published bundle must not create
duplicate reports, versions, or publications; updates must supersede with a
new version while the prior version stays intact; drafts must never appear in
the public projection. Every claim is verified by reading back the database
and the public API, not from response codes alone.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import create_async_engine

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings
from hermes_cti.db.models import (
    Publication,
    PublicationCandidate,
    Report,
    ReportVersion,
)
from hermes_cti.reporting.contracts import ReportBundle, ReportState
from tests.test_phase7 import _fixture

TOKEN_HEADERS = {"X-Analyst-Token": "test-analyst-token"}


def _query(postgres_settings: Settings, coro):
    """Run one async DB query on the ephemeral PostgreSQL from sync tests."""
    engine = create_async_engine(postgres_settings.database_url.get_secret_value())

    async def runner():
        try:
            async with engine.connect() as conn:
                return await coro(conn)
        finally:
            await engine.dispose()

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        return pool.submit(lambda: asyncio.run(runner())).result()


def _derive_bundle(
    *, public_id: str, slug: str, tail: str, report_id: UUID | None = None
) -> ReportBundle:
    """Clone the Phase 7 valid fixture with fully distinct identities."""
    base = _fixture()
    report_id = report_id or uuid4()
    version_id = uuid4()
    evidence_id = uuid4()
    evidence = base.evidence[0].model_copy(
        update={
            "evidence_id": evidence_id,
            "statement": base.evidence[0].statement + " " + tail,
        }
    )
    hunt = (
        base.hunt.model_copy(
            update={
                "hunt_id": uuid4(),
                "report_version_id": version_id,
                "evidence_ids": (evidence_id,),
            }
        )
        if base.hunt
        else None
    )
    remediation = (
        base.remediation.model_copy(
            update={
                "remediation_id": uuid4(),
                "report_version_id": version_id,
                "evidence_ids": (evidence_id,),
            }
        )
        if base.remediation
        else None
    )
    detections = tuple(
        item.model_copy(
            update={
                "detection_id": uuid4(),
                "report_version_id": version_id,
                "evidence_ids": (evidence_id,),
            }
        )
        for item in base.detections
    )
    return base.model_copy(
        update={
            "report_id": report_id,
            "report_version_id": version_id,
            "public_id": public_id,
            "slug": slug,
            "headline": base.headline + " " + tail,
            "headline_evidence_ids": (evidence_id,),
            "evidence": (evidence,),
            "hunt": hunt,
            "remediation": remediation,
            "detections": detections,
        }
    )


def _submit(client: TestClient, bundle: ReportBundle, publish: bool = True):
    return client.post(
        "/api/v1/analyst/reports",
        json={"bundle": bundle.model_dump(mode="json"), "publish": publish},
        headers=TOKEN_HEADERS,
    )


@pytest.fixture
def analyst_client(postgres_settings):
    settings = postgres_settings.model_copy(
        update={"analyst_token": SecretStr("test-analyst-token")}
    )
    with TestClient(create_app(settings=settings)) as client:
        yield client


def test_invalid_candidate_does_not_block_valid_candidate(
    analyst_client, postgres_settings
) -> None:
    blocked = _derive_bundle(
        public_id="PUB-2027-9001", slug="blocked-9001", tail="alpha"
    ).model_copy(update={"hunt": None})  # coverage gate must fail this one
    valid = _derive_bundle(public_id="PUB-2027-9002", slug="valid-9002", tail="beta")

    failed = _submit(analyst_client, blocked)
    assert failed.status_code == 422, failed.text

    published = _submit(analyst_client, valid)
    assert published.status_code == 200, published.text
    assert published.json()["state"] == "published"

    async def verify(conn):
        report_count = await conn.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.public_id.in_(["PUB-2027-9001", "PUB-2027-9002"]))
        )
        published_count = await conn.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.public_id == "PUB-2027-9002", Report.state == "published")
        )
        return int(report_count or 0), int(published_count or 0)

    report_count, published_count = _query(postgres_settings, verify)
    assert report_count == 1  # blocked candidate never persisted
    assert published_count == 1


def test_duplicate_submission_of_published_bundle_is_idempotent(
    analyst_client, postgres_settings
) -> None:
    bundle = _derive_bundle(public_id="PUB-2027-9003", slug="once-9003", tail="gamma")
    first = _submit(analyst_client, bundle)
    assert first.status_code == 200, first.text
    second = _submit(analyst_client, bundle)
    assert second.status_code == 200, second.text

    async def verify(conn):
        reports = await conn.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.public_id == "PUB-2027-9003")
        )
        versions = await conn.scalar(
            select(func.count())
            .select_from(ReportVersion)
            .where(ReportVersion.report_id == bundle.report_id)
        )
        publications = await conn.scalar(
            select(func.count())
            .select_from(Publication)
            .where(Publication.report_version_id == bundle.report_version_id)
        )
        return tuple(map(int, (reports, versions, publications)))

    reports, versions, publications = _query(postgres_settings, verify)
    assert (reports, versions, publications) == (1, 1, 1)


def test_update_creates_new_version_and_supersedes_without_rewriting_old(
    analyst_client, postgres_settings
) -> None:
    v1 = _derive_bundle(public_id="PUB-2027-9004", slug="evo-9004", tail="delta")
    assert _submit(analyst_client, v1).status_code == 200

    # Version 2 is the same report identity with a fresh version identity;
    # every sub-artifact (hunt/remediation/detections) is re-derived so the
    # bundle validator's version-ownership gates hold.
    v2 = _derive_bundle(
        public_id="PUB-2027-9004",
        slug="evo-9004",
        tail="delta",
        report_id=v1.report_id,
    ).model_copy(
        update={
            "version": 2,
            "supersedes_id": v1.report_version_id,
            "executive_summary": "Updated summary: exploitation continued after "
            "the vendor advisory. " + _fixture().executive_summary,
        }
    )
    updated = _submit(analyst_client, v2)
    assert updated.status_code == 200, updated.text
    assert updated.json()["report_version_id"] == str(v2.report_version_id)

    async def verify(conn):
        current = await conn.scalar(
            select(Report.current_version_id).where(Report.public_id == "PUB-2027-9004")
        )
        old_version_row = (
            await conn.execute(
                select(ReportVersion.version, ReportVersion.structured_content).where(
                    ReportVersion.id == v1.report_version_id
                )
            )
        ).first()
        versions = await conn.scalar(
            select(func.count())
            .select_from(ReportVersion)
            .where(ReportVersion.report_id == v1.report_id)
        )
        supersedes = await conn.scalar(
            select(ReportVersion.supersedes_id).where(
                ReportVersion.id == v2.report_version_id
            )
        )
        return current, old_version_row, int(versions or 0), supersedes

    current, old_version_row, version_count, supersedes = _query(
        postgres_settings, verify
    )
    assert version_count == 2
    assert current == v2.report_version_id
    assert supersedes == v1.report_version_id
    # The prior version is intact, not rewritten in place.
    assert old_version_row is not None
    assert old_version_row[0] == 1
    assert old_version_row[1]["headline"] == v1.headline


def test_blocked_candidate_recorded_in_ledger_and_excluded_from_public(
    analyst_client, postgres_settings
) -> None:
    """Task 2.4: one blocked candidate carries its exact missing fields in the
    durable ledger while a valid sibling publishes and reaches the public
    projection — and the blocked one never does."""
    import asyncio
    from uuid import uuid4 as _uuid4

    from hermes_cti.analyst.candidate_ledger import candidate_identity
    from hermes_cti.analyst.contracts import CandidateRecord
    from hermes_cti.db.models import IngestionRun

    run_id = _uuid4()
    seeded_at = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)

    async def seed_run() -> None:
        engine = create_async_engine(postgres_settings.database_url.get_secret_value())
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    insert(IngestionRun).values(
                        id=run_id,
                        run_type="daily",
                        idempotency_key=f"gating:{run_id}",
                        status="completed",
                        triggering_origin="test",
                        application_version="test",
                        configuration_hash="0" * 64,
                        started_at=seeded_at,
                        completed_at=seeded_at,
                    )
                )
        finally:
            await engine.dispose()

    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        pool.submit(lambda: asyncio.run(seed_run())).result()

    def ledger(lifecycle: str, tail: str, **fields: object) -> CandidateRecord:
        return CandidateRecord.model_validate(
            {
                "candidate_id": candidate_identity(run_id, f"cve:{tail}"),
                "run_id": run_id,
                "event_identity": f"cve:{tail}",
                "event_type": "cve",
                "rank": 1,
                "lifecycle": lifecycle,
                **fields,
            }
        )

    blocked = _derive_bundle(
        public_id="PUB-2027-9006", slug="blocked-9006", tail="zeta"
    ).model_copy(update={"hunt": None})
    failed = _submit(analyst_client, blocked)
    assert failed.status_code == 422
    exact_missing = failed.json()["detail"]  # service-computed, not hand-written
    assert (
        "missing" in str(exact_missing).lower()
        or "threat" in str(exact_missing).lower()
    ), exact_missing

    stored = analyst_client.put(
        f"/api/v1/analyst/candidates/{candidate_identity(run_id, 'cve:zeta')}",
        json=ledger(
            "blocked",
            "zeta",
            validation_state="failed",
            publication_state="not_published",
            failure_reason=str(exact_missing),
            retry_eligible=False,
        ).model_dump(mode="json"),
        headers=TOKEN_HEADERS,
    )
    assert stored.status_code == 200, stored.text

    valid = _derive_bundle(public_id="PUB-2027-9007", slug="valid-9007", tail="eta")
    published = _submit(analyst_client, valid)
    assert published.status_code == 200, published.text
    ok = analyst_client.put(
        f"/api/v1/analyst/candidates/{candidate_identity(run_id, 'cve:eta')}",
        json=ledger(
            "published",
            "eta",
            validation_state="passed",
            publication_state="published",
            published_public_id="PUB-2027-9007",
            retry_eligible=False,
            report_id=valid.report_id,
            report_version_id=valid.report_version_id,
        ).model_dump(mode="json"),
        headers=TOKEN_HEADERS,
    )
    assert ok.status_code == 200

    summary = analyst_client.get(
        f"/api/v1/analyst/candidates?run_id={run_id}", headers=TOKEN_HEADERS
    )
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["counts"]["blocked"] == 1
    assert payload["counts"]["published"] == 1
    assert payload["published_ids"] == ["PUB-2027-9007"]

    listed = analyst_client.get("/api/v1/public/reports?page=1&page_size=100")
    assert listed.status_code == 200
    public_ids = {item["public_id"] for item in listed.json().get("items", [])}
    assert "PUB-2027-9007" in public_ids
    assert "PUB-2027-9006" not in public_ids

    async def verify(conn):
        return await conn.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.public_id == "PUB-2027-9006")
        )

    assert _query(postgres_settings, verify) == 0
    # Permanent gate failure -> not retry-eligible, so the next execution will
    # not loop on it (the identified candidate from the valid path is separate).
    assert payload["retry_eligible"] == 0

    # Read the blocked row back from the DB: the stored failure reason is the
    # exact, service-computed missing-field text (truncated only to column width).
    async def blocked_reason(conn):
        return await conn.scalar(
            select(PublicationCandidate.failure_reason).where(
                PublicationCandidate.run_id == run_id,
                PublicationCandidate.lifecycle == "blocked",
            )
        )

    stored_reason = _query(postgres_settings, blocked_reason)
    assert stored_reason is not None
    assert str(exact_missing)[:40] in stored_reason


def test_draft_submission_never_reaches_public_projection(
    analyst_client, postgres_settings
) -> None:
    draft = _derive_bundle(
        public_id="PUB-2027-9005", slug="draft-9005", tail="epsilon"
    ).model_copy(update={"state": ReportState.DRAFT})
    saved = _submit(analyst_client, draft, publish=False)
    assert saved.status_code == 200, saved.text
    assert saved.json()["state"] == "draft"
    assert saved.json()["public_url"] is None

    listed = analyst_client.get("/api/v1/public/reports?page=1&page_size=100")
    assert listed.status_code == 200
    public_ids = {item["public_id"] for item in listed.json().get("items", [])}
    assert "PUB-2027-9005" not in public_ids
