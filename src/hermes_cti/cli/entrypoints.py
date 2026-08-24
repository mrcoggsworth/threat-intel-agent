"""Explicit worker and dedicated scheduler process entrypoints."""

from __future__ import annotations

import asyncio

import typer

from hermes_cti.core.settings import load_settings
from hermes_cti.db.pipeline import DailyPipeline
from hermes_cti.db.scheduler import DailyScheduler
from hermes_cti.db.session import Database
from hermes_cti.ingestion.source_config import load_source_registry


def run_worker() -> None:
    """Report that model/enrichment workers are not part of Phase 4."""

    typer.echo("Hermes worker is reserved for a later analysis phase.")


def run_scheduler() -> None:
    """Run the independent timezone-aware daily scheduler process."""

    settings = load_settings()
    registry = load_source_registry()
    database = Database(settings)
    scheduler = DailyScheduler(
        settings,
        DailyPipeline(settings, database),
        registry,
    )
    try:
        asyncio.run(scheduler.run_forever())
    finally:
        asyncio.run(database.dispose())
