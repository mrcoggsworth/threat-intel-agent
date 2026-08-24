"""Container-side operational checks; emits output only on failure."""
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
from datetime import UTC, datetime
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _request(url: str, token: str | None = None, host: str | None = None) -> tuple[int, dict[str, object] | None]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("X-Admin-Token", token)
    if host:
        request.add_header("Host", host)
    try:
        with urllib.request.urlopen(request, timeout=float(_env("HERMES_MONITOR_TIMEOUT_SECONDS", "5"))) as response:
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


def check() -> list[str]:
    failures: list[str] = []
    public_base = _env("HERMES_PUBLIC_BASE_URL", "http://proxy")
    private_base = _env("HERMES_PRIVATE_BASE_URL", public_base)
    private_host = os.environ.get("HERMES_PRIVATE_HOST")
    token_path = Path(_env("HERMES_ADMIN_TOKEN_FILE", "/run/secrets/hermes_admin_token"))
    token = token_path.read_text(encoding="utf-8").strip() if token_path.is_file() else ""
    live_status, _ = _request(f"{public_base}/health/live")
    if live_status != 200:
        failures.append("public liveness")
    ready_status, _ = _request(f"{private_base}/health/ready", token, private_host)
    if ready_status != 200:
        failures.append("private readiness")
    last_status, last_payload = _request(f"{private_base}/api/v1/ops/last-success", token, private_host)
    if last_status != 200:
        failures.append("last-success endpoint")
    else:
        last_age = _age(last_payload.get("last_success") if last_payload else None)
        if last_age is None or last_age > float(_env("HERMES_LAST_SUCCESS_MAX_AGE_SECONDS", "172800")):
            failures.append("last successful run stale")
    heartbeat = Path(_env("HERMES_HEARTBEAT_FILE", "/runtime/scheduler.heartbeat"))
    if not heartbeat.is_file() or time.time() - heartbeat.stat().st_mtime > float(
        _env("HERMES_HEARTBEAT_MAX_AGE_SECONDS", "120")
    ):
        failures.append("scheduler heartbeat stale")
    metadata = Path(_env("HERMES_BACKUP_METADATA_FILE", "/backups/latest.metadata"))
    if not metadata.is_file() or time.time() - metadata.stat().st_mtime > float(
        _env("HERMES_BACKUP_MAX_AGE_SECONDS", "172800")
    ):
        failures.append("backup stale")
    usage = shutil.disk_usage(_env("HERMES_DISK_PATH", "/"))
    if usage.used / usage.total >= float(_env("HERMES_DISK_USED_FRACTION", "0.85")):
        failures.append("disk threshold")
    cert_value = os.environ.get("HERMES_CERT_FILE")
    cert_path = Path(cert_value) if cert_value else None
    if cert_path is not None:
        try:
            cert = ssl._ssl._test_decode_cert(str(cert_path))
            expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)
            if (expires - datetime.now(UTC)).total_seconds() < float(
                _env("HERMES_CERT_MIN_REMAINING_SECONDS", "1209600")
            ):
                failures.append("certificate expiry")
        except (KeyError, OSError, ValueError):
            failures.append("certificate check")
    else:
        failures.append("certificate path not configured")
    return failures


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
