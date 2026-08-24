"""Phase 7 report validation, rendering, and publication orchestration."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.db.models import Report
from hermes_cti.models.contracts import ReportState
from hermes_cti.reporting.contracts import (
    RenderedReport,
    ReportBundle,
    ValidationManifest,
)
from hermes_cti.reporting.renderers import ReportRenderer
from hermes_cti.reporting.repository import ReportRepository
from hermes_cti.reporting.validation import ReportValidator


class ReportPersistence(Protocol):
    """Typed repository protocol for publication transaction tests."""

    async def persist_bundle(
        self,
        session: AsyncSession,
        bundle: ReportBundle,
        manifest: ValidationManifest | None,
        rendered: RenderedReport | None,
        *,
        publish: bool,
    ) -> object: ...


class ReportPipeline:
    """Keep validation and rendering complete before database mutation."""

    def __init__(
        self,
        *,
        validator: ReportValidator | None = None,
        renderer: ReportRenderer | None = None,
        repository: ReportPersistence | None = None,
    ) -> None:
        self.validator = validator or ReportValidator()
        self.renderer = renderer or ReportRenderer()
        self.repository = repository or ReportRepository()

    def validate(self, bundle: ReportBundle) -> ValidationManifest:
        return self.validator.validate(bundle)

    def render(self, bundle: ReportBundle) -> RenderedReport:
        return self.renderer.render(bundle)

    async def save_draft(self, session: AsyncSession, bundle: ReportBundle) -> object:
        if bundle.state is not ReportState.DRAFT:
            raise ValueError("save_draft requires draft state")
        return await self.repository.persist_bundle(
            session, bundle, None, None, publish=False
        )

    async def publish(self, session: AsyncSession, bundle: ReportBundle) -> object:
        """Publish an approved bundle after all validation/rendering succeeds.

        The caller must provide a transaction-scoped session. Rendering happens
        before repository mutation, and any persistence error propagates so the
        surrounding transaction can preserve the previous published version.
        """

        if bundle.state is not ReportState.APPROVED:
            raise ValueError("only approved reports may be published")
        manifest = self.validate(bundle)
        rendered = self.render(bundle)
        return await self.repository.persist_bundle(
            session, bundle, manifest, rendered, publish=True
        )

    @staticmethod
    def public_report_ids(reports: tuple[Report, ...]) -> tuple[UUID, ...]:
        """Stable helper for public projections without exposing drafts."""

        return tuple(
            sorted(
                (
                    report.id
                    for report in reports
                    if getattr(report, "state", None) == "published"
                ),
                key=str,
            )
        )
