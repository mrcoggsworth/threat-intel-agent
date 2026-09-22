"""Offline unit tests for the hermes-cti analyst CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hermes_cti.cli.analyst_commands import _load_token
from hermes_cti.cli.main import app
from tests.test_phase7 import _fixture

runner = CliRunner()


def test_load_token_from_service_token_file_env(tmp_path: Path, monkeypatch) -> None:
    token_path = tmp_path / "service-token"
    token_path.write_text("profile-token\n", encoding="utf-8")
    monkeypatch.delenv("HERMES_ANALYST_TOKEN", raising=False)
    monkeypatch.setenv("HERMES_ANALYST_SERVICE_TOKEN_FILE", str(token_path))

    assert _load_token() == "profile-token"


def test_validate_bundle_success(tmp_path: Path) -> None:
    bundle = _fixture()
    bundle_path = tmp_path / "valid_bundle.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

    result = runner.invoke(app, ["analyst", "validate-bundle", str(bundle_path)])
    assert result.exit_code == 0, result.output
    assert (
        "[SUCCESS] ReportBundle passed all schema and publication gates!"
        in result.output
    )
    assert "Headline:" in result.output


def test_validate_bundle_invalid_json(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not json content", encoding="utf-8")

    result = runner.invoke(app, ["analyst", "validate-bundle", str(bad_path)])
    assert result.exit_code == 1
    assert "[FAILED] Invalid JSON" in result.output


def test_validate_bundle_unsupported_claim(tmp_path: Path) -> None:
    bundle = _fixture()
    data = json.loads(bundle.model_dump_json())
    data["headline"] = "Completely UnsupportedHeadline Injected"
    bad_path = tmp_path / "unsupported.json"
    bad_path.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(app, ["analyst", "validate-bundle", str(bad_path)])
    assert result.exit_code == 1
    assert "Evidence coverage validation failed" in result.output
    assert "unsupportedheadline" in result.output


def test_next_public_id_format() -> None:
    result = runner.invoke(app, ["analyst", "next-public-id", "--year", "2026"])
    assert result.exit_code == 0
    assert result.output.strip().startswith("PUB-2026-")


def test_analyst_health_command(tmp_path: Path) -> None:
    empty_cron = tmp_path / "cron"
    empty_cron.mkdir()
    result = runner.invoke(app, ["analyst", "health", "--cron-dir", str(empty_cron)])
    assert result.exit_code == 0
    assert "CTI-Hermes Analyst Health Diagnosis:" in result.output
    assert "Target Endpoint:" in result.output
