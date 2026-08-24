"""Offline Phase 7 report, detection, rendering, and publication tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from hermes_cti.detections import (
    FileEvidence,
    SigmaFieldMatch,
    SigmaLogSource,
    SigmaRuleSpec,
)
from hermes_cti.detections.generators import (
    compile_yara,
    convert_sigma,
    generate_sigma,
    generate_yara,
    parse_sigma,
    query_artifact,
)
from hermes_cti.models.contracts import (
    DetectionType,
    Remediation,
    ReportState,
    Severity,
    ThreatHunt,
)
from hermes_cti.reporting import (
    ReportBundle,
    ReportEvidence,
    ReportEvidenceType,
    ReportPipeline,
    ReportRenderer,
    ReportSection,
    ReportTimelineEvent,
    ReportValidator,
)
from hermes_cti.reporting.contracts import RenderedReport

REPORT_ID = UUID("00000000-0000-0000-0000-000000000101")
VERSION_ID = UUID("00000000-0000-0000-0000-000000000102")
EVIDENCE_ID = UUID("00000000-0000-0000-0000-000000000103")


def _fixture() -> ReportBundle:
    evidence = ReportEvidence(
        evidence_id=EVIDENCE_ID,
        evidence_type=ReportEvidenceType.SOURCE_TEXT,
        statement="Public CVE-2027-1234 exploitation observed in a vendor advisory.",
        confidence=0.95,
    )
    sigma = generate_sigma(
        VERSION_ID,
        UUID("00000000-0000-0000-0000-000000000104"),
        SigmaRuleSpec(
            title="Public exploitation process execution",
            description="Detects the publicly documented process pattern.",
            logsource=SigmaLogSource(product="windows"),
            matches=(SigmaFieldMatch(field="process.command_line", value="rundll32"),),
        ),
        evidence_ids=(EVIDENCE_ID,),
    )
    yara = generate_yara(
        VERSION_ID,
        UUID("00000000-0000-0000-0000-000000000105"),
        FileEvidence(
            evidence_ids=(EVIDENCE_ID,),
            file_name="public-sample.bin",
            strings=("public-marker",),
            public_source="vendor advisory",
        ),
        rule_name="public_sample",
    )
    hunt = ThreatHunt(
        hunt_id=UUID("00000000-0000-0000-0000-000000000106"),
        report_version_id=VERSION_ID,
        objective="Find public exploitation telemetry.",
        scope="Publicly documented indicators and behavior.",
        platforms=("Windows",),
        telemetry_requirements=("process creation",),
        lookback="30 days",
        hypothesis="The documented process pattern may recur in public telemetry.",
        procedure=(
            "Search process creation telemetry.",
            "Review matching parent processes.",
        ),
        expected_evidence=("rundll32 process execution",),
        false_positives=("Administrative software",),
        escalation_criteria=("Repeated matching execution",),
        validation_checklist=("Confirm source and timestamp",),
        queries=("Template query",),
        evidence_ids=(EVIDENCE_ID,),
    )
    remediation = Remediation(
        remediation_id=UUID("00000000-0000-0000-0000-000000000107"),
        report_version_id=VERSION_ID,
        immediate_containment=("Restrict the publicly documented execution path.",),
        exposure_reduction=("Reduce exposure to the affected public service.",),
        patching=("Apply the vendor remediation for CVE-2027-1234.",),
        configuration_changes=("Review the documented configuration control.",),
        credential_actions=("Review credentials only if public evidence supports it.",),
        blocking_limitations=("IOC blocking does not replace patching.",),
        evidence_preservation=(
            "Preserve relevant public-source context and timestamps.",
        ),
        recovery=("Restore validated service configuration.",),
        verification=("Confirm the vendor remediation is applied.",),
        rollback=("Use the documented vendor rollback procedure.",),
        evidence_ids=(EVIDENCE_ID,),
        references=("https://example.com/advisory",),
    )
    timeline = ReportTimelineEvent(
        occurred_at=datetime(2027, 1, 2, tzinfo=UTC),
        label="Public advisory",
        description="Vendor advisory documented public exploitation.",
        evidence_ids=(EVIDENCE_ID,),
    )
    return ReportBundle(
        report_id=REPORT_ID,
        report_version_id=VERSION_ID,
        public_id="public-2027-1234",
        slug="public-cve-2027-1234",
        version=1,
        report_type="vulnerability",
        headline="Public CVE-2027-1234 exploitation observed",
        headline_evidence_ids=(EVIDENCE_ID,),
        executive_summary="Public evidence documents exploitation of CVE-2027-1234.",
        technical_analysis="The advisory describes a process execution pattern.",
        evidence_summary="The source is a public vendor advisory.",
        evidence=(evidence,),
        detections=(sigma, yara),
        hunt=hunt,
        remediation=remediation,
        timeline=(timeline,),
        confidence=0.9,
        severity=Severity.HIGH,
        caveats=(
            "This report describes public CTI and does not assess any organization.",
        ),
        state=ReportState.APPROVED,
        generated_by="deterministic-fixture",
        application_version="test",
    )


def test_complete_fixture_validates_with_separate_hunt_remediation_and_artifacts() -> (
    None
):
    bundle = _fixture()
    manifest = ReportValidator().validate(bundle)
    assert manifest.valid
    assert manifest.coverage.valid
    assert {item.detection_type for item in bundle.detections} == {
        DetectionType.SIGMA,
        DetectionType.YARA,
    }
    assert bundle.hunt is not None
    assert bundle.remediation is not None


def test_missing_required_sections_fail_validation() -> None:
    bundle = _fixture().model_copy(update={"hunt": None})
    coverage = ReportValidator().validate_coverage(bundle)
    assert ReportSection.THREAT_HUNTING in coverage.missing_sections
    with pytest.raises(ValueError, match="evidence coverage failed"):
        ReportValidator().validate(bundle)


def test_unsupported_headline_claim_fails_coverage() -> None:
    bundle = _fixture().model_copy(update={"headline": "Confirmed internal compromise"})
    coverage = ReportValidator().validate_coverage(bundle)
    assert coverage.unsupported_claims
    assert "internal compromise" in coverage.unsupported_claims


def test_unsupported_remediation_fails_coverage() -> None:
    remediation = _fixture().remediation
    assert remediation is not None
    bundle = _fixture().model_copy(
        update={"remediation": remediation.model_copy(update={"evidence_ids": ()})}
    )
    coverage = ReportValidator().validate_coverage(bundle)
    assert coverage.unsupported_remediation


def test_sigma_parsing_conversion_and_invalid_rejection() -> None:
    sigma = _fixture().detections[0]
    parsed = parse_sigma(sigma.content)
    result = convert_sigma(sigma.content, backend="spl")
    assert parsed.title == sigma.title
    assert result.converted[0].template
    with pytest.raises(ValueError):
        parse_sigma("title: [invalid")


def test_yara_compile_success_and_failure() -> None:
    yara = _fixture().detections[1]
    compiled = compile_yara(yara.content)
    assert compiled.valid
    with pytest.raises(ValueError):
        compile_yara("rule broken { condition: syntax error }")


def test_safe_rendering_escapes_malicious_values() -> None:
    bundle = _fixture().model_copy(update={"headline": "<script>alert(1)</script>"})
    rendered = ReportRenderer().render(bundle)
    assert "<script>" not in rendered.portal.content
    assert "&lt;script&gt;" in rendered.portal.content
    assert "<script>" not in rendered.markdown.content


def test_spl_and_kql_templates_are_explicit_and_separate() -> None:
    condition = SigmaFieldMatch(field="process_name", value='x" OR 1=1')
    for backend in ("spl", "kql"):
        artifact = query_artifact(
            VERSION_ID,
            uuid4(),
            __import__(
                "hermes_cti.detections.contracts", fromlist=["QuerySpec"]
            ).QuerySpec(
                backend=backend,
                title="Template query",
                platform="unknown",
                telemetry=("process",),
                fields=("process_name",),
                conditions=(condition,),
                template=True,
                evidence_ids=(EVIDENCE_ID,),
            ),
        )
        assert artifact.validation_result == "template"
        assert "1=1" in artifact.content


class _MemoryRepository:
    def __init__(self) -> None:
        self.calls = 0
        self.state = "published"

    async def persist_bundle(self, session, bundle, manifest, rendered, *, publish):
        self.calls += 1
        self.state = "published" if publish else bundle.state.value
        return object()


class _FailingRenderer(ReportRenderer):
    def render(self, bundle: ReportBundle) -> RenderedReport:
        raise RuntimeError("render failure")


@pytest.mark.asyncio
async def test_publication_render_failure_preserves_previous_publication() -> None:
    repository = _MemoryRepository()
    pipeline = ReportPipeline(repository=repository, renderer=_FailingRenderer())
    with pytest.raises(RuntimeError, match="render failure"):
        await pipeline.publish(None, _fixture())
    assert repository.calls == 0
    assert repository.state == "published"


def test_public_projection_excludes_non_published_records() -> None:
    from hermes_cti.db.models import Report

    published = Report(
        id=REPORT_ID,
        public_id="published",
        slug="published",
        headline="published",
        report_type="threat",
        severity="high",
        confidence=0.8,
        state="published",
        last_updated_at=datetime.now(UTC),
    )
    draft = Report(
        id=uuid4(),
        public_id="draft",
        slug="draft",
        headline="draft",
        report_type="threat",
        severity="high",
        confidence=0.8,
        state="draft",
        last_updated_at=datetime.now(UTC),
    )
    assert ReportPipeline.public_report_ids((draft, published)) == (REPORT_ID,)
