"""PostgreSQL persistence for Phase 6 correlation artifacts."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid5

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.correlation.contracts import (
    ContradictionEvidence,
    CorrelationCandidate,
    CorrelationRelationship,
    CorrelationResult,
    ResurfacingEvent,
)
from hermes_cti.db.models import (
    CorrelationCandidateRecord,
    CorrelationContradictionRecord,
    Relationship,
    RelationshipEvidence,
    ResurfacingEventRecord,
    RiskAssessment,
)
from hermes_cti.models.contracts import RelationshipProposal, ReviewState


class CorrelationRepository:
    """Idempotent persistence and public/private query boundary for Phase 6."""

    async def persist_result(
        self, session: AsyncSession, result: CorrelationResult
    ) -> None:
        for relationship in result.relationships:
            await self.persist_relationship(session, relationship)
        for candidate in result.candidates:
            await self.persist_candidate(session, candidate)
        for contradiction in result.contradictions:
            await self.persist_contradiction(session, contradiction)

    async def persist_relationship(
        self, session: AsyncSession, relationship: CorrelationRelationship
    ) -> Relationship:
        values = {
            "id": relationship.relationship_id,
            "source_entity_type": relationship.source.entity_type.value,
            "source_entity_id": relationship.source.entity_id,
            "relationship_type": relationship.relationship_type,
            "target_entity_type": relationship.target.entity_type.value,
            "target_entity_id": relationship.target.entity_id,
            "direction": relationship.direction,
            "origin": relationship.origin.value,
            "confidence": relationship.confidence,
            "first_seen_at": relationship.first_seen_at,
            "last_seen_at": relationship.last_seen_at,
            "active": relationship.active,
            "review_state": relationship.review_state.value,
            "supersedes_id": relationship.supersedes_id,
            "origin_rule": relationship.origin_rule,
            "justification": relationship.justification,
            "prompt_version": relationship.prompt_version,
            "model_identifier": relationship.model_identifier,
        }
        statement = (
            insert(Relationship)
            .values(values)
            .on_conflict_do_update(
                index_elements=[
                    Relationship.source_entity_type,
                    Relationship.source_entity_id,
                    Relationship.relationship_type,
                    Relationship.target_entity_type,
                    Relationship.target_entity_id,
                    Relationship.origin_rule,
                ],
                set_={
                    "last_seen_at": relationship.last_seen_at,
                    "confidence": relationship.confidence,
                    "justification": relationship.justification,
                    "active": relationship.active,
                    "review_state": relationship.review_state.value,
                },
            )
        )
        await session.execute(statement)
        record = await session.scalar(
            select(Relationship).where(Relationship.id == relationship.relationship_id)
        )
        if record is None:
            record = await session.scalar(
                select(Relationship).where(
                    Relationship.source_entity_id == relationship.source.entity_id,
                    Relationship.relationship_type == relationship.relationship_type,
                    Relationship.target_entity_id == relationship.target.entity_id,
                    Relationship.origin_rule == relationship.origin_rule,
                )
            )
        if record is None:
            raise RuntimeError("relationship was not persisted")
        for evidence_id in relationship.evidence_ids:
            evidence = insert(RelationshipEvidence).values(
                id=uuid5(relationship.relationship_id, f"evidence:{evidence_id}"),
                relationship_id=record.id,
                evidence_claim_id=evidence_id,
                evidence_role="supports",
                weight=1.0,
            )
            await session.execute(evidence.on_conflict_do_nothing())
        return cast(Relationship, record)

    async def persist_candidate(
        self, session: AsyncSession, candidate: CorrelationCandidate
    ) -> CorrelationCandidateRecord:
        values = {
            "id": candidate.candidate_id,
            "source_entity_type": candidate.source.entity_type.value,
            "source_entity_id": candidate.source.entity_id,
            "target_entity_type": candidate.target.entity_type.value,
            "target_entity_id": candidate.target.entity_id,
            "candidate_type": candidate.candidate_type,
            "score": candidate.score,
            "rationale": candidate.rationale,
            "evidence_ids": [str(item) for item in candidate.evidence_ids],
            "relationship_established": candidate.relationship_established,
        }
        await session.execute(
            insert(CorrelationCandidateRecord)
            .values(values)
            .on_conflict_do_update(
                index_elements=[
                    CorrelationCandidateRecord.source_entity_type,
                    CorrelationCandidateRecord.source_entity_id,
                    CorrelationCandidateRecord.target_entity_type,
                    CorrelationCandidateRecord.target_entity_id,
                    CorrelationCandidateRecord.candidate_type,
                ],
                set_={
                    "score": candidate.score,
                    "rationale": candidate.rationale,
                    "evidence_ids": values["evidence_ids"],
                    "relationship_established": False,
                },
            )
        )
        record = await session.scalar(
            select(CorrelationCandidateRecord).where(
                CorrelationCandidateRecord.id == candidate.candidate_id
            )
        )
        if record is None:
            raise RuntimeError("correlation candidate was not persisted")
        return record

    async def persist_contradiction(
        self, session: AsyncSession, contradiction: ContradictionEvidence
    ) -> CorrelationContradictionRecord:
        values = {
            "id": contradiction.contradiction_id,
            "subject_entity_type": contradiction.subject.entity_type.value,
            "subject_entity_id": contradiction.subject.entity_id,
            "claim_key": contradiction.claim_key,
            "observed_values": list(contradiction.observed_values),
            "evidence_ids": [str(item) for item in contradiction.evidence_ids],
            "justification": contradiction.justification,
        }
        await session.execute(
            insert(CorrelationContradictionRecord)
            .values(values)
            .on_conflict_do_update(
                index_elements=[
                    CorrelationContradictionRecord.subject_entity_type,
                    CorrelationContradictionRecord.subject_entity_id,
                    CorrelationContradictionRecord.claim_key,
                ],
                set_={
                    "observed_values": values["observed_values"],
                    "evidence_ids": values["evidence_ids"],
                    "justification": values["justification"],
                },
            )
        )
        record = await session.scalar(
            select(CorrelationContradictionRecord).where(
                CorrelationContradictionRecord.id == contradiction.contradiction_id
            )
        )
        if record is None:
            raise RuntimeError("contradiction was not persisted")
        return record

    async def persist_resurfacing(
        self, session: AsyncSession, event: ResurfacingEvent
    ) -> ResurfacingEventRecord:
        values = {
            "id": event.event_id,
            "entity_type": event.entity.entity_type.value,
            "entity_id": event.entity.entity_id,
            "previous_assessment_id": event.previous_assessment_id,
            "new_assessment_id": event.new_assessment_id,
            "reasons": [reason.value for reason in event.reasons],
            "evidence_ids": [str(item) for item in event.evidence_ids],
            "previous_score": event.previous_score,
            "new_score": event.new_score,
            "justification": event.justification,
            "review_state": event.review_state.value,
        }
        await session.execute(
            insert(ResurfacingEventRecord)
            .values(values)
            .on_conflict_do_nothing(
                index_elements=[
                    ResurfacingEventRecord.previous_assessment_id,
                    ResurfacingEventRecord.new_assessment_id,
                ]
            )
        )
        record = await session.scalar(
            select(ResurfacingEventRecord).where(
                ResurfacingEventRecord.id == event.event_id
            )
        )
        if record is None:
            record = await session.scalar(
                select(ResurfacingEventRecord).where(
                    ResurfacingEventRecord.previous_assessment_id
                    == event.previous_assessment_id,
                    ResurfacingEventRecord.new_assessment_id == event.new_assessment_id,
                )
            )
        if record is None:
            raise RuntimeError("resurfacing event was not persisted")
        return cast(ResurfacingEventRecord, record)

    async def persist_model_proposal(
        self, session: AsyncSession, proposal: RelationshipProposal
    ) -> Relationship:
        """Persist only after CorrelationService has applied proposal policy."""

        if proposal.origin.value != "model_inference":
            raise ValueError("repository accepts only model-inference proposals")
        origin_rule = f"model_proposal@phase6-v1:{proposal.proposal_id}"
        relationship = CorrelationRelationship(
            relationship_id=proposal.proposal_id,
            source=proposal.source,
            relationship_type=proposal.relationship_type,
            target=proposal.target,
            origin="model_inference",
            confidence=proposal.confidence,
            review_state=proposal.review_state,
            origin_rule=origin_rule,
            justification=proposal.justification,
            evidence_ids=proposal.evidence_ids,
            prompt_version=proposal.prompt_version,
            model_identifier=proposal.model_identifier,
        )
        return await self.persist_relationship(session, relationship)

    async def public_relationships(
        self, session: AsyncSession
    ) -> tuple[Relationship, ...]:
        result = await session.execute(
            select(Relationship)
            .where(
                Relationship.active.is_(True),
                Relationship.review_state == ReviewState.REVIEWED.value,
            )
            .order_by(
                Relationship.source_entity_type,
                Relationship.source_entity_id,
                Relationship.relationship_type,
                Relationship.target_entity_type,
                Relationship.target_entity_id,
            )
        )
        return tuple(result.scalars().all())

    async def assessment_history(
        self, session: AsyncSession, entity_type: str, entity_id: UUID
    ) -> tuple[RiskAssessment, ...]:
        result = await session.execute(
            select(RiskAssessment)
            .where(
                RiskAssessment.entity_type == entity_type,
                RiskAssessment.entity_id == entity_id,
            )
            .order_by(desc(RiskAssessment.assessment_version), RiskAssessment.id)
        )
        return tuple(result.scalars().all())
