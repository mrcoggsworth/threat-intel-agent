"""Durable candidate-ledger behavior: idempotent upsert, bounded failure state.

The daily analyst execution must survive interruption without duplicating
publication work. These tests pin the ledger boundary: natural-key
idempotency, deterministic candidate identity, bounded failure reasons,
lifecycle constraint enforcement, and per-state accounting.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from hermes_cti.analyst.candidate_ledger import (
    CandidateLedgerRepository,
    candidate_identity,
)
from hermes_cti.analyst.contracts import CandidateRecord
from hermes_cti.db.models import IngestionRun, PublicationCandidate

NOW = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)


async def _ensure_run(session, run_id: UUID) -> None:
    """Ledger rows reference a real ingestion run through its FK."""
    session.add(
        IngestionRun(
            id=run_id,
            run_type="daily",
            idempotency_key=f"ledger-test:{run_id}",
            status="completed",
            triggering_origin="test",
            application_version="test",
            configuration_hash="0" * 64,
            started_at=NOW,
            completed_at=NOW,
        )
    )
    await session.flush()


def _record(
    run_id: UUID,
    event_identity: str = "cve:CVE-2026-76460",
    *,
    lifecycle: str = "identified",
    **overrides: object,
) -> CandidateRecord:
    payload: dict[str, object] = {
        "candidate_id": candidate_identity(run_id, event_identity),
        "run_id": run_id,
        "event_identity": event_identity,
        "event_type": "cve",
        "rank": 1,
        "lifecycle": lifecycle,
        "evidence_ids": (),
        "source_urls": ("https://example.test/advisory",),
        "enrichment_state": "complete",
        "validation_state": "not_run",
        "publication_state": "not_published",
        "failure_reason": None,
        "retry_eligible": True,
        "attempts": 0,
    }
    payload.update(overrides)
    return CandidateRecord.model_validate(payload)


def test_candidate_identity_is_deterministic() -> None:
    run = uuid4()
    first = candidate_identity(run, "cve:CVE-2026-76460")
    second = candidate_identity(run, "cve:CVE-2026-76460")
    other_run = candidate_identity(uuid4(), "cve:CVE-2026-76460")
    assert first == second
    assert first != other_run


@pytest.mark.asyncio
async def test_repeated_upsert_is_idempotent(database) -> None:
    run_id = uuid4()
    repository = CandidateLedgerRepository()
    async with database.transaction() as session:
        await _ensure_run(session, run_id)
        await repository.upsert(
            session, _record(run_id, lifecycle="researching", attempts=1)
        )
    async with database.transaction() as session:
        await repository.upsert(
            session,
            _record(run_id, lifecycle="validated", attempts=2, retry_eligible=False),
        )
    async with database.session() as session:
        rows = (
            await session.scalars(
                select(PublicationCandidate).where(
                    PublicationCandidate.run_id == run_id
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].lifecycle == "validated"
        assert rows[0].attempts == 2
        assert rows[0].retry_eligible is False


@pytest.mark.asyncio
async def test_concurrent_upserts_do_not_duplicate(database) -> None:
    import asyncio

    run_id = uuid4()
    repository = CandidateLedgerRepository()
    async with database.transaction() as session:
        await _ensure_run(session, run_id)

    async def write() -> None:
        async with database.transaction() as session:
            await repository.upsert(
                session, _record(run_id, lifecycle="researching", attempts=1)
            )

    await asyncio.gather(write(), write())
    async with database.session() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(PublicationCandidate)
            .where(PublicationCandidate.run_id == run_id)
        )
        assert count == 1


def test_contract_rejects_unknown_lifecycle() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _record(uuid4(), lifecycle="published_twice")


@pytest.mark.asyncio
async def test_invalid_lifecycle_rejected_at_both_boundaries(database) -> None:
    from sqlalchemy.exc import IntegrityError

    from hermes_cti.db.models import PublicationCandidate as PC

    run_id = uuid4()
    repository = CandidateLedgerRepository()
    async with database.transaction() as session:
        await _ensure_run(session, run_id)
    bad = _record(run_id).model_copy(update={"lifecycle": "published_twice"})

    # Repository guard rejects it before any write.
    with pytest.raises(ValueError, match="unknown candidate lifecycle"):
        async with database.transaction() as session:
            await repository.upsert(session, bad)

    # A direct row insert is still rejected by the database check constraint.
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(
                PC(
                    candidate_id=candidate_identity(run_id, "cve:CVE-2026-76460"),
                    run_id=run_id,
                    event_identity="cve:CVE-2026-76460",
                    event_type="cve",
                    rank=1,
                    lifecycle="published_twice",
                )
            )
            await session.flush()


@pytest.mark.asyncio
async def test_failure_reason_is_bounded_and_recorded(database) -> None:
    run_id = uuid4()
    repository = CandidateLedgerRepository()
    long_reason = "missing evidence: " + ("x" * 5000)
    # model_copy(update=...) skips validation on purpose: the repository must
    # still keep the persisted column within its declared width.
    record = _record(run_id, lifecycle="blocked", retry_eligible=False).model_copy(
        update={"failure_reason": long_reason}
    )
    async with database.transaction() as session:
        await _ensure_run(session, run_id)
        await repository.upsert(session, record)
    async with database.session() as session:
        row = await session.scalar(
            select(PublicationCandidate).where(
                PublicationCandidate.candidate_id
                == candidate_identity(run_id, "cve:CVE-2026-76460")
            )
        )
        assert row is not None
        assert row.failure_reason is not None
        assert len(row.failure_reason) <= 1024
        assert row.retry_eligible is False


@pytest.mark.asyncio
async def test_ledger_summary_counts_by_lifecycle(database) -> None:
    run_id = uuid4()
    repository = CandidateLedgerRepository()
    plans = [
        ("cve:CVE-2026-000001", "published", False),
        ("cve:CVE-2026-000002", "blocked", False),
        ("cve:CVE-2026-000003", "identified", True),
        ("cve:CVE-2026-000004", "identified", True),
    ]
    async with database.transaction() as session:
        await _ensure_run(session, run_id)
        for index, (identity, lifecycle, retry) in enumerate(plans, start=1):
            await repository.upsert(
                session,
                _record(
                    run_id,
                    identity,
                    lifecycle=lifecycle,
                    rank=index,
                    retry_eligible=retry,
                ),
            )
    async with database.session() as session:
        summary = await repository.summary(session, run_id)
        assert summary.counts["identified"] == 2
        assert summary.counts["blocked"] == 1
        assert summary.counts["published"] == 1
        assert summary.total == 4
        assert summary.retry_eligible == 2
