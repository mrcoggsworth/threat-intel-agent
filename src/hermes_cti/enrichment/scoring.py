"""Deterministic, explainable priority scoring for public vulnerabilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from hermes_cti.models.contracts import (
    Confidence,
    PriorityScore,
    ScoreComponent,
    Severity,
)


@dataclass(frozen=True, slots=True)
class ScoreInputs:
    """Evidence-backed inputs. Missing values contribute zero, never guesses."""

    known_exploited: bool | None = None
    cvss_score: float | None = None
    epss_score: float | None = None
    published_at: datetime | None = None
    modified_at: datetime | None = None
    affected_product_significance: float = 0.0
    source_reliability: float = 0.0
    independent_corroboration: int = 0
    evidence_ids: tuple[UUID, ...] = ()


def _bounded(value: float, maximum: float) -> float:
    return max(0.0, min(maximum, value))


def _severity(cvss_score: float | None) -> Severity:
    if cvss_score is None:
        return Severity.INFO
    if cvss_score >= 9.0:
        return Severity.CRITICAL
    if cvss_score >= 7.0:
        return Severity.HIGH
    if cvss_score >= 4.0:
        return Severity.MEDIUM
    if cvss_score > 0:
        return Severity.LOW
    return Severity.INFO


def _recency_factor(
    published_at: datetime | None,
    modified_at: datetime | None,
    now: datetime,
) -> float:
    candidate = modified_at or published_at
    if candidate is None:
        return 0.0
    timestamp = candidate.astimezone(UTC)
    age_days = max(0.0, (now.astimezone(UTC) - timestamp).total_seconds() / 86_400)
    return max(0.0, 1.0 - age_days / 365.0)


def calculate_priority_score(
    inputs: ScoreInputs,
    *,
    now: datetime | None = None,
    score_version: str = "phase5-v1",
) -> PriorityScore:
    """Return a score whose stored components exactly reproduce its total."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    exploitation = 25.0 if inputs.known_exploited is True else 0.0
    cvss = _bounded((inputs.cvss_score or 0.0) / 10.0 * 20.0, 20.0)
    epss = _bounded(inputs.epss_score or 0.0, 1.0) * 20.0
    recency = _recency_factor(inputs.published_at, inputs.modified_at, current) * 10.0
    product = _bounded(inputs.affected_product_significance, 1.0) * 10.0
    reliability = _bounded(inputs.source_reliability, 1.0) * 7.5
    corroboration = _bounded(inputs.independent_corroboration / 3.0, 1.0) * 7.5
    values = (
        (
            "exploitation_state",
            exploitation,
            25.0,
            "CISA or equivalent evidence marks exploitation.",
        ),
        ("cvss", cvss, 20.0, "Normalized CVSS base score."),
        ("epss", epss, 20.0, "EPSS probability from the provider response."),
        ("recency", recency, 10.0, "Publication or modification recency."),
        (
            "affected_product_significance",
            product,
            10.0,
            "Evidence-backed affected-product significance.",
        ),
        (
            "source_reliability",
            reliability,
            7.5,
            "Reliability of supporting public sources.",
        ),
        (
            "independent_corroboration",
            corroboration,
            7.5,
            "Independent corroborating public sources.",
        ),
    )
    components = tuple(
        ScoreComponent(
            name=name,
            value=round(value, 4),
            maximum=maximum,
            rationale=rationale,
            evidence_ids=inputs.evidence_ids,
        )
        for name, value, maximum, rationale in values
    )
    score = round(sum(component.value for component in components), 4)
    confidence = min(
        1.0,
        max(
            0.0,
            _bounded(inputs.source_reliability, 1.0) * 0.4
            + _bounded(inputs.independent_corroboration / 3.0, 1.0) * 0.3
            + (1.0 if inputs.known_exploited is not None else 0.25) * 0.3,
        ),
    )
    return PriorityScore(
        score_version=score_version,
        score=score,
        severity=_severity(inputs.cvss_score),
        confidence=Confidence.__metadata__[0](confidence) if False else confidence,
        components=components,
        evidence_ids=inputs.evidence_ids,
    )
