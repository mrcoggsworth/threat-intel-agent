"""Offline tests for monitor gating and deployment receipt invariants."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_recovery_gate_suppresses_healthy_and_enforces_cooldown(tmp_path: Path) -> None:
    gate_module = load_script("recovery_gate")
    evidence = tmp_path / "monitor-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "state": "healthy",
                "correlation_id": "corr-1",
            }
        )
    )
    gate = gate_module.RecoveryGate(tmp_path)
    assert not gate.evaluate(evidence).allowed
    evidence.write_text(
        json.dumps(
            {
                "event_id": "event-2",
                "state": "actionable_failure",
                "run_id": "run-2",
                "correlation_id": "corr-2",
            }
        )
    )
    decision = gate.evaluate(evidence)
    assert decision.allowed
    gate.complete(decision, outcome="completed")
    assert not gate.evaluate(evidence).allowed
    assert "cooldown" in gate.evaluate(evidence).reason
    events = (tmp_path / "recovery-events.jsonl").read_text().splitlines()
    assert {json.loads(line)["event"] for line in events} >= {
        "suppressed",
        "attempted",
        "completed",
    }


def test_deployment_receipt_is_secret_free_and_tamper_evident(tmp_path: Path) -> None:
    receipt_module = load_script("deployment_receipt")
    path = tmp_path / "receipts" / "deployment.json"
    receipt = receipt_module.create_receipt(
        path,
        artifact_reference="registry.example/hermes@sha256:" + "a" * 64,
        artifact_digest="sha256:" + "a" * 64,
        source_revision="b" * 40,
        migration_revision="0013",
        environment_checksum="c" * 64,
        approval_reference="change-123",
        approval_identity="operator@example.test",
        rollback_image="registry.example/hermes@sha256:" + "d" * 64,
        rollback_receipt="/state/receipts/prior.json",
        backup_metadata="/backups/latest.metadata",
        health_endpoint="https://ops.example.test/health/live",
        health_verified_at=datetime.now(UTC).isoformat(),
    )
    assert receipt_module.verify_receipt(receipt)
    assert path.stat().st_mode & 0o077 == 0
    assert "password" not in path.read_text().lower()
    tampered = json.loads(path.read_text())
    tampered["artifact"]["source_revision"] = "tampered"
    assert not receipt_module.verify_receipt(tampered)


def test_plan05_controls_are_present() -> None:
    jobs = json.loads(
        (ROOT / ".hermes/profiles/cti-maintainer/cron/jobs.json").read_text()
    )
    assert "cti-maintainer-approved-release" not in {job["id"] for job in jobs}
    assert "--insecure" not in (ROOT / "scripts/health-watchdog.sh").read_text()
    assert (
        "--insecure"
        not in (
            ROOT / ".hermes/profiles/cti-maintainer/scripts/health-watchdog.sh"
        ).read_text()
    )
    deployment = (ROOT / "scripts/deploy-approved.sh").read_text()
    assert "HERMES_MIGRATION_COMPATIBLE" in deployment
    assert "HERMES_ROLLBACK_RECEIPT" in deployment
    assert "deployment_receipt.py" in deployment
