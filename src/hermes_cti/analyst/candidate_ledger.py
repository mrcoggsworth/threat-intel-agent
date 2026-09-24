"""Repository boundary for the durable publication-candidate ledger.

The daily analyst execution records every qualifying event through this
repository so publication is gated per candidate: a blocked or deferred
candidate is isolated with its reason while valid candidates continue, and an
interrupted execution resumes from persisted lifecycle state without
duplicate submission. Identity is (run_id, event_identity); candidate_id is a
deterministic v5 UUID so repeated executions converge on one row.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.analyst.contracts import (
    CANDIDATE_LIFECYCLE_STATES,
    CandidateLedgerSummary,
    CandidateRecord,
)
from hermes_cti.db.models import PublicationCandidate

CANDIDATE_NAMESPACE = UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")
FAILURE_REASON_MAX_CHARS = 1024


def candidate_identity(run_id: UUID, event_identity: str) -> UUID:
    """Deterministic candidate ID for one event in one ingestion run."""
    return uuid5(CANDIDATE_NAMESPACE, f"candidate:{run_id}:{event_identity}")


class CandidateLedgerRepository:
    """Idempotent upsert and per-run accounting for publication candidates."""

    async def upsert(self, session: AsyncSession, record: CandidateRecord) -> None:
        if record.lifecycle not in CANDIDATE_LIFECYCLE_STATES:
            raise ValueError(f"unknown candidate lifecycle: {record.lifecycle}")
        expected_id = candidate_identity(record.run_id, record.event_identity)
        if record.candidate_id != expected_id:
            raise ValueError(
                "candidate_id must equal candidate_identity(run_id, event_identity)"
            )
        reason = record.failure_reason
        if reason is not None and len(reason) > FAILURE_REASON_MAX_CHARS:
            reason = reason[: FAILURE_REASON_MAX_CHARS - 1] + "…"
        await session.execute(
            insert(PublicationCandidate)
            .values(
                candidate_id=record.candidate_id,
                run_id=record.run_id,
                event_identity=record.event_identity,
                event_type=record.event_type,
                rank=record.rank,
                lifecycle=record.lifecycle,
                evidence_ids=[str(item) for item in record.evidence_ids],
                source_urls=list(record.source_urls),
                enrichment_state=record.enrichment_state,
                validation_state=record.validation_state,
                publication_state=record.publication_state,
                failure_reason=reason,
                published_public_id=record.published_public_id,
                retry_eligible=record.retry_eligible,
                attempts=record.attempts,
                report_id=record.report_id,
                report_version_id=record.report_version_id,
            )
            .on_conflict_do_update(
                index_elements=["run_id", "event_identity"],
                set_={
                    "event_type": record.event_type,
                    "rank": record.rank,
                    "lifecycle": record.lifecycle,
                    "evidence_ids": [str(item) for item in record.evidence_ids],
                    "source_urls": list(record.source_urls),
                    "enrichment_state": record.enrichment_state,
                    "validation_state": record.validation_state,
                    "publication_state": record.publication_state,
                    "failure_reason": reason,
                    "published_public_id": record.published_public_id,
                    "retry_eligible": record.retry_eligible,
                    "attempts": record.attempts,
                    "report_id": record.report_id,
                    "report_version_id": record.report_version_id,
                    "updated_at": func.now(),
                },
            )
        )

    async def list_for_run(
        self,
        session: AsyncSession,
        run_id: UUID,
        *,
        lifecycle: str | None = None,
        limit: int = 50,
    ) -> tuple[PublicationCandidate, ...]:
        statement = (
            select(PublicationCandidate)
            .where(PublicationCandidate.run_id == run_id)
            .order_by(PublicationCandidate.rank, PublicationCandidate.candidate_id)
            .limit(max(1, min(limit, 200)))
        )
        if lifecycle is not None:
            statement = statement.where(PublicationCandidate.lifecycle == lifecycle)
        return tuple((await session.scalars(statement)).all())

    async def summary(
        self, session: AsyncSession, run_id: UUID
    ) -> CandidateLedgerSummary:
        rows = (
            await session.execute(
                select(
                    PublicationCandidate.lifecycle,
                    func.count(),
                    func.count()
                    .filter(PublicationCandidate.retry_eligible.is_(True))
                    .label("retryable"),
                )
                .where(PublicationCandidate.run_id == run_id)
                .group_by(PublicationCandidate.lifecycle)
            )
        ).all()
        counts = {str(lifecycle): int(total) for lifecycle, total, _ in rows}
        published_ids = tuple(
            str(item)
            for item in (
                await session.scalars(
                    select(PublicationCandidate.published_public_id)
                    .where(
                        PublicationCandidate.run_id == run_id,
                        PublicationCandidate.lifecycle == "published",
                        PublicationCandidate.published_public_id.is_not(None),
                    )
                    .order_by(PublicationCandidate.rank)
                )
            ).all()
        )
        return CandidateLedgerSummary(
            run_id=run_id,
            total=sum(counts.values()),
            counts=dict(sorted(counts.items())),
            retry_eligible=sum(retryable for _, _, retryable in rows),
            published_ids=published_ids,
        )
