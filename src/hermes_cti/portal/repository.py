"""Single-query-oriented portal read repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any, Protocol

from sqlalchemy import String, case, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from hermes_cti.db.models import Report, ReportVersion
from hermes_cti.models.contracts import ReportState, Severity
from hermes_cti.portal.contracts import (
    PortalQuery,
    ReportChangeState,
    ReportSort,
)


@dataclass(frozen=True, slots=True)
class ReportRow:
    """Typed database projection used by the portal service."""

    report: Report
    version: ReportVersion


@dataclass(frozen=True, slots=True)
class ReportPageRows:
    items: tuple[ReportRow, ...]
    total: int


class PortalReadRepository(Protocol):
    """Read boundary allowing deterministic offline portal tests."""

    async def list_reports(
        self, session: AsyncSession | None, query: PortalQuery
    ) -> ReportPageRows: ...

    async def get_report(
        self, session: AsyncSession | None, identifier: str
    ) -> ReportRow | None: ...

    async def list_drafts(
        self, session: AsyncSession | None, limit: int
    ) -> tuple[Report, ...]: ...


class SqlPortalReadRepository:
    """Published-only repository with bounded filters and no per-row queries."""

    @staticmethod
    def _base_query() -> Any:
        return (
            select(Report, ReportVersion)
            .join(ReportVersion, ReportVersion.id == Report.current_version_id)
            .where(Report.state == ReportState.PUBLISHED.value)
        )

    @classmethod
    def _filtered_query(cls, query: PortalQuery) -> Any:
        statement = cls._base_query()
        if query.search:
            term = f"%{query.search.strip()}%"
            statement = statement.where(
                or_(
                    Report.headline.ilike(term),
                    cast(ReportVersion.structured_content, String).ilike(term),
                )
            )
        if query.severities:
            statement = statement.where(
                Report.severity.in_([item.value for item in query.severities])
            )
        if query.confidence_min is not None:
            statement = statement.where(Report.confidence >= query.confidence_min)
        if query.date_from is not None:
            statement = statement.where(
                Report.last_updated_at
                >= datetime.combine(query.date_from, time.min, tzinfo=UTC)
            )
        if query.date_to is not None:
            statement = statement.where(
                Report.last_updated_at
                < datetime.combine(query.date_to, time.max, tzinfo=UTC)
            )
        if query.change_states:
            state_clauses: list[Any] = []
            for change_state in query.change_states:
                if change_state is ReportChangeState.RESURFACED:
                    state_clauses.append(Report.resurfaced.is_(True))
                elif change_state is ReportChangeState.NEW:
                    state_clauses.append(
                        Report.first_published_at == Report.last_updated_at
                    )
                else:
                    state_clauses.append(
                        Report.first_published_at.is_not(None)
                        & (Report.first_published_at != Report.last_updated_at)
                        & Report.resurfaced.is_(False)
                    )
            statement = statement.where(or_(*state_clauses))
        return statement

    @classmethod
    def _order_by(cls, query: PortalQuery) -> tuple[Any, ...]:
        if query.sort is ReportSort.NEWEST:
            return (desc(Report.first_published_at), desc(Report.id))
        if query.sort is ReportSort.CHANGED:
            return (desc(Report.last_updated_at), desc(Report.id))
        if query.sort is ReportSort.CONFIDENCE:
            return (desc(Report.confidence), desc(Report.last_updated_at), Report.id)
        if query.sort is ReportSort.SOURCES:
            # Source count is stored in the version JSON; keep this deterministic.
            source_count = func.jsonb_array_length(
                ReportVersion.structured_content["source_references"]
            )
            return (desc(source_count), desc(Report.last_updated_at), Report.id)
        severity_rank = case(
            (Report.severity == Severity.CRITICAL.value, 4),
            (Report.severity == Severity.HIGH.value, 3),
            (Report.severity == Severity.MEDIUM.value, 2),
            else_=1,
        )
        return (desc(severity_rank), desc(Report.last_updated_at), Report.id)

    async def list_reports(
        self, session: AsyncSession | None, query: PortalQuery
    ) -> ReportPageRows:
        if session is None:
            raise RuntimeError("database session is required")
        filtered = self._filtered_query(query)
        total = int(
            await session.scalar(select(func.count()).select_from(filtered.subquery()))
            or 0
        )
        result = await session.execute(
            filtered.order_by(*self._order_by(query))
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return ReportPageRows(
            items=tuple(
                ReportRow(report=row[0], version=row[1]) for row in result.all()
            ),
            total=total,
        )

    async def get_report(
        self, session: AsyncSession | None, identifier: str
    ) -> ReportRow | None:
        if session is None:
            raise RuntimeError("database session is required")
        result = await session.execute(
            self._base_query().where(
                or_(Report.slug == identifier, Report.public_id == identifier)
            )
        )
        row = result.first()
        return ReportRow(report=row[0], version=row[1]) if row else None

    async def list_drafts(
        self, session: AsyncSession | None, limit: int
    ) -> tuple[Report, ...]:
        if session is None:
            raise RuntimeError("database session is required")
        result = await session.execute(
            select(Report)
            .where(Report.state != ReportState.PUBLISHED.value)
            .order_by(desc(Report.last_updated_at), Report.id)
            .limit(limit)
        )
        return tuple(result.scalars().all())
