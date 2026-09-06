"""Shared construction of private ingestion-health projections."""

from __future__ import annotations

from typing import Literal

from hermes_cti.db.models import IngestionRun
from hermes_cti.models.contracts import RunHealthSummary

RunHealthKind = Literal["latest_attempt", "latest_full_success", "latest_usable"]


def summarize_run(run: IngestionRun | None, *, kind: RunHealthKind) -> RunHealthSummary:
    """Convert a persisted run into a typed, secret-free health projection."""

    if run is None:
        return RunHealthSummary(kind=kind)

    limitations: list[str] = []
    if run.failed_sources:
        limitations.append(f"{run.failed_sources} source(s) failed")
    if run.total_sources and run.successful_sources < run.total_sources:
        limitations.append("source coverage is partial")
    return RunHealthSummary(
        kind=kind,
        run_id=run.id,
        status=run.status,
        scheduled_for=run.scheduled_for,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_sources=run.total_sources,
        successful_sources=run.successful_sources,
        failed_sources=run.failed_sources,
        error_summary=run.error_summary,
        limitations=tuple(limitations),
    )
