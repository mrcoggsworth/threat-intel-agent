"""Typed, idempotent Phase 7 report and artifact persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti import __version__
from hermes_cti.db.models import (
    Detection,
    Hunt,
    Publication,
    Report,
    ReportEntity,
    ReportVersion,
)
from hermes_cti.db.models import (
    Remediation as RemediationRecord,
)
from hermes_cti.models.contracts import DetectionArtifact
from hermes_cti.reporting.contracts import (
    RenderedReport,
    ReportBundle,
    ValidationManifest,
)


class ReportRepository:
    """Persistence boundary for versioned reports and approved publication."""

    async def persist_bundle(
        self,
        session: AsyncSession,
        bundle: ReportBundle,
        manifest: ValidationManifest | None,
        rendered: RenderedReport | None,
        *,
        publish: bool,
    ) -> Report:
        report = await session.get(Report, bundle.report_id)
        if report is None:
            report = await session.scalar(
                select(Report).where(Report.public_id == bundle.public_id)
            )
        now = datetime.now(UTC)
        target_state = "published" if publish else bundle.state.value
        if report is None:
            report = Report(
                id=bundle.report_id,
                public_id=bundle.public_id,
                slug=bundle.slug,
                headline=bundle.headline,
                report_type=bundle.report_type,
                severity=bundle.severity.value,
                confidence=bundle.confidence,
                state=target_state,
                first_published_at=now if publish else None,
                last_updated_at=now,
                current_version_id=bundle.report_version_id,
                resurfaced=bundle.resurfaced,
            )
            session.add(report)
        else:
            report.headline = bundle.headline
            report.slug = bundle.slug
            report.last_updated_at = now
            report.resurfaced = bundle.resurfaced
            if publish:
                report.state = "published"
                report.first_published_at = report.first_published_at or now
                report.current_version_id = bundle.report_version_id
            elif report.state != "published":
                report.state = target_state

        structured = json.loads(bundle.stable_json())
        version = await session.scalar(
            select(ReportVersion).where(ReportVersion.id == bundle.report_version_id)
        )
        if version is None:
            version = ReportVersion(
                id=bundle.report_version_id,
                report_id=report.id,
                version=bundle.version,
                executive_summary=bundle.executive_summary,
                technical_analysis=bundle.technical_analysis,
                evidence_summary=bundle.evidence_summary,
                analytical_caveats=list(bundle.caveats),
                source_coverage=(
                    manifest.coverage.model_dump(mode="json") if manifest else {}
                ),
                generated_by=bundle.generated_by,
                model_identifier=bundle.model_identifier,
                prompt_version=bundle.prompt_version,
                validation_status="published" if publish else bundle.state.value,
                supersedes_id=bundle.supersedes_id,
                structured_content=structured,
                evidence_ids=[str(item.evidence_id) for item in bundle.evidence],
                artifact_manifest=(
                    {
                        "markdown": rendered.markdown.artifact_hash,
                        "json": rendered.json_artifact.artifact_hash,
                        "portal": rendered.portal.artifact_hash,
                        "downloads": [
                            item.artifact_hash for item in rendered.downloads
                        ],
                    }
                    if rendered
                    else {}
                ),
                skill_versions=list(bundle.skill_versions),
                application_version=bundle.application_version or __version__,
            )
            session.add(version)
        await session.flush()

        for entity_type, entity_id, role in self._entities(bundle):
            await session.execute(
                insert(ReportEntity)
                .values(
                    id=uuid5(
                        bundle.report_version_id,
                        f"entity:{entity_type}:{entity_id}:{role}",
                    ),
                    report_version_id=bundle.report_version_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    role=role,
                )
                .on_conflict_do_nothing()
            )
        if bundle.hunt is not None:
            await self._persist_hunt(session, bundle)
        if bundle.remediation is not None:
            await self._persist_remediation(session, bundle)
        for artifact in bundle.detections:
            await self._persist_detection(session, bundle.report_version_id, artifact)
        if publish:
            previous = await session.scalar(
                select(Publication)
                .join(ReportVersion, Publication.report_version_id == ReportVersion.id)
                .where(
                    ReportVersion.report_id == report.id,
                    Publication.state == "published",
                    Publication.report_version_id != bundle.report_version_id,
                )
                .order_by(desc(Publication.published_at))
                .limit(1)
            )
            await session.execute(
                insert(Publication)
                .values(
                    id=uuid5(bundle.report_version_id, "publication"),
                    report_version_id=bundle.report_version_id,
                    published_at=now,
                    publication_target="public_cti",
                    application_version=bundle.application_version,
                    validation_manifest=(
                        manifest.model_dump(mode="json") if manifest else {}
                    ),
                    rollback_target=previous.report_version_id if previous else None,
                    state="published",
                )
                .on_conflict_do_nothing()
            )
        await session.flush()
        return report

    @staticmethod
    def _entities(bundle: ReportBundle) -> tuple[tuple[str, UUID, str], ...]:
        output: set[tuple[str, UUID, str]] = set()
        for ioc in bundle.iocs:
            output.add(
                (ioc.indicator.entity_type.value, ioc.indicator.entity_id, "ioc")
            )
        for vulnerability in bundle.vulnerabilities:
            output.add(
                (
                    "vulnerability",
                    vulnerability.vulnerability_id,
                    "vulnerability",
                )
            )
        for relation in bundle.historical_relationships:
            output.add(
                (
                    relation.relationship.source.entity_type.value,
                    relation.relationship.source.entity_id,
                    "relationship_source",
                )
            )
            output.add(
                (
                    relation.relationship.target.entity_type.value,
                    relation.relationship.target.entity_id,
                    "relationship_target",
                )
            )
        return tuple(sorted(output, key=lambda item: (item[0], str(item[1]), item[2])))

    async def _persist_hunt(self, session: AsyncSession, bundle: ReportBundle) -> None:
        assert bundle.hunt is not None
        existing = await session.scalar(
            select(Hunt).where(Hunt.report_version_id == bundle.report_version_id)
        )
        if existing is None:
            session.add(
                Hunt(
                    id=bundle.hunt.hunt_id,
                    report_version_id=bundle.report_version_id,
                    objective=bundle.hunt.objective,
                    scope=bundle.hunt.scope,
                    platforms=list(bundle.hunt.platforms),
                    telemetry_requirements=list(bundle.hunt.telemetry_requirements),
                    lookback=bundle.hunt.lookback,
                    hypothesis=bundle.hunt.hypothesis,
                    procedure=list(bundle.hunt.procedure),
                    expected_evidence=list(bundle.hunt.expected_evidence),
                    false_positives=list(bundle.hunt.false_positives),
                    escalation_criteria=list(bundle.hunt.escalation_criteria),
                    validation_checklist=list(bundle.hunt.validation_checklist),
                    queries=list(bundle.hunt.queries),
                    evidence_ids=[str(item) for item in bundle.hunt.evidence_ids],
                    state=bundle.state.value,
                )
            )

    async def _persist_remediation(
        self, session: AsyncSession, bundle: ReportBundle
    ) -> None:
        assert bundle.remediation is not None
        existing = await session.scalar(
            select(RemediationRecord).where(
                RemediationRecord.report_version_id == bundle.report_version_id
            )
        )
        if existing is None:
            remediation = bundle.remediation
            session.add(
                RemediationRecord(
                    id=remediation.remediation_id,
                    report_version_id=bundle.report_version_id,
                    immediate_containment=list(remediation.immediate_containment),
                    exposure_reduction=list(remediation.exposure_reduction),
                    patching=list(remediation.patching),
                    configuration_changes=list(remediation.configuration_changes),
                    credential_actions=list(remediation.credential_actions),
                    blocking_limitations=list(remediation.blocking_limitations),
                    evidence_preservation=list(remediation.evidence_preservation),
                    recovery=list(remediation.recovery),
                    verification=list(remediation.verification),
                    rollback=list(remediation.rollback),
                    evidence_ids=[str(item) for item in remediation.evidence_ids],
                    references=[str(item) for item in remediation.references],
                    state=remediation.state.value,
                )
            )

    async def _persist_detection(
        self,
        session: AsyncSession,
        report_version_id: UUID,
        artifact: DetectionArtifact,
    ) -> None:
        existing = await session.scalar(
            select(Detection).where(Detection.id == artifact.detection_id)
        )
        if existing is None:
            session.add(
                Detection(
                    id=artifact.detection_id,
                    report_version_id=report_version_id,
                    detection_type=artifact.detection_type.value,
                    title=artifact.title,
                    content=artifact.content,
                    telemetry_requirements=list(artifact.telemetry_requirements),
                    assumptions=list(artifact.assumptions),
                    attack_references=list(artifact.attack_techniques),
                    evidence_ids=[str(item) for item in artifact.evidence_ids],
                    validation_tool=artifact.validation_tool,
                    validation_result=artifact.validation_result,
                    artifact_hash=artifact.artifact_hash,
                    state=artifact.state.value,
                )
            )

    async def version_history(
        self, session: AsyncSession, report_id: UUID
    ) -> tuple[ReportVersion, ...]:
        result = await session.execute(
            select(ReportVersion)
            .where(ReportVersion.report_id == report_id)
            .order_by(ReportVersion.version, ReportVersion.id)
        )
        return tuple(result.scalars().all())

    async def public_reports(self, session: AsyncSession) -> tuple[Report, ...]:
        result = await session.execute(
            select(Report)
            .where(Report.state == "published")
            .order_by(desc(Report.last_updated_at), Report.id)
        )
        return tuple(result.scalars().all())
