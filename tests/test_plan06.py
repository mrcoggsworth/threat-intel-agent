"""Disposable cross-profile and canary validation for reliability Plan 06."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from hermes_cti.analyst.contracts import CorpusQuery, CorpusResource
from hermes_cti.ingestion.http_client import FetchError, FetchResult
from hermes_cti.ingestion.service import IngestionService
from hermes_cti.ingestion.source_config import load_source_registry
from hermes_cti.models.contracts import RunStatus, SourceConfig, SourceRegistry

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "tests/fixtures/plan06_canary_manifest.json"


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"plan06_{name}", ROOT / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FixtureHTTPClient:
    """Small deterministic transport that exercises the real collector."""

    def __init__(self, failed_urls: set[str]) -> None:
        self.failed_urls = failed_urls

    async def fetch(
        self,
        url: str,
        *,
        request: Any,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> FetchResult:
        del request, headers, timeout_seconds, max_response_bytes
        if url in self.failed_urls:
            raise FetchError("fixture_failure", "fixture source failed", retry_count=1)
        body = (
            b'<rss version="2.0"><channel><title>Fixture</title>'
            b"<item><guid>fixture-1</guid><title>Fixture advisory</title>"
            b"<link>https://fixture.test/advisory</link>"
            b"<description>Safe fixture evidence.</description>"
            b"</item></channel></rss>"
        )
        return FetchResult(
            url=url,
            status_code=200,
            body=body,
            headers=(("content-type", "application/rss+xml"),),
            retry_count=0,
        )


def fixture_source(name: str, url: str) -> SourceConfig:
    return SourceConfig(
        name=name,
        type="rss",
        url=url,
        category="news",
        timeout_seconds=1,
        max_response_bytes=10_000,
    )


def collect_fixture_run(failed_urls: set[str]) -> Any:
    sources = (
        fixture_source("Good fixture", "https://fixture.test/good"),
        fixture_source("Second fixture", "https://fixture.test/second"),
    )
    service = IngestionService(http_client=FixtureHTTPClient(failed_urls))
    return asyncio.run(service.collect_once(SourceRegistry(sources=sources)))


def test_plan06_matrix_and_canary_contract_are_complete() -> None:
    record = json.loads(FIXTURE.read_text(encoding="utf-8"))
    objectives = record["objectives"]
    assert {item["id"] for item in objectives} == {
        "ingestion",
        "analyst",
        "profiles",
        "operations",
        "deployment",
        "canary",
    }
    assert all(
        item["entrypoint"]
        and item["fixture"]
        and item["expected_status"]
        and item["evidence"]
        for item in objectives
    )
    assert len(record["stop_triggers"]) >= 5
    assert record["rollback"] == {
        "required": True,
        "target": "last-verified-immutable-receipt",
        "retain_failed_evidence": True,
        "authorize_production": False,
    }


def test_ingestion_fixtures_preserve_full_partial_and_failed_semantics() -> None:
    registry = load_source_registry(ROOT / "config/sources.json")
    assert len(registry.sources) >= 39
    assert len({source.category for source in registry.sources}) == 8

    full = collect_fixture_run(set())
    assert full.manifest.status is RunStatus.COMPLETED
    assert full.manifest.successful_sources == 2
    assert len(full.source_documents) == 2
    assert all(document.canonical_url for document in full.source_documents)

    partial = collect_fixture_run({"https://fixture.test/second"})
    assert partial.manifest.status is RunStatus.FAILED
    assert partial.manifest.successful_sources == 1
    assert partial.manifest.failed_sources == 1
    assert partial.manifest.error_summary == "1 source(s) failed"
    assert len(partial.source_documents) == 1


def test_analyst_query_and_public_isolation_contracts_are_enforced() -> None:
    query = CorpusQuery(limit=100, published=True)
    query.validate_for(CorpusResource.CVES)
    with pytest.raises(ValueError):
        CorpusQuery(limit=101)
    with pytest.raises(ValueError):
        CorpusQuery(review_state="reviewed").validate_for(CorpusResource.CVES)

    from tests.test_phase8 import client

    public = client()
    assert public.get("/api/v1/public/corpus/cves").status_code == 404
    assert public.get("/api/v1/public/reports/private-draft").status_code == 404


def test_profile_reconciler_supports_dry_run_upgrade_repeat_and_protection(
    tmp_path: Path,
) -> None:
    installer = ROOT / "scripts/install-hermes-profiles.sh"
    runtime = tmp_path / "profiles"
    base = [
        str(installer),
        "--repo",
        str(ROOT),
        "--runtime-root",
        str(runtime),
        "--private-service-url",
        "https://ops.fixture.test",
        "--analyst-service-url",
        "https://analyst.fixture.test",
        "--model",
        "fixture-model",
        "--provider",
        "fixture-provider",
        "--no-cli",
        "--no-cron",
    ]
    dry = subprocess.run([*base, "--dry-run"], capture_output=True, text=True)
    assert dry.returncode == 0, dry.stderr
    assert not runtime.exists()

    first = subprocess.run(base, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    analyst = runtime / "cti-analyst"
    analyst_env = analyst / ".env"
    analyst_env.write_text("operator-secret-fixture\n", encoding="utf-8")
    (analyst / "operator-extension.md").write_text("preserve\n", encoding="utf-8")

    repeat = subprocess.run(
        [*base, "--model", "fixture-model-v2"], capture_output=True, text=True
    )
    assert repeat.returncode == 0, repeat.stderr
    assert analyst_env.read_text(encoding="utf-8") == "operator-secret-fixture\n"
    assert (analyst / "operator-extension.md").read_text(
        encoding="utf-8"
    ) == "preserve\n"
    for profile in ("cti-analyst", "cti-maintainer"):
        root = runtime / profile
        jobs = json.loads((root / "cron/jobs.json").read_text(encoding="utf-8"))
        assert jobs and all(job["profile"] == profile for job in jobs)
        materialized = "".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in root.rglob("*")
            if path.is_file()
        )
        assert "$USER" not in materialized
        assert "__SET_AND_PIN_" not in materialized


def test_monitor_recovery_and_cli_exit_codes_are_cross_profile_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monitor = load_script("monitor")
    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("alive\n", encoding="utf-8")
    backup = tmp_path / "backup.metadata"
    backup.write_text("backup-fixture\n", encoding="utf-8")
    for name, value in {
        "HERMES_PUBLIC_BASE_URL": "https://public.fixture.test",
        "HERMES_PRIVATE_BASE_URL": "https://private.fixture.test",
        "HERMES_HEARTBEAT_FILE": str(heartbeat),
        "HERMES_BACKUP_METADATA_FILE": str(backup),
        "HERMES_MONITOR_EVIDENCE_FILE": str(tmp_path / "monitor-evidence.json"),
        "HERMES_MONITOR_EVENT_LOG": str(tmp_path / "monitor-events.jsonl"),
        "HERMES_DISK_USED_FRACTION": "1.0",
    }.items():
        monkeypatch.setenv(name, value)

    current = datetime.now(UTC).isoformat()
    mode = {"status": "completed"}

    def request(
        url: str, token: str | None = None, host: str | None = None
    ) -> tuple[int, dict[str, Any]]:
        del token, host
        if url.endswith("/health/live") or url.endswith("/health/ready"):
            return 200, {}
        return 200, {
            "latest_attempt": {"run_id": "run-fixture", **mode},
            "latest_full_success": {"run_id": "full-fixture", "completed_at": current},
        }

    monkeypatch.setattr(monitor, "_request", request)
    healthy = monitor.collect_snapshot()
    assert healthy["state"] == "healthy"
    mode["status"] = "failed"
    actionable = monitor.collect_snapshot()
    assert actionable["state"] == "actionable_failure"
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(actionable), encoding="utf-8")

    gate_script = ROOT / "scripts/recovery_gate.py"
    healthy_evidence = tmp_path / "healthy.json"
    healthy_evidence.write_text(json.dumps({"event_id": "healthy", "state": "healthy"}))
    suppressed = subprocess.run(
        [
            sys.executable,
            str(gate_script),
            str(healthy_evidence),
            "--state-dir",
            str(tmp_path / "gate"),
        ],
        capture_output=True,
        text=True,
    )
    assert suppressed.returncode == 1
    allowed = subprocess.run(
        [
            sys.executable,
            str(gate_script),
            str(evidence),
            "--state-dir",
            str(tmp_path / "gate"),
        ],
        capture_output=True,
        text=True,
    )
    assert allowed.returncode == 0


def test_deployment_preflight_rejects_mutable_artifacts_and_receipts_verify(
    tmp_path: Path,
) -> None:
    receipt = load_script("deployment_receipt")
    rollback = tmp_path / "rollback.json"
    digest = "a" * 64
    receipt.create_receipt(
        rollback,
        artifact_reference=f"registry.fixture/hermes@sha256:{digest}",
        artifact_digest=f"sha256:{digest}",
        source_revision="b" * 40,
        migration_revision="0013",
        environment_checksum="c" * 64,
        approval_reference="fixture-change",
        approval_identity="fixture-operator",
        rollback_image=f"registry.fixture/hermes@sha256:{digest}",
        rollback_receipt="prior-fixture",
        backup_metadata="backup-fixture",
        health_endpoint="https://private.fixture.test/health/live",
        health_verified_at=datetime.now(UTC).isoformat(),
    )
    assert receipt.verify_receipt_file(rollback)
    env_file = tmp_path / "production.env"
    env_file.write_text("HERMES_FIXTURE=1\n", encoding="utf-8")
    checksum = __import__("hashlib").sha256(env_file.read_bytes()).hexdigest()
    environment = os.environ | {
        "HERMES_DEPLOY_APPROVED": "true",
        "HERMES_APPROVAL_REFERENCE": "fixture-change",
        "HERMES_APPROVAL_IDENTITY": "fixture-operator",
        "HERMES_IMAGE": "registry.fixture/hermes:mutable",
        "HERMES_SOURCE_REVISION": "b" * 40,
        "HERMES_MIGRATION_REVISION": "0013",
        "HERMES_ENV_CHECKSUM": checksum,
        "HERMES_BACKUP_METADATA_FILE": str(tmp_path / "backup.metadata"),
        "HERMES_ROLLBACK_IMAGE": f"registry.fixture/hermes@sha256:{digest}",
        "HERMES_ROLLBACK_RECEIPT": str(rollback),
        "HERMES_ENV_FILE": str(env_file),
    }
    blocked = subprocess.run(
        ["sh", str(ROOT / "scripts/deploy-approved.sh")],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert blocked.returncode == 2
    assert "immutable sha256 digest" in blocked.stderr
