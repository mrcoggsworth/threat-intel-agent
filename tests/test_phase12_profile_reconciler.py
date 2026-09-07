"""Offline safety tests for the non-destructive Hermes profile reconciler."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "scripts/install-hermes-profiles.sh"


def run_installer(runtime_root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(INSTALLER),
            "--repo",
            str(ROOT),
            "--runtime-root",
            str(runtime_root),
            "--private-service-url",
            "https://ops.example.test",
            "--analyst-service-url",
            "https://analyst.example.test",
            "--model",
            "gpt-test",
            "--provider",
            "provider-test",
            "--no-cli",
            "--no-cron",
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_reconciler_materializes_jobs_and_resolves_runtime_values(
    tmp_path: Path,
) -> None:
    result = run_installer(tmp_path / "runtime")
    assert result.returncode == 0, result.stderr
    for profile in ("cti-analyst", "cti-maintainer"):
        root = tmp_path / "runtime" / profile
        jobs = json.loads((root / "cron/jobs.json").read_text())
        assert jobs
        assert all(job["profile"] == profile for job in jobs)
        assert all(job["workdir"] == str(ROOT) for job in jobs)
        assert all(job.get("model") == "gpt-test" for job in jobs if job.get("model"))
        assert all(
            job.get("provider") == "provider-test"
            for job in jobs
            if job.get("provider")
        )
        watchdog = (
            next(job for job in jobs if job["id"].endswith("health-watchdog"))
            if profile == "cti-maintainer"
            else None
        )
        if watchdog:
            assert watchdog["wakeAgent"] is False
            assert watchdog["preflight"] == "always"
        installed = "".join(
            path.read_text(errors="ignore")
            for path in root.rglob("*")
            if path.is_file()
        )
        assert "$USER" not in installed
        assert "__SET_AND_PIN_" not in installed
        assert "__INCIDENT_" not in installed
        assert (root / ".env").stat().st_mode & 0o777 == 0o600


def test_reconciler_preserves_runtime_state_and_repairs_managed_files(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    assert run_installer(runtime_root).returncode == 0
    analyst = runtime_root / "cti-analyst"
    protected = {
        ".env": "operator credential template\n",
        "sessions/session.json": "session\n",
        "logs/run.log": "log\n",
        "gateway/state": "gateway\n",
        "audit/events.jsonl": "audit\n",
        "memories/MEMORY.md": "operator memory\n",
    }
    for relative, value in protected.items():
        path = analyst / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    (analyst / "operator-extension.md").write_text("keep\n")
    (analyst / "prompts/daily-analysis.md").write_text("damaged\n")

    result = run_installer(runtime_root)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assets = {item["path"]: item for item in report["profiles"][0]["assets"]}
    assert assets["prompts/daily-analysis.md"]["action"] == "updated"
    assert assets[".env"]["action"] == "preserved"
    for relative, value in protected.items():
        assert (analyst / relative).read_text() == value
    assert (analyst / "operator-extension.md").read_text() == "keep\n"


def test_dry_run_and_symlink_escape_do_not_write(tmp_path: Path) -> None:
    dry_root = tmp_path / "dry"
    result = run_installer(dry_root, "--dry-run")
    assert result.returncode == 0, result.stderr
    assert not (dry_root / "cti-analyst").exists()
    assert json.loads(result.stdout)["status"] == "dry-run"

    link_root = tmp_path / "link"
    outside = tmp_path / "outside"
    outside.mkdir()
    link_root.mkdir()
    (link_root / "cti-analyst").symlink_to(outside, target_is_directory=True)
    result = run_installer(link_root)
    assert result.returncode != 0
    assert "symlink outside profile root" in result.stderr
    assert not (outside / "config.yaml").exists()


def test_replacement_is_explicit_and_recoverable(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    assert run_installer(runtime_root).returncode == 0
    analyst = runtime_root / "cti-analyst"
    (analyst / ".env").write_text("secret\n")
    result = run_installer(runtime_root, "--replace", "--yes")
    assert result.returncode == 0, result.stderr
    backups = list(runtime_root.glob("cti-analyst.replacement-backup.*"))
    assert len(backups) == 1
    assert (backups[0] / ".env").read_text() == "secret\n"
    assert (analyst / ".env").read_text() != "secret\n"


@pytest.mark.parametrize(
    "script", ("install-hermes-profiles.sh", "install-hermes-jobs.sh")
)
def test_installer_shell_syntax(script: str) -> None:
    command = ["bash", "-n", str(ROOT / "scripts" / script)]
    subprocess.run(command, check=True)
