"""Deterministic historical correlation and guarded resurfacing services."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from hermes_cti.correlation.contracts import (
    AssessmentSnapshot,
    ContradictionEvidence,
    CorrelationCandidate,
    CorrelationEntity,
    CorrelationRelationship,
    CorrelationResult,
    ResurfacingEvent,
    ResurfacingReason,
    utc_now,
)
from hermes_cti.models.contracts import (
    EntityType,
    RelationshipOrigin,
    RelationshipProposal,
    ReviewState,
)

RULE_VERSION = "phase6-v1"
CANDIDATE_VERSION = "phase6-candidates-v1"


def _sorted_unique(values: Iterable[UUID]) -> tuple[UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _common(left: Iterable[str], right: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(left).intersection(right)))


def _stable_id(prefix: str, *values: object) -> UUID:
    return uuid5(NAMESPACE_URL, ":".join((prefix, *(str(value) for value in values))))


def _combined_evidence(
    left: CorrelationEntity, right: CorrelationEntity
) -> tuple[UUID, ...]:
    return _sorted_unique((*left.evidence_ids, *right.evidence_ids))


def _bounds(*entities: CorrelationEntity) -> tuple[datetime | None, datetime | None]:
    first = [item.first_seen_at for item in entities if item.first_seen_at is not None]
    last = [item.last_seen_at for item in entities if item.last_seen_at is not None]
    return (min(first) if first else None, max(last) if last else None)


def _overlap_or_near(left: CorrelationEntity, right: CorrelationEntity) -> bool:
    if left.first_seen_at is None or right.first_seen_at is None:
        return False
    left_last = left.last_seen_at or left.first_seen_at
    right_last = right.last_seen_at or right.first_seen_at
    return max(left.first_seen_at, right.first_seen_at) <= min(
        left_last, right_last
    ) + timedelta(days=180)


class CorrelationEngine:
    """Correlate public CTI using versioned, reproducible rules."""

    _exact_rules: tuple[tuple[str, str, str, float], ...] = (
        ("cve_ids", "same_cve", "exact_cve", 1.0),
        ("indicator_keys", "same_indicator", "normalized_indicator", 0.98),
        ("cpe_keys", "same_cpe", "exact_cpe", 0.97),
        ("product_keys", "same_product", "normalized_product", 0.94),
        ("attack_ids", "same_attack_technique", "exact_attack_id", 0.9),
        ("content_hashes", "same_content", "content_hash", 1.0),
        (
            "provider_identifiers",
            "same_provider_identifier",
            "provider_stable_identifier",
            0.96,
        ),
        (
            "validated_infrastructure_keys",
            "validated_infrastructure_reuse",
            "validated_infrastructure",
            0.88,
        ),
    )
    _candidate_fields: tuple[tuple[str, float], ...] = (
        ("infrastructure_keys", 0.72),
        ("malware_names", 0.7),
        ("tool_names", 0.68),
        ("campaign_names", 0.68),
        ("actor_aliases", 0.45),
        ("behaviors", 0.55),
        ("sectors", 0.4),
        ("geographies", 0.35),
    )

    def correlate(
        self,
        subject: CorrelationEntity,
        historical: Iterable[CorrelationEntity],
    ) -> CorrelationResult:
        relationships: list[CorrelationRelationship] = []
        candidates: list[CorrelationCandidate] = []
        historical_by_id = {
            (item.reference.entity_type, item.reference.entity_id): item
            for item in historical
        }
        historical_sorted = sorted(
            historical_by_id.values(),
            key=lambda item: (
                item.reference.entity_type.value,
                str(item.reference.entity_id),
            ),
        )
        for prior in historical_sorted:
            relationships.extend(self._exact_relationships(subject, prior))
            candidates.extend(self._candidates(subject, prior))
        contradictions = self.contradictions(subject, historical_sorted)
        relationships = sorted(
            relationships,
            key=lambda item: (str(item.relationship_id), item.origin_rule),
        )
        candidates = sorted(
            candidates,
            key=lambda item: (
                str(item.target.entity_id),
                item.candidate_type,
                str(item.candidate_id),
            ),
        )
        return CorrelationResult(
            relationships=tuple(relationships),
            candidates=tuple(candidates),
            contradictions=contradictions,
        )

    def _exact_relationships(
        self, subject: CorrelationEntity, prior: CorrelationEntity
    ) -> list[CorrelationRelationship]:
        relationships: list[CorrelationRelationship] = []
        for attribute, relationship_type, rule_name, confidence in self._exact_rules:
            common = _common(getattr(subject, attribute), getattr(prior, attribute))
            if not common:
                continue
            first, last = _bounds(subject, prior)
            rule = f"{rule_name}@{RULE_VERSION}"
            relationships.append(
                CorrelationRelationship(
                    relationship_id=_stable_id(
                        "relationship",
                        subject.reference.entity_id,
                        relationship_type,
                        prior.reference.entity_id,
                        rule,
                    ),
                    source=subject.reference,
                    relationship_type=relationship_type,
                    target=prior.reference,
                    origin="deterministic",
                    confidence=confidence,
                    first_seen_at=first,
                    last_seen_at=last,
                    review_state=ReviewState.REVIEWED,
                    origin_rule=rule,
                    justification=(
                        f"Exact public-CTI match on {attribute}: {', '.join(common)}."
                    ),
                    evidence_ids=_combined_evidence(subject, prior),
                )
            )
        return relationships

    def _candidates(
        self, subject: CorrelationEntity, prior: CorrelationEntity
    ) -> list[CorrelationCandidate]:
        candidates: list[CorrelationCandidate] = []
        for attribute, base_score in self._candidate_fields:
            common = _common(getattr(subject, attribute), getattr(prior, attribute))
            if not common:
                continue
            score = min(1.0, base_score + min(0.15, 0.03 * (len(common) - 1)))
            candidates.append(
                CorrelationCandidate(
                    candidate_id=_stable_id(
                        "candidate",
                        subject.reference.entity_id,
                        prior.reference.entity_id,
                        attribute,
                    ),
                    source=subject.reference,
                    target=prior.reference,
                    candidate_type=attribute.removesuffix("_names").removesuffix(
                        "_keys"
                    ),
                    score=score,
                    rationale=(
                        f"Candidate only: shared {attribute} {', '.join(common)}; "
                        "evidence review is required before a relationship "
                        "is established."
                    ),
                    evidence_ids=_combined_evidence(subject, prior),
                )
            )
        if _overlap_or_near(subject, prior):
            candidates.append(
                CorrelationCandidate(
                    candidate_id=_stable_id(
                        "candidate",
                        subject.reference.entity_id,
                        prior.reference.entity_id,
                        "temporal",
                    ),
                    source=subject.reference,
                    target=prior.reference,
                    candidate_type="temporal_relevance",
                    score=0.3,
                    rationale=(
                        "Candidate only: public observations overlap or are within "
                        "the temporal window."
                    ),
                    evidence_ids=_combined_evidence(subject, prior),
                )
            )
        for similarity in sorted(
            subject.semantic_similarities,
            key=lambda item: (str(item.candidate_reference.entity_id), item.score),
        ):
            if similarity.candidate_reference == prior.reference:
                candidates.append(
                    CorrelationCandidate(
                        candidate_id=_stable_id(
                            "candidate",
                            subject.reference.entity_id,
                            prior.reference.entity_id,
                            "semantic",
                        ),
                        source=subject.reference,
                        target=prior.reference,
                        candidate_type="semantic_similarity",
                        score=similarity.score,
                        rationale=(
                            "Candidate only: caller-supplied semantic similarity; "
                            "no relationship is asserted."
                        ),
                        evidence_ids=_sorted_unique(
                            (
                                *_combined_evidence(subject, prior),
                                *similarity.evidence_ids,
                            )
                        ),
                    )
                )
        return candidates

    def contradictions(
        self,
        subject: CorrelationEntity,
        historical: Iterable[CorrelationEntity] = (),
    ) -> tuple[ContradictionEvidence, ...]:
        groups: dict[str, dict[str, set[UUID]]] = {}
        for entity in (subject, *tuple(historical)):
            for assertion in entity.assertions:
                groups.setdefault(assertion.claim_key, {}).setdefault(
                    assertion.value, set()
                ).update(assertion.evidence_ids)
        output: list[ContradictionEvidence] = []
        for claim_key, values in sorted(groups.items()):
            if len(values) < 2:
                continue
            evidence = _sorted_unique(
                evidence_id
                for value_ids in values.values()
                for evidence_id in value_ids
            )
            output.append(
                ContradictionEvidence(
                    contradiction_id=_stable_id(
                        "contradiction",
                        subject.reference.entity_id,
                        claim_key,
                        *sorted(values),
                    ),
                    subject=subject.reference,
                    claim_key=claim_key,
                    observed_values=tuple(sorted(values)),
                    evidence_ids=evidence,
                    justification=(
                        f"Public evidence contains conflicting values for {claim_key}; "
                        "both assertions remain visible for review."
                    ),
                )
            )
        return tuple(output)


class ResurfacingDetector:
    """Create events only for material, evidence-backed changes."""

    def __init__(self, *, epss_delta: float = 0.1, cvss_delta: float = 1.0) -> None:
        if epss_delta <= 0 or cvss_delta <= 0:
            raise ValueError("resurfacing thresholds must be positive")
        self.epss_delta = epss_delta
        self.cvss_delta = cvss_delta

    def detect(
        self,
        previous: AssessmentSnapshot,
        current: AssessmentSnapshot,
        *,
        new_evidence_ids: tuple[UUID, ...] = (),
    ) -> ResurfacingEvent | None:
        if previous.entity != current.entity:
            raise ValueError("assessment versions must refer to the same entity")
        reasons: list[ResurfacingReason] = []
        if not previous.known_exploited and current.known_exploited:
            reasons.append(ResurfacingReason.KEV_ADDITION)
        if (
            previous.epss_score is not None
            and current.epss_score is not None
            and abs(current.epss_score - previous.epss_score) >= self.epss_delta
        ):
            reasons.append(ResurfacingReason.MATERIAL_EPSS_CHANGE)
        if (
            previous.cvss_score is not None
            and current.cvss_score is not None
            and abs(current.cvss_score - previous.cvss_score) >= self.cvss_delta
        ):
            reasons.append(ResurfacingReason.MATERIAL_CVSS_CHANGE)
        flags = (
            (
                current.active_exploitation_evidence,
                ResurfacingReason.ACTIVE_EXPLOITATION,
            ),
            (
                current.infrastructure_reactivated,
                ResurfacingReason.INFRASTRUCTURE_REACTIVATED,
            ),
            (
                current.independent_corroboration,
                ResurfacingReason.INDEPENDENT_CORROBORATION,
            ),
            (
                bool(
                    set(current.affected_product_keys)
                    - set(previous.affected_product_keys)
                ),
                ResurfacingReason.AFFECTED_SURFACE_EXPANDED,
            ),
            (current.attack_chain_completed, ResurfacingReason.ATTACK_CHAIN_COMPLETED),
            (current.coverage_obsolete, ResurfacingReason.COVERAGE_OBSOLETE),
        )
        reasons.extend(reason for enabled, reason in flags if enabled)
        evidence_ids = _sorted_unique((*new_evidence_ids, *current.evidence_ids))
        if not reasons:
            return None
        if not evidence_ids:
            raise ValueError("resurfacing requires new evidence IDs")
        reason_text = ", ".join(reason.value for reason in reasons)
        event_id = _stable_id(
            "resurfacing", previous.assessment_id, current.assessment_id, *reasons
        )
        return ResurfacingEvent(
            event_id=event_id,
            entity=current.entity,
            previous_assessment_id=previous.assessment_id,
            new_assessment_id=current.assessment_id,
            reasons=tuple(reasons),
            evidence_ids=evidence_ids,
            previous_score=previous.score,
            new_score=current.score,
            justification=(
                f"Historical public-CTI assessment resurfaced for: {reason_text}. "
                "The prior assessment remains queryable."
            ),
            created_at=utc_now(),
        )


class CorrelationService:
    """Application service boundary for correlation and proposal policy."""

    def __init__(
        self,
        engine: CorrelationEngine | None = None,
        resurfacing: ResurfacingDetector | None = None,
    ) -> None:
        self.engine = engine or CorrelationEngine()
        self.resurfacing = resurfacing or ResurfacingDetector()

    def correlate(
        self,
        subject: CorrelationEntity,
        historical: Iterable[CorrelationEntity],
    ) -> CorrelationResult:
        return self.engine.correlate(subject, historical)

    def resurface(
        self,
        previous: AssessmentSnapshot,
        current: AssessmentSnapshot,
        *,
        new_evidence_ids: tuple[UUID, ...] = (),
    ) -> ResurfacingEvent | None:
        return self.resurfacing.detect(
            previous, current, new_evidence_ids=new_evidence_ids
        )

    @staticmethod
    def validate_model_proposal(proposal: RelationshipProposal) -> RelationshipProposal:
        if proposal.origin is not RelationshipOrigin.MODEL_INFERENCE:
            raise ValueError(
                "controlled model proposal submission requires model_inference origin"
            )
        if proposal.review_state not in {ReviewState.PROPOSED, ReviewState.REVIEWED}:
            raise ValueError("model proposals must remain proposed or reviewed")
        actor_attribution = proposal.target.entity_type is EntityType.ACTOR and any(
            token in proposal.relationship_type.casefold()
            for token in ("attribut", "actor")
        )
        if actor_attribution:
            quality = getattr(proposal, "attribution_evidence_quality", None)
            if not proposal.evidence_ids or quality not in {
                "explicit_source",
                "corroborated_sources",
            }:
                raise ValueError(
                    "unsupported actor attribution: commodity tools, generic "
                    "techniques, geography, or weak IOC overlap are not sufficient"
                )
        return proposal

    def submit_model_proposal(
        self, proposal: RelationshipProposal
    ) -> RelationshipProposal:
        """Validate a proposal before the repository is allowed to persist it."""

        return self.validate_model_proposal(proposal)

    @staticmethod
    def public_projection(
        relationships: Iterable[CorrelationRelationship],
    ) -> tuple[CorrelationRelationship, ...]:
        """Return only reviewed relationships for a future public read-only surface."""

        return tuple(
            sorted(
                (
                    item
                    for item in relationships
                    if item.review_state is ReviewState.REVIEWED
                ),
                key=lambda item: (
                    str(item.source.entity_id),
                    str(item.target.entity_id),
                    item.relationship_type,
                ),
            )
        )
