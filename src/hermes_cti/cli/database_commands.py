"""Explicit database and daily-pipeline CLI commands."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid5

import typer
from pydantic import ValidationError

from hermes_cti.core.settings import load_settings
from hermes_cti.db.migrations import run_migrations
from hermes_cti.db.models import Vulnerability
from hermes_cti.db.pipeline import DailyPipeline
from hermes_cti.db.repositories import PersistenceRepository, RunRepository
from hermes_cti.db.session import Database
from hermes_cti.enrichment import EnrichmentCache, EnrichmentService, build_providers
from hermes_cti.ingestion.source_config import load_source_registry
from hermes_cti.models.contracts import SourceRegistry, normalize_cve_id

database_app = typer.Typer(help="Operate PostgreSQL persistence and scheduling.")


@database_app.command("migrate")
def migrate(
    revision: str = typer.Option("head", "--revision", help="Alembic revision."),
) -> None:
    """Apply database migrations explicitly."""

    try:
        run_migrations(load_settings(), revision)
    except (OSError, ValueError) as exc:
        typer.echo(f"Migration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Database migrated to {revision}")


@database_app.command("run-daily")
def run_daily(
    source_path: Path = typer.Option(  # noqa: B008
        "config/sources.json", "--sources", help="Authoritative source registry."
    ),
) -> None:
    """Run one lock-protected collection and persistence cycle."""

    settings = load_settings()
    registry = load_source_registry(source_path)
    database = Database(settings)

    async def execute() -> bool:
        try:
            result = await DailyPipeline(settings, database).run_once(registry)
            return result.acquired_lock
        finally:
            await database.dispose()

    if not asyncio.run(execute()):
        typer.echo("Daily run not started: another scheduler holds the lock.", err=True)
        raise typer.Exit(code=2)
    typer.echo("Daily run completed.")


@database_app.command("status")
def status() -> None:
    """Print last-successful and stale-run status as deterministic JSON."""

    settings = load_settings()
    database = Database(settings)

    async def query() -> dict[str, object]:
        async with database.session() as session:
            repository = RunRepository()
            last = await repository.last_successful(session)
            stale = await repository.stale_runs(
                session,
                older_than=datetime.now(UTC)
                - timedelta(seconds=settings.daily_run_stale_after_seconds),
            )
            return {
                "last_successful_run_id": str(last.id) if last else None,
                "last_successful_completed_at": (
                    last.completed_at.isoformat()
                    if last and last.completed_at
                    else None
                ),
                "stale_run_ids": [str(run.id) for run in stale],
            }

    try:
        payload = asyncio.run(query())
    finally:
        asyncio.run(database.dispose())
    typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":")))


@database_app.command("retry-failed")
def retry_failed(
    run_id: UUID = typer.Option(  # noqa: B008
        ..., "--run-id", help="Failed run identifier."
    ),
) -> None:
    """Retry failed sources in a new idempotent daily run."""

    settings = load_settings()
    registry = load_source_registry()
    database = Database(settings)

    async def execute() -> tuple[bool, int]:
        try:
            async with database.session() as session:
                failed_ids = await RunRepository().failed_source_ids(session, run_id)
            failed = tuple(
                source for source in registry.sources if source.source_id in failed_ids
            )
            if not failed:
                return True, 0
            result = await DailyPipeline(settings, database).run_once(
                SourceRegistry(sources=failed),
                idempotency_key=f"retry:{run_id}",
            )
            return result.acquired_lock, len(failed)
        finally:
            await database.dispose()

    acquired, count = asyncio.run(execute())
    if count == 0:
        typer.echo(f"No failed sources found for run {run_id}.")
    elif not acquired:
        typer.echo("Retry not started: another scheduler holds the lock.", err=True)
        raise typer.Exit(code=2)
    else:
        typer.echo(f"Retried {count} failed source(s) in a new run.")


@database_app.command("enrich")
def enrich(
    cve_ids: list[str] | None = typer.Option(  # noqa: B008
        None, "--cve", help="CVE identifier to enrich; may be repeated."
    ),
    record_ids: list[UUID] | None = typer.Option(  # noqa: B008
        None, "--record-id", help="Vulnerability UUID; may be repeated."
    ),
    run_ids: list[UUID] | None = typer.Option(  # noqa: B008
        None, "--run-id", help="Ingestion run UUID; may be repeated."
    ),
) -> None:
    """Enrich selected vulnerability records or CVEs with bounded providers."""
    if not cve_ids and not record_ids and not run_ids:
        typer.echo(
            "Enrichment failed: provide at least one --cve, --record-id, or --run-id",
            err=True,
        )
        raise typer.Exit(code=1)
    settings = load_settings()
    providers = build_providers(settings)
    service = EnrichmentService(
        providers,
        cache=EnrichmentCache(
            stale_if_error_seconds=settings.enrichment_stale_if_error_seconds
        ),
    )
    database = Database(settings)

    async def execute() -> list[dict[str, object]]:
        selected: dict[UUID, str] = {}
        for value in cve_ids or []:
            normalized = normalize_cve_id(value)
            identifier = uuid5(
                UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"),
                f"vulnerability:{normalized}",
            )
            selected[identifier] = normalized
        try:
            async with database.session() as session:
                for identifier in record_ids or []:
                    row = await session.get(Vulnerability, identifier)
                    if row is not None:
                        selected[identifier] = row.cve_id
                for run_id in run_ids or []:
                    for (
                        identifier,
                        cve_id,
                    ) in await RunRepository().vulnerability_ids_for_run(
                        session, run_id
                    ):
                        selected[identifier] = cve_id
            if not selected:
                raise ValueError("provide at least one --cve, --record-id, or --run-id")
            output: list[dict[str, object]] = []
            repository = PersistenceRepository()
            for identifier, cve_id in sorted(
                selected.items(), key=lambda item: item[1]
            ):
                result = await service.enrich_cve(cve_id, identifier)
                async with database.transaction() as session:
                    await repository.persist_enrichment_run(
                        session,
                        provider_responses=result.provider_results,
                        entity_type=result.entity.entity_type.value,
                        entity_id=result.entity.entity_id,
                        priority=result.priority,
                    )
                output.append(
                    {
                        "cve": cve_id,
                        "entity_id": str(identifier),
                        "status": result.status.value,
                        "score": result.priority.score if result.priority else None,
                        "providers": [
                            {
                                "provider": item.provider,
                                "status": item.status.value,
                                "error": (
                                    item.error_classification.value
                                    if item.error_classification
                                    else None
                                ),
                            }
                            for item in result.provider_results
                        ],
                    }
                )
            return output
        finally:
            for provider in providers:
                await provider.aclose()
            await database.dispose()

    try:
        payload = asyncio.run(execute())
    except (OSError, ValueError, ValidationError) as exc:
        typer.echo(f"Enrichment failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"enriched": payload}, sort_keys=True, separators=(",", ":")))
