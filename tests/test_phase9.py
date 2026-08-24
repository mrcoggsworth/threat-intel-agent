"""Offline Phase 9 deployment, secrets, and profile contract tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import SecretStr

from hermes_cti.api.main import create_app
from hermes_cti.core.settings import Settings, load_settings
from tests.test_phase8 import MemoryPortalService

ROOT = Path(__file__).parents[1]


def test_production_compose_has_private_topology_and_one_application_image() -> None:
    compose = yaml.safe_load((ROOT / "deploy/docker-compose.yml").read_text())
    services = compose["services"]
    assert set(services) >= {
        "proxy",
        "web",
        "worker",
        "scheduler",
        "postgres",
        "backup",
        "monitor",
    }
    assert services["web"]["image"].startswith("${HERMES_IMAGE")
    assert services["web"]["image"] == services["worker"]["image"]
    assert services["web"]["image"] == services["scheduler"]["image"]
    assert services["proxy"]["ports"] == ["80:80", "443:443"]
    for name in ("web", "worker", "scheduler", "postgres", "backup", "monitor"):
        assert "ports" not in services[name]
    assert compose["networks"]["backend"]["internal"] is True
    assert "docker.sock" not in (ROOT / "deploy/docker-compose.yml").read_text()


def test_production_dockerfile_is_multistage_and_non_root() -> None:
    dockerfile = (ROOT / "deploy/Dockerfile").read_text()
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "USER hermes" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile


@pytest.mark.parametrize(
    "script",
    (
        "scripts/backup-postgres.sh",
        "scripts/restore-verify.sh",
        "scripts/smoke-test.sh",
        "scripts/health-watchdog.sh",
        "scripts/deploy-approved.sh",
        "scripts/install-hermes-jobs.sh",
        "scripts/scheduler-entrypoint.sh",
    ),
)
def test_shell_scripts_parse(script: str) -> None:
    subprocess.run(["sh", "-n", str(ROOT / script)], check=True)


def test_runtime_secret_files_are_supported_without_committing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_file = tmp_path / "database-url"
    admin_file = tmp_path / "admin-token"
    database_file.write_text("postgresql+asyncpg://hermes:pw@postgres/hermes\n")
    admin_file.write_text("admin-token-value\n")
    monkeypatch.setenv("HERMES_DATABASE_URL_FILE", str(database_file))
    monkeypatch.setenv("HERMES_ADMIN_TOKEN_FILE", str(admin_file))
    monkeypatch.delenv("HERMES_DATABASE_URL", raising=False)
    monkeypatch.delenv("HERMES_ADMIN_TOKEN", raising=False)
    settings = load_settings(tmp_path / "missing.yaml")
    assert settings.database_url == SecretStr(
        "postgresql+asyncpg://hermes:pw@postgres/hermes"
    )
    assert settings.admin_token == SecretStr("admin-token-value")


def test_scheduler_heartbeat_is_private_and_safe(tmp_path: Path) -> None:
    heartbeat = tmp_path / "scheduler.heartbeat"
    heartbeat.write_text("2026-08-24T12:00:00Z\n")
    settings = Settings(
        admin_token=SecretStr("test-admin"),
        database_required=False,
        scheduler_heartbeat_file=str(heartbeat),
    )
    client = TestClient(
        create_app(settings=settings, portal_service=MemoryPortalService())
    )
    response = client.get(
        "/api/v1/ops/scheduler-heartbeat",
        headers={"X-Admin-Token": "test-admin"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "scope": "private",
        "heartbeat": "2026-08-24T12:00:00Z",
    }
    assert client.get("/api/v1/ops/scheduler-heartbeat").status_code == 404


def test_profiles_separate_governance_and_prompts_contain_no_secret_values() -> None:
    analyst = (ROOT / ".hermes/profiles/cti-analyst/SOUL.md").read_text()
    maintainer = (ROOT / ".hermes/profiles/cti-maintainer/SOUL.md").read_text()
    installer = (ROOT / "scripts/install-hermes-jobs.sh").read_text()
    assert "deployment state" in analyst
    assert "draft pull requests" in maintainer
    assert "cron add" in installer
    assert "jobs.json" in (ROOT / ".hermes/profiles/README.md").read_text()
    for path in (ROOT / ".hermes").rglob("*.md"):
        assert "postgresql+asyncpg://" not in path.read_text()
    assert "HERMES_ADMIN_TOKEN=" not in installer
