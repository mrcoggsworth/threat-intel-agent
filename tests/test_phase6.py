"""Offline Phase 6 historical correlation and resurfacing tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from hermes_cti.correlation import (
    AssessmentSnapshot,
    CorrelationEntity,
    CorrelationService,
    EvidenceAssertion,
    ResurfacingDetector,
    ResurfacingReason,
)
from hermes_cti.correlation.contracts import CorrelationRelationship
from hermes_cti.correlation.engine import RULE_VERSION
from hermes_cti.models.contracts import (
    EntityReference,
    EntityType,
    RelationshipOrigin,
    RelationshipProposal,
    ReviewState,
    Severity,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def ref(entity_type: EntityType, value: str) -> EntityReference:
    return EntityReference(entity_type=entity_type, entity_id=UUID(value))


def entity(
    entity_type: EntityType,
    value: str,
    *,
    evidence: tuple[UUID, ...] = (),
    **fields: tuple[str, ...],
) -> CorrelationEntity:
    return CorrelationEntity(
        reference=ref(entity_type, value), evidence_ids=evidence, **fields
    )


def test_exact_cve_relationship_is_reproducible_and_duplicate_safe() -> None:
    evidence = (uuid4(), uuid4())
    subject = entity(
        EntityType.REPORT,
        "00000000-0000-0000-0000-000000000001",
        evidence=evidence[:1],
        cve_ids=("CVE-2026-1234",),
        content_hashes=("a" * 64,),
    )
    prior = entity(
        EntityType.VULNERABILITY,
        "00000000-0000-0000-0000-000000000002",
        evidence=evidence[1:],
        cve_ids=("CVE-2026-1234",),
        content_hashes=("a" * 64,),
    )
    service = CorrelationService()

    first = service.correlate(subject, (prior, prior))
    second = service.correlate(subject, (prior,))

    assert first == second
    assert len(first.relationships) == 2
    assert {item.origin_rule for item in first.relationships} == {
        f"exact_cve@{RULE_VERSION}",
        f"content_hash@{RULE_VERSION}",
    }
    assert all(
        item.evidence_ids == tuple(sorted(evidence, key=str))
        for item in first.relationships
    )


def test_weak_overlap_is_candidate_only_and_not_actor_attribution() -> None:
    actor = entity(
        EntityType.ACTOR,
        "00000000-0000-0000-0000-000000000010",
        actor_aliases=("Example Group",),
        evidence=(uuid4(),),
    )
    subject = entity(
        EntityType.REPORT,
        "00000000-0000-0000-0000-000000000011",
        tool_names=("Commodity Tool",),
        actor_aliases=("Example Group",),
        geographies=("US",),
        evidence=(uuid4(),),
    )
    result = CorrelationService().correlate(subject, (actor,))
    assert not result.relationships
    assert any(item.candidate_type == "actor_aliases" for item in result.candidates)
    assert all(not item.relationship_established for item in result.candidates)

    with pytest.raises(ValueError, match="actor attribution"):
        RelationshipProposal(
            proposal_id=uuid4(),
            source=subject.reference,
            relationship_type="attributed_to",
            target=actor.reference,
            origin=RelationshipOrigin.MODEL_INFERENCE,
            confidence=0.8,
            justification="The tool and geography overlap.",
            review_state=ReviewState.PROPOSED,
            evidence_ids=(),
        )


def test_contradiction_is_preserved() -> None:
    first_evidence, second_evidence = uuid4(), uuid4()
    subject = CorrelationEntity(
        reference=ref(EntityType.VULNERABILITY, "00000000-0000-0000-0000-000000000020"),
        evidence_ids=(first_evidence, second_evidence),
        assertions=(
            EvidenceAssertion(
                claim_key="exploitation_status",
                value="active",
                evidence_ids=(first_evidence,),
            ),
            EvidenceAssertion(
                claim_key="exploitation_status",
                value="not_observed",
                evidence_ids=(second_evidence,),
            ),
        ),
    )
    contradictions = CorrelationService().correlate(subject, ()).contradictions
    assert len(contradictions) == 1
    assert contradictions[0].observed_values == ("active", "not_observed")
    assert set(contradictions[0].evidence_ids) == {first_evidence, second_evidence}


def snapshot(
    assessment_id: str,
    version: int,
    *,
    score: float,
    evidence: tuple[UUID, ...],
    **kwargs: object,
) -> AssessmentSnapshot:
    return AssessmentSnapshot(
        assessment_id=UUID(assessment_id),
        entity=ref(EntityType.VULNERABILITY, "00000000-0000-0000-0000-000000000030"),
        assessment_version=version,
        score=score,
        severity=Severity.HIGH,
        confidence=0.7,
        epss_score=kwargs.pop("epss_score", 0.2),
        cvss_score=kwargs.pop("cvss_score", 6.0),
        evidence_ids=evidence,
        **kwargs,
    )


def test_resurfacing_links_prior_and_new_assessment_with_reasons() -> None:
    new_evidence = (uuid4(), uuid4())
    previous = snapshot(
        "00000000-0000-0000-0000-000000000040",
        1,
        score=40,
        evidence=(uuid4(),),
        known_exploited=False,
        affected_product_keys=("vendor/product",),
    )
    current = snapshot(
        "00000000-0000-0000-0000-000000000041",
        2,
        score=82,
        evidence=new_evidence[:1],
        known_exploited=True,
        epss_score=0.8,
        cvss_score=8.5,
        affected_product_keys=("vendor/product", "vendor/new-product"),
        active_exploitation_evidence=True,
    )

    event = ResurfacingDetector().detect(
        previous, current, new_evidence_ids=new_evidence
    )

    assert event is not None
    assert event.previous_assessment_id == previous.assessment_id
    assert event.new_assessment_id == current.assessment_id
    assert ResurfacingReason.KEV_ADDITION in event.reasons
    assert ResurfacingReason.MATERIAL_EPSS_CHANGE in event.reasons
    assert ResurfacingReason.MATERIAL_CVSS_CHANGE in event.reasons
    assert ResurfacingReason.ACTIVE_EXPLOITATION in event.reasons
    assert ResurfacingReason.AFFECTED_SURFACE_EXPANDED in event.reasons
    assert set(event.evidence_ids) == set(new_evidence)
    assert "prior assessment remains queryable" in event.justification


def test_model_proposal_stays_private_and_confidence_is_not_severity() -> None:
    proposal = RelationshipProposal(
        proposal_id=uuid4(),
        source=ref(EntityType.REPORT, "00000000-0000-0000-0000-000000000050"),
        relationship_type="uses_malware",
        target=ref(EntityType.MALWARE, "00000000-0000-0000-0000-000000000051"),
        origin=RelationshipOrigin.MODEL_INFERENCE,
        confidence=0.55,
        justification="A reviewed model lead based on public evidence.",
        review_state=ReviewState.PROPOSED,
        evidence_ids=(uuid4(),),
        prompt_version="phase6-test-prompt",
        model_identifier="test-model",
    )
    validated = CorrelationService().submit_model_proposal(proposal)
    relationship = CorrelationRelationship(
        relationship_id=validated.proposal_id,
        source=validated.source,
        relationship_type=validated.relationship_type,
        target=validated.target,
        origin="model_inference",
        confidence=validated.confidence,
        review_state=validated.review_state,
        origin_rule="model_proposal@phase6-v1",
        justification=validated.justification,
        evidence_ids=validated.evidence_ids,
    )
    assert CorrelationService.public_projection((relationship,)) == ()
    assert relationship.confidence == 0.55
    assert Severity.HIGH.value != str(relationship.confidence)
