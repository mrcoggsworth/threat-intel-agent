"""Unit coverage for explicit ingestion run-health semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
from typer.testing import CliRunner

from hermes_cti.api.main import create_app
from hermes_cti.cli import database_commands
from hermes_cti.cli.main import app as cli_app
from hermes_cti.core.settings import Settings
from hermes_cti.db.models import IngestionRun
from hermes_cti.db.pipeline import DailyRunResult
from hermes_cti.db.run_status import summarize_run
from hermes_cti.models.contracts import RunStatus


def _run(
    *,
    status: RunStatus,
    completed_at: datetime | None,
    total_sources: int,
    successful_sources: int,
    failed_sources: int,
) -> IngestionRun:
    return IngestionRun(
        id=uuid4(),
        run_type="daily",
        idempotency_key=f"test:{uuid4()}",
        started_at=completed_at,
        completed_at=completed_at,
        status=status.value,
        triggering_origin="test",
        application_version="test",
        configuration_hash="a" * 64,
        total_sources=total_sources,
        successful_sources=successful_sources,
        failed_sources=failed_sources,
    )


def test_failed_partial_run_is_usable_but_not_full_success() -> None:
    run = _run(
        status=RunStatus.FAILED,
        completed_at=datetime(2026, 9, 6, 12, tzinfo=UTC),
        total_sources=3,
        successful_sources=2,
        failed_sources=1,
    )

    summary = summarize_run(run, kind="latest_usable")

    assert summary.kind == "latest_usable"
    assert summary.status is RunStatus.FAILED
    assert summary.successful_sources == 2
    assert summary.failed_sources == 1
    assert summary.limitations == ("1 source(s) failed", "source coverage is partial")


def test_empty_summary_is_explicitly_unavailable() -> None:
    summary = summarize_run(None, kind="latest_full_success")

    assert summary.kind == "latest_full_success"
    assert summary.run_id is None
    assert summary.status is None
    assert summary.limitations == ()


def test_daily_run_result_requires_full_coverage_for_success() -> None:
    full = DailyRunResult(
        acquired_lock=True,
        run_status=RunStatus.COMPLETED,
        total_sources=2,
        successful_sources=2,
    )
    partial = DailyRunResult(
        acquired_lock=True,
        run_status=RunStatus.FAILED,
        total_sources=2,
        successful_sources=1,
        failed_sources=1,
    )
    unusable = DailyRunResult(
        acquired_lock=True,
        run_status=RunStatus.FAILED,
        total_sources=2,
        failed_sources=2,
    )

    assert full.is_full_success
    assert full.is_usable
    assert not partial.is_full_success
    assert partial.is_usable
    assert not unusable.is_usable


def test_ops_run_status_is_private_and_explicit_when_database_is_unavailable() -> None:
    settings = Settings(
        admin_token=SecretStr("test-admin"),
        database_required=False,
    )

    with TestClient(create_app(settings=settings)) as client:
        response = client.get(
            "/api/v1/ops/run-status",
            headers={"X-Admin-Token": "test-admin"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "scope": "private",
        "latest_attempt": None,
        "latest_full_success": None,
        "latest_usable": None,
    }


def test_run_daily_cli_fails_for_failed_parent_run(monkeypatch) -> None:
    class FakeDatabase:
        def __init__(self, settings: Settings) -> None:
            pass

        async def dispose(self) -> None:
            pass

    class FakePipeline:
        def __init__(self, settings: Settings, database: FakeDatabase) -> None:
            pass

        async def run_once(self, *args: object, **kwargs: object) -> DailyRunResult:
            return DailyRunResult(
                acquired_lock=True,
                run_status=RunStatus.FAILED,
                total_sources=2,
                successful_sources=1,
                failed_sources=1,
                error_summary="1 source(s) failed",
            )

    monkeypatch.setattr(
        database_commands, "load_settings", lambda: Settings(database_required=False)
    )
    monkeypatch.setattr(
        database_commands, "load_source_registry", lambda path: object()
    )
    monkeypatch.setattr(database_commands, "Database", FakeDatabase)
    monkeypatch.setattr(database_commands, "DailyPipeline", FakePipeline)

    result = CliRunner().invoke(cli_app, ["db", "run-daily"])

    assert result.exit_code == 1
    assert "Daily run failed" in result.output
    assert "Daily run completed." not in result.output


def test_run_daily_cli_uses_distinct_lock_contention_exit(monkeypatch) -> None:
    class FakeDatabase:
        def __init__(self, settings: Settings) -> None:
            pass

        async def dispose(self) -> None:
            pass

    class FakePipeline:
        def __init__(self, settings: Settings, database: FakeDatabase) -> None:
            pass

        async def run_once(self, *args: object, **kwargs: object) -> DailyRunResult:
            return DailyRunResult(acquired_lock=False)

    monkeypatch.setattr(
        database_commands, "load_settings", lambda: Settings(database_required=False)
    )
    monkeypatch.setattr(
        database_commands, "load_source_registry", lambda path: object()
    )
    monkeypatch.setattr(database_commands, "Database", FakeDatabase)
    monkeypatch.setattr(database_commands, "DailyPipeline", FakePipeline)

    result = CliRunner().invoke(cli_app, ["db", "run-daily"])

    assert result.exit_code == 2
    assert "another scheduler holds the lock" in result.output
