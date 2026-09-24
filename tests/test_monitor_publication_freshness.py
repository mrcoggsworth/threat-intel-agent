"""Publication-freshness monitor signals (Task 4.3).

Ingestion freshness and publication freshness are distinct assertions: a
collection can be current while nothing publishes. These tests pin the
combined verdict: fresh public report => no signal; stale public report =>
stale_data incident; a durable blocked ledger reason downgrades the stale
feed to degraded (an explained state, not an incident); a pending or empty
ledger with no explanation remains stale_data. Secret-free by construction:
details carry public IDs and counts only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _fixture_env(
    monkeypatch,
    tmp_path: Path,
    *,
    reports_age_seconds: float,
    ledger: dict[str, Any] | None,
) -> Any:
    monitor = load_script("monitor")
    heartbeat = tmp_path / "heartbeat"
    heartbeat.write_text("alive\n", encoding="utf-8")
    backup = tmp_path / "backup.metadata"
    backup.write_text("backup-fixture\n", encoding="utf-8")
    token_file = tmp_path / "analyst-token"
    token_file.write_text("fixture-token\n", encoding="utf-8")
    for name, value in {
        "HERMES_PUBLIC_BASE_URL": "https://public.fixture.test",
        "HERMES_PRIVATE_BASE_URL": "https://private.fixture.test",
        "HERMES_HEARTBEAT_FILE": str(heartbeat),
        "HERMES_BACKUP_METADATA_FILE": str(backup),
        "HERMES_DISK_USED_FRACTION": "1.0",
        "HERMES_ANALYST_TOKEN_FILE": str(token_file),
        "HERMES_PUBLICATION_MAX_AGE_SECONDS": "345600",
        "HERMES_MONITOR_EVIDENCE_FILE": str(tmp_path / "evidence.json"),
        "HERMES_MONITOR_EVENT_LOG": str(tmp_path / "events.jsonl"),
    }.items():
        monkeypatch.setenv(name, value)

    now = datetime.now(UTC)
    newest_age = now - timedelta(seconds=reports_age_seconds)
    calls: dict[str, int] = {}

    def request(
        url: str, token: str | None = None, host: str | None = None
    ) -> tuple[int, dict[str, Any]]:
        if url.endswith("/health/live") or url.endswith("/health/ready"):
            return 200, {}
        if "/api/v1/public/reports" in url:
            return 200, {
                "items": [
                    {
                        "public_id": "PUB-2026-042",
                        "last_updated_at": newest_age.isoformat(),
                    }
                ]
            }
        if "/api/v1/ops/run-status" in url:
            calls["run-status"] = calls.get("run-status", 0) + 1
            return 200, {
                "latest_attempt": {"run_id": "run-fixture", "status": "completed"},
                "latest_full_success": {
                    "run_id": "run-fixture",
                    "completed_at": now.isoformat(),
                },
            }
        return 200, {}

    def request_headers(
        url: str, headers: dict[str, str], host: str | None = None
    ) -> tuple[int, dict[str, Any]]:
        assert headers.get("X-Analyst-Token") == "fixture-token"
        if "/api/v1/analyst/candidates" in url:
            return 200, ledger or {"total": 0, "counts": {}, "retry_eligible": 0}
        return 200, {}

    monkeypatch.setattr(monitor, "_request", request)
    monkeypatch.setattr(monitor, "_request_headers", request_headers)
    return monitor


def test_fresh_publication_emits_no_freshness_signal(
    monkeypatch, tmp_path: Path
) -> None:
    monitor = _fixture_env(
        monkeypatch,
        tmp_path,
        reports_age_seconds=3600,
        ledger={"total": 4, "counts": {"published": 4}, "retry_eligible": 0},
    )
    snapshot = monitor.collect_snapshot()
    assert snapshot["state"] == "healthy"
    assert "publication stale without explicit reason" not in snapshot["failures"]


def test_stale_publication_without_ledger_is_incident(
    monkeypatch, tmp_path: Path
) -> None:
    monitor = _fixture_env(
        monkeypatch,
        tmp_path,
        reports_age_seconds=8 * 86400,
        ledger={"total": 0, "counts": {}, "retry_eligible": 0},
    )
    snapshot = monitor.collect_snapshot()
    assert "publication stale without explicit reason" in snapshot["failures"]
    signal = next(
        item for item in snapshot["signals"] if item["name"] == "publication_freshness"
    )
    assert signal["state"] == "stale_data"
    assert "PUB-2026-042" in (signal["detail"] or "")
    # secret-free: the fixture token must never appear in evidence
    assert "fixture-token" not in json.dumps(snapshot)


def test_blocked_ledger_explains_stale_publication_as_degraded(
    monkeypatch, tmp_path: Path
) -> None:
    monitor = _fixture_env(
        monkeypatch,
        tmp_path,
        reports_age_seconds=8 * 86400,
        ledger={"total": 2, "counts": {"blocked": 2}, "retry_eligible": 0},
    )
    snapshot = monitor.collect_snapshot()
    assert "publication stale without explicit reason" not in snapshot["failures"]
    signal = next(
        item for item in snapshot["signals"] if item["name"] == "publication_freshness"
    )
    assert signal["state"] == "degraded"
    assert "blocked" in signal["detail"]


def test_pending_ledger_with_stale_publication_is_incident(
    monkeypatch, tmp_path: Path
) -> None:
    monitor = _fixture_env(
        monkeypatch,
        tmp_path,
        reports_age_seconds=8 * 86400,
        ledger={"total": 3, "counts": {"identified": 3}, "retry_eligible": 3},
    )
    snapshot = monitor.collect_snapshot()
    assert "publication stale without explicit reason" in snapshot["failures"]
