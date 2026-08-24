"""Offline tests for the Phase 0 application foundation."""

from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from hermes_cti import __version__
from hermes_cti.api.dependencies import get_readiness_checker
from hermes_cti.api.main import create_app
from hermes_cti.cli.main import app as cli_app
from hermes_cti.core.logging import JSONFormatter, SecretRedactor, configure_logging
from hermes_cti.core.settings import Settings, load_settings
from hermes_cti.db.readiness import ReadinessResult


class StubReadinessChecker:
    def __init__(self, result: ReadinessResult) -> None:
        self.result = result

    async def check(self) -> ReadinessResult:
        return self.result


def test_all_phase0_packages_import() -> None:
    import hermes_cti.api
    import hermes_cti.cli
    import hermes_cti.correlation
    import hermes_cti.db
    import hermes_cti.detections
    import hermes_cti.enrichment
    import hermes_cti.extraction
    import hermes_cti.ingestion
    import hermes_cti.models
    import hermes_cti.portal
    import hermes_cti.reporting

    assert hermes_cti.api


def test_application_factory_and_liveness() -> None:
    app = create_app(Settings(database_required=True))
    with TestClient(app) as client:
        response = client.get("/health/live", headers={"X-Request-ID": "test-run"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-run"


def test_readiness_healthy_path_uses_dependency_override() -> None:
    app = create_app(Settings(database_required=True))
    app.dependency_overrides[get_readiness_checker] = lambda: StubReadinessChecker(
        ReadinessResult(configuration="ok", database="ok")
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"configuration": "ok", "database": "ok"},
    }


def test_readiness_unhealthy_path_is_controlled() -> None:
    app = create_app(Settings(database_required=True))
    app.dependency_overrides[get_readiness_checker] = lambda: StubReadinessChecker(
        ReadinessResult(
            configuration="unavailable",
            database="not_configured",
            message="required database configuration is missing",
        )
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    assert "database" in response.json()["checks"]
    assert "password" not in response.text.lower()


def test_default_readiness_reports_missing_required_configuration() -> None:
    app = create_app(Settings(database_required=True))
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["configuration"] == "unavailable"


def test_version_endpoint_matches_package_version() -> None:
    with TestClient(create_app(Settings(database_required=False))) as client:
        response = client.get("/version")

    assert response.status_code == 200
    assert response.json()["version"] == __version__


def test_settings_yaml_and_environment_precedence(tmp_path, monkeypatch) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        "agent:\n  name: YAML Hermes\n  log_level: WARNING\n"
        "ingestion:\n  timeout_seconds: 7\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HERMES_MAX_CONCURRENCY", "11")

    settings = load_settings(config)

    assert settings.app_name == "YAML Hermes"
    assert settings.log_level == "DEBUG"
    assert settings.http_timeout_seconds == 7
    assert settings.max_concurrency == 11


def test_secret_values_are_redacted_from_settings_and_logs() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://user:super-secret-password@db/hermes",
        secret_key="another-secret-value",
    )
    representation = repr(settings) + str(settings)
    assert "super-secret-password" not in representation
    assert "another-secret-value" not in representation

    formatter = JSONFormatter(
        SecretRedactor(
            [
                settings.database_url.get_secret_value(),
                settings.secret_key.get_secret_value(),
            ]
        )
    )
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "connecting with password=another-secret-value url=%s",
        (settings.database_url.get_secret_value(),),
        None,
    )

    rendered = formatter.format(record)
    assert "super-secret-password" not in rendered
    assert "another-secret-value" not in rendered
    assert json.loads(rendered)["request_id"] == "-"


def test_configure_logging_uses_json_handler() -> None:
    configure_logging(Settings(database_required=False))
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)


def test_cli_version() -> None:
    result = CliRunner().invoke(cli_app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_cli_doctor_failure_is_actionable(monkeypatch) -> None:
    monkeypatch.delenv("HERMES_DATABASE_URL", raising=False)
    monkeypatch.setenv("HERMES_DATABASE_REQUIRED", "true")
    result = CliRunner().invoke(cli_app, ["doctor"])
    assert result.exit_code == 1
    assert "Hermes doctor: FAIL" in result.output
    assert "HERMES_DATABASE_URL" in result.output
