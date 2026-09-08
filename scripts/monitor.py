"""Container-side operational checks and machine-readable monitor evidence."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

MonitorState = Literal[
    "healthy",
    "degraded",
    "actionable_failure",
    "stale_data",
    "unknown",
    "operator_required",
]


@dataclass(frozen=True)
class MonitorSignal:
    """One observable check with recovery-relevant context."""

    name: str
    state: MonitorState
    observed_at: str
    endpoint: str | None = None
    observed_status: int | None = None
    run_id: str | None = None
    correlation_id: str | None = None
    detail: str | None = None


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _request(
    url: str, token: str | None = None, host: str | None = None
) -> tuple[int, dict[str, Any] | None]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("X-Admin-Token", token)
    if host:
        request.add_header("Host", host)
    context: ssl.SSLContext | None = None
    if url.startswith("https://"):
        context = ssl.create_default_context(
            cafile=os.environ.get("HERMES_TLS_CA_FILE") or None
        )
    try:
        with urllib.request.urlopen(
            request,
            timeout=float(_env("HERMES_MONITOR_TIMEOUT_SECONDS", "5")),
            context=context,
        ) as response:
            payload = response.read(1_000_000)
            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                value = None
            return response.status, value if isinstance(value, dict) else None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except (OSError, ValueError):
        return 0, None


def _age(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return (datetime.now(UTC) - datetime.fromisoformat(value)).total_seconds()
    except ValueError:
        return None


def _signal(
    name: str,
    state: MonitorState,
    *,
    endpoint: str | None,
    observed_status: int | None,
    run_id: str | None,
    correlation_id: str,
    detail: str | None = None,
) -> MonitorSignal:
    return MonitorSignal(
        name=name,
        state=state,
        observed_at=datetime.now(UTC).isoformat(),
        endpoint=endpoint,
        observed_status=observed_status,
        run_id=run_id,
        correlation_id=correlation_id,
        detail=detail,
    )


def collect_snapshot() -> dict[str, Any]:
    """Collect evidence without invoking an agent or performing recovery."""

    failures: list[str] = []
    signals: list[MonitorSignal] = []
    public_base = _env("HERMES_PUBLIC_BASE_URL", "http://proxy")
    private_base = _env("HERMES_PRIVATE_BASE_URL", public_base)
    private_host = os.environ.get("HERMES_PRIVATE_HOST")
    token_path = Path(
        _env("HERMES_ADMIN_TOKEN_FILE", "/run/secrets/hermes_admin_token")
    )
    try:
        token = (
            token_path.read_text(encoding="utf-8").strip()
            if token_path.is_file()
            else ""
        )
    except OSError:
        token = ""
    correlation_id = os.environ.get("HERMES_MONITOR_CORRELATION_ID", str(uuid4()))

    live_endpoint = f"{public_base}/health/live"
    live_status, _ = _request(live_endpoint)
    if live_status != 200:
        failures.append("public liveness")
        signals.append(
            _signal(
                "public_liveness",
                "unknown" if live_status == 0 else "operator_required",
                endpoint=live_endpoint,
                observed_status=live_status,
                run_id=None,
                correlation_id=correlation_id,
            )
        )

    ready_endpoint = f"{private_base}/health/ready"
    ready_status, _ = _request(ready_endpoint, token, private_host)
    if ready_status != 200:
        failures.append("private readiness")
        signals.append(
            _signal(
                "private_readiness",
                "unknown" if ready_status == 0 else "operator_required",
                endpoint=ready_endpoint,
                observed_status=ready_status,
                run_id=None,
                correlation_id=correlation_id,
            )
        )

    run_endpoint = f"{private_base}/api/v1/ops/run-status"
    run_status, run_payload = _request(run_endpoint, token, private_host)
    latest_attempt = run_payload.get("latest_attempt") if run_payload else None
    full_success = run_payload.get("latest_full_success") if run_payload else None
    run_id = latest_attempt.get("run_id") if isinstance(latest_attempt, dict) else None
    if run_status != 200:
        failures.append("run-status endpoint")
        signals.append(
            _signal(
                "run_status_endpoint",
                "unknown",
                endpoint=run_endpoint,
                observed_status=run_status,
                run_id=None,
                correlation_id=correlation_id,
            )
        )
    else:
        if not isinstance(full_success, dict):
            failures.append("no full-success run")
            signals.append(
                _signal(
                    "full_success_run",
                    "stale_data",
                    endpoint=run_endpoint,
                    observed_status=run_status,
                    run_id=run_id if isinstance(run_id, str) else None,
                    correlation_id=correlation_id,
                    detail="no latest_full_success projection",
                )
            )
        else:
            last_age = _age(full_success.get("completed_at"))
            if last_age is None or last_age > float(
                _env("HERMES_LAST_SUCCESS_MAX_AGE_SECONDS", "172800")
            ):
                failures.append("last successful run stale")
                signals.append(
                    _signal(
                        "full_success_freshness",
                        "stale_data",
                        endpoint=run_endpoint,
                        observed_status=run_status,
                        run_id=full_success.get("run_id"),
                        correlation_id=correlation_id,
                    )
                )
        if (
            isinstance(latest_attempt, dict)
            and latest_attempt.get("status") == "failed"
        ):
            failures.append("latest ingestion attempt failed")
            signals.append(
                _signal(
                    "latest_ingestion_attempt",
                    "actionable_failure",
                    endpoint=run_endpoint,
                    observed_status=run_status,
                    run_id=run_id if isinstance(run_id, str) else None,
                    correlation_id=correlation_id,
                    detail=latest_attempt.get("error_summary"),
                )
            )

    heartbeat = Path(_env("HERMES_HEARTBEAT_FILE", "/runtime/scheduler.heartbeat"))
    heartbeat_age = (
        time.time() - heartbeat.stat().st_mtime if heartbeat.is_file() else None
    )
    if heartbeat_age is None or heartbeat_age > float(
        _env("HERMES_HEARTBEAT_MAX_AGE_SECONDS", "120")
    ):
        failures.append("scheduler heartbeat stale")
        signals.append(
            _signal(
                "scheduler_heartbeat",
                "stale_data",
                endpoint=None,
                observed_status=None,
                run_id=run_id if isinstance(run_id, str) else None,
                correlation_id=correlation_id,
            )
        )

    metadata = Path(_env("HERMES_BACKUP_METADATA_FILE", "/backups/latest.metadata"))
    metadata_age = (
        time.time() - metadata.stat().st_mtime if metadata.is_file() else None
    )
    if metadata_age is None or metadata_age > float(
        _env("HERMES_BACKUP_MAX_AGE_SECONDS", "172800")
    ):
        failures.append("backup stale")
        signals.append(
            _signal(
                "backup_readiness",
                "operator_required",
                endpoint=None,
                observed_status=None,
                run_id=None,
                correlation_id=correlation_id,
            )
        )

    usage = shutil.disk_usage(_env("HERMES_DISK_PATH", "/"))
    if usage.used / usage.total >= float(_env("HERMES_DISK_USED_FRACTION", "0.85")):
        failures.append("disk threshold")
        signals.append(
            _signal(
                "disk_capacity",
                "operator_required",
                endpoint=None,
                observed_status=None,
                run_id=None,
                correlation_id=correlation_id,
            )
        )

    cert_value = os.environ.get("HERMES_CERT_FILE")
    if cert_value:
        try:
            cert = ssl._ssl._test_decode_cert(cert_value)
            expires = datetime.strptime(
                cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
            ).replace(tzinfo=UTC)
            if (expires - datetime.now(UTC)).total_seconds() < float(
                _env("HERMES_CERT_MIN_REMAINING_SECONDS", "1209600")
            ):
                failures.append("certificate expiry")
        except (KeyError, OSError, ValueError):
            failures.append("certificate check")
            signals.append(
                _signal(
                    "certificate_verification",
                    "operator_required",
                    endpoint=None,
                    observed_status=None,
                    run_id=None,
                    correlation_id=correlation_id,
                )
            )

    states = {signal.state for signal in signals}
    if not failures:
        state: MonitorState = "healthy"
    elif "unknown" in states:
        state = "unknown"
    elif "actionable_failure" in states:
        state = "actionable_failure"
    elif "stale_data" in states:
        state = "stale_data"
    else:
        state = "operator_required"
    return {
        "event_id": str(uuid4()),
        "observed_at": datetime.now(UTC).isoformat(),
        "state": state,
        "failures": failures,
        "run_id": run_id if isinstance(run_id, str) else None,
        "correlation_id": correlation_id,
        "signals": [asdict(signal) for signal in signals],
    }


def _persist_snapshot(snapshot: dict[str, Any]) -> None:
    evidence_file = Path(
        _env("HERMES_MONITOR_EVIDENCE_FILE", "/runtime/monitor-evidence.json")
    )
    event_log = Path(_env("HERMES_MONITOR_EVENT_LOG", "/runtime/monitor-events.jsonl"))
    try:
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = evidence_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(snapshot, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(evidence_file)
        with event_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(snapshot, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"hermes monitor evidence write failed: {exc}", file=sys.stderr)


def check() -> list[str]:
    """Return legacy failure labels while persisting richer evidence."""

    snapshot = collect_snapshot()
    _persist_snapshot(snapshot)
    return [str(failure) for failure in snapshot["failures"]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    while True:
        failures = check()
        if failures:
            print("hermes monitor failed: " + ", ".join(failures), file=sys.stderr)
            return 1
        if not args.loop:
            return 0
        time.sleep(float(_env("HERMES_MONITOR_INTERVAL_SECONDS", "60")))


if __name__ == "__main__":
    raise SystemExit(main())
