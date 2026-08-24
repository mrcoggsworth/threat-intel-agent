"""Evidence coverage and publication-readiness validation for Phase 7."""

from __future__ import annotations

import re
from collections.abc import Iterable
from uuid import UUID

from hermes_cti.detections.generators import (
    compile_yara,
    convert_sigma,
    parse_sigma,
)
from hermes_cti.models.contracts import DetectionType, ReportState
from hermes_cti.reporting.contracts import (
    EvidenceCoverage,
    ReportBundle,
    ReportSection,
    ValidationManifest,
)

_STOPWORDS = {
    "about",
    "after",
    "against",
    "documented",
    "evidence",
    "from",
    "public",
    "reported",
    "that",
    "this",
    "with",
}
_FORBIDDEN_INTERNAL_CLAIMS = (
    "your environment",
    "your organization",
    "internal compromise",
    "home lab",
    "confirmed breach",
)


def _words(value: str) -> tuple[str, ...]:
    return tuple(
        word
        for word in re.findall(r"[a-z0-9][a-z0-9._-]+", value.casefold())
        if len(word) >= 5 and word not in _STOPWORDS
    )


def _all_evidence_ids(bundle: ReportBundle) -> set[UUID]:
    return {item.evidence_id for item in bundle.evidence}


def _iter_remediation_actions(bundle: ReportBundle) -> Iterable[str]:
    if bundle.remediation is None:
        return ()
    remediation = bundle.remediation
    return (
        *remediation.immediate_containment,
        *remediation.exposure_reduction,
        *remediation.patching,
        *remediation.configuration_changes,
        *remediation.credential_actions,
        *remediation.blocking_limitations,
        *remediation.evidence_preservation,
        *remediation.recovery,
        *remediation.verification,
        *remediation.rollback,
    )


class ReportValidator:
    """Validate evidence coverage before any report is persisted or published."""

    def validate_coverage(self, bundle: ReportBundle) -> EvidenceCoverage:
        evidence_ids = _all_evidence_ids(bundle)
        missing: list[ReportSection] = []
        if bundle.hunt is None:
            missing.append(ReportSection.THREAT_HUNTING)
        if bundle.remediation is None:
            missing.append(ReportSection.REMEDIATION)
        if not bundle.detections:
            missing.append(ReportSection.DETECTION_CONTENT)
        if not bundle.timeline:
            missing.append(ReportSection.TIMELINE)
        if not bundle.caveats:
            missing.append(ReportSection.CAVEATS)

        evidence_text = " ".join(item.statement for item in bundle.evidence).casefold()
        unsupported_claims = [
            phrase
            for phrase in _FORBIDDEN_INTERNAL_CLAIMS
            if phrase in bundle.headline.casefold()
        ]
        unsupported_claims.extend(
            word for word in _words(bundle.headline) if word not in evidence_text
        )
        if not set(bundle.headline_evidence_ids).issubset(evidence_ids):
            unsupported_claims.append("headline references unavailable evidence")

        unsupported_remediation: list[str] = []
        if bundle.remediation is not None:
            if not bundle.remediation.evidence_ids:
                unsupported_remediation.append("remediation has no supporting evidence")
            elif not set(bundle.remediation.evidence_ids).issubset(evidence_ids):
                unsupported_remediation.append(
                    "remediation references unavailable evidence"
                )
            unsupported_remediation.extend(
                action
                for action in _iter_remediation_actions(bundle)
                if not action.strip()
            )

        if bundle.hunt is not None and not set(bundle.hunt.evidence_ids).issubset(
            evidence_ids
        ):
            missing.append(ReportSection.THREAT_HUNTING)
        for artifact in bundle.detections:
            if not set(artifact.evidence_ids).issubset(evidence_ids):
                missing.append(ReportSection.DETECTION_CONTENT)
        covered_set = set(bundle.headline_evidence_ids)
        for ioc in bundle.iocs:
            covered_set.update(ioc.evidence_ids)
        for vulnerability in bundle.vulnerabilities:
            covered_set.update(vulnerability.evidence_ids)
        for mapping in bundle.attack_mappings:
            covered_set.update(mapping.source_document_ids)
        for artifact in bundle.detections:
            covered_set.update(artifact.evidence_ids)
        if bundle.hunt is not None:
            covered_set.update(bundle.hunt.evidence_ids)
        if bundle.remediation is not None:
            covered_set.update(bundle.remediation.evidence_ids)
        for timeline_event in bundle.timeline:
            covered_set.update(timeline_event.evidence_ids)
        for relationship in bundle.historical_relationships:
            covered_set.update(relationship.evidence_ids)
        covered = tuple(sorted(covered_set, key=str))
        return EvidenceCoverage(
            valid=not missing
            and not unsupported_claims
            and not unsupported_remediation,
            missing_sections=tuple(dict.fromkeys(missing)),
            unsupported_claims=tuple(dict.fromkeys(unsupported_claims)),
            unsupported_remediation=tuple(dict.fromkeys(unsupported_remediation)),
            covered_evidence_ids=covered,
        )

    def validate(self, bundle: ReportBundle) -> ValidationManifest:
        coverage = self.validate_coverage(bundle)
        for artifact in bundle.detections:
            if artifact.detection_type is DetectionType.SIGMA:
                parse_sigma(artifact.content)
                convert_sigma(
                    artifact.content,
                    backend="spl",
                    evidence_ids=artifact.evidence_ids,
                )
                convert_sigma(
                    artifact.content,
                    backend="kql",
                    evidence_ids=artifact.evidence_ids,
                )
            elif artifact.detection_type is DetectionType.YARA:
                compile_yara(artifact.content)
            elif (
                artifact.detection_type in {DetectionType.SPL, DetectionType.KQL}
                and not artifact.evidence_ids
            ):
                raise ValueError("query artifacts require evidence IDs")
        if not coverage.valid:
            raise ValueError(
                "report evidence coverage failed: "
                f"missing={coverage.missing_sections}, "
                f"claims={coverage.unsupported_claims}, "
                f"remediation={coverage.unsupported_remediation}"
            )
        if bundle.state is ReportState.PUBLISHED:
            raise ValueError("reports must be approved before publication")
        return ValidationManifest(
            valid=True,
            coverage=coverage,
            renderer_version="phase7-renderer-v1",
            application_version=bundle.application_version,
            model_identifier=bundle.model_identifier,
            prompt_version=bundle.prompt_version,
            skill_versions=bundle.skill_versions,
            evidence_ids=tuple(
                sorted((item.evidence_id for item in bundle.evidence), key=str)
            ),
            artifact_hashes=tuple(
                sorted(
                    (
                        item.artifact_hash
                        for item in bundle.detections
                        if item.artifact_hash
                    ),
                )
            ),
        )
