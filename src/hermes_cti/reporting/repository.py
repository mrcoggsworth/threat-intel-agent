"""Typed, idempotent Phase 7 report and artifact persistence."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti import __version__
from hermes_cti.db.entity_models import EntityEvidence
from hermes_cti.db.entity_repositories import EntityRepository
from hermes_cti.db.model_run_repository import ModelRunRepository
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
        pending_current_version_id: UUID | None = None
        if report is None:
            pending_current_version_id = bundle.report_version_id
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
                current_version_id=None,
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
                pending_current_version_id = bundle.report_version_id
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
        if pending_current_version_id is not None:
            report.current_version_id = pending_current_version_id

        await self._persist_provenance(session, bundle, report.id)

        if bundle.model_identifier is not None:
            await ModelRunRepository().persist(
                session,
                model_run_id=uuid5(bundle.report_version_id, "model-run"),
                purpose="report_generation",
                model_provider=bundle.model_identifier,
                prompt_name="report_generation",
                prompt_version=bundle.prompt_version or "unknown",
                skill_version_hashes=(
                    bundle.skill_version_hashes or bundle.skill_versions
                ),
                system_prompt_hash=bundle.system_prompt_hash,
                triggering_run_id=bundle.triggering_run_id,
                token_metadata=bundle.token_metadata,
                cost_metadata=bundle.cost_metadata,
                input_evidence_ids=tuple(item.evidence_id for item in bundle.evidence),
                output_hash=hashlib.sha256(bundle.stable_json().encode()).hexdigest(),
                started_at=now,
                completed_at=now,
            )

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
            publication_id = uuid5(bundle.report_version_id, "publication")
            if rendered is not None:
                artifact_hashes = (
                    rendered.markdown.artifact_hash,
                    rendered.json_artifact.artifact_hash,
                    rendered.portal.artifact_hash,
                    *(item.artifact_hash for item in rendered.downloads),
                )
                for index, artifact_hash in enumerate(artifact_hashes):
                    await session.execute(
                        insert(EntityEvidence)
                        .values(
                            id=uuid5(
                                publication_id, f"artifact:{index}:{artifact_hash}"
                            ),
                            entity_type="publication",
                            entity_id=publication_id,
                            evidence_span={"artifact_index": index},
                            origin_type="publication_renderer",
                            content_hash=artifact_hash,
                        )
                        .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
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
            for affected in vulnerability.affected_products:
                output.add(("product", affected.product.product_id, "affected_product"))
            output.add(
                (
                    "vulnerability",
                    vulnerability.vulnerability_id,
                    "vulnerability",
                )
            )
        for mapping in bundle.attack_mappings:
            output.add(("technique", mapping.mapping_id, "attack_mapping"))
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

    async def _persist_provenance(
        self, session: AsyncSession, bundle: ReportBundle, report_id: UUID
    ) -> None:
        """Persist source-backed links for reports and generated artifacts."""
        entity_repository = EntityRepository()
        evidence_by_id = {item.evidence_id: item for item in bundle.evidence}
        all_evidence_ids = tuple(evidence_by_id)

        async def link(
            entity_type: str,
            entity_id: UUID,
            evidence_ids: tuple[UUID, ...] = (),
            source_document_ids: tuple[UUID, ...] = (),
            content_hash: str | None = None,
            supporting_urls: tuple[str, ...] = (),
        ) -> None:
            links: set[tuple[UUID | None, UUID | None, tuple[str, ...]]] = set()
            for source_document_id in source_document_ids:
                links.add((source_document_id, None, ()))
            for evidence_id in evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    continue
                urls: list[str] = []
                if evidence.source_url is not None:
                    urls.append(str(evidence.source_url))
                if evidence.source_reference is not None:
                    urls.append(str(evidence.source_reference.canonical_url))
                links.add(
                    (evidence.source_document_id, evidence_id, tuple(sorted(set(urls))))
                )
            if supporting_urls:
                links.add((None, None, tuple(sorted(set(supporting_urls)))))
            if not links and content_hash is not None:
                links.add((None, None, ()))
            for index, (
                link_source_document_id,
                link_evidence_id,
                link_urls,
            ) in enumerate(sorted(links, key=str)):
                await session.execute(
                    insert(EntityEvidence)
                    .values(
                        id=uuid5(
                            entity_id,
                            f"report-provenance:{entity_type}:{index}:{link_evidence_id}:{link_source_document_id}",
                        ),
                        entity_type=entity_type,
                        entity_id=entity_id,
                        source_document_id=link_source_document_id,
                        evidence_claim_id=None,
                        evidence_span={"evidence_id": str(link_evidence_id)}
                        if link_evidence_id
                        else {},
                        confidence=evidence_by_id[link_evidence_id].confidence
                        if link_evidence_id
                        else 1.0,
                        origin_type="report_generation",
                        supporting_urls=list(link_urls) or None,
                        content_hash=content_hash,
                    )
                    .on_conflict_do_nothing(index_elements=[EntityEvidence.id])
                )

        await link(
            "report",
            report_id,
            all_evidence_ids,
            supporting_urls=tuple(
                str(item.canonical_url) for item in bundle.source_references
            ),
        )
        await link("report_version", bundle.report_version_id, all_evidence_ids)
        for vulnerability in bundle.vulnerabilities:
            await link(
                "vulnerability",
                vulnerability.vulnerability_id,
                vulnerability.evidence_ids,
            )
            for affected in vulnerability.affected_products:
                product = affected.product
                await entity_repository.upsert_product(
                    session,
                    entity_id=product.product_id,
                    vendor=product.vendor,
                    product=product.product,
                    normalized_vendor=product.normalized_vendor
                    or product.vendor.casefold(),
                    normalized_product=product.normalized_product
                    or product.product.casefold(),
                    ecosystem=product.ecosystem or "unknown",
                    product_type=product.product_type,
                    canonical_identifiers={
                        "values": list(product.canonical_identifiers)
                    },
                )
                await link("product", product.product_id, vulnerability.evidence_ids)
        for mapping in bundle.attack_mappings:
            await entity_repository.upsert_attack_technique(
                session,
                entity_id=mapping.mapping_id,
                attack_id=mapping.attack_id,
                framework_version=mapping.framework_version,
                name=mapping.name,
                tactic=mapping.tactic,
                platform=",".join(mapping.platforms) if mapping.platforms else None,
                description_reference=str(mapping.description_reference)
                if mapping.description_reference
                else None,
            )
            await link(
                "technique",
                mapping.mapping_id,
                source_document_ids=mapping.source_document_ids,
            )
        for artifact in bundle.detections:
            await link("detection", artifact.detection_id, artifact.evidence_ids)
        if bundle.hunt is not None:
            await link("hunt", bundle.hunt.hunt_id, bundle.hunt.evidence_ids)
        if bundle.remediation is not None:
            await link(
                "remediation",
                bundle.remediation.remediation_id,
                bundle.remediation.evidence_ids,
            )
        if bundle.historical_relationships:
            for item in bundle.historical_relationships:
                await link(
                    "relationship",
                    item.relationship.relationship_id,
                    item.evidence_ids or item.relationship.evidence_ids,
                )

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
