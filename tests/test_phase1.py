"""Offline contract and source-registry tests for Phase 1."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hermes_cti.cli.main import app as cli_app
from hermes_cti.ingestion.source_config import (
    SourceConfigurationError,
    load_source_registry,
    source_configuration_hash,
)
from hermes_cti.models import (
    DetectionArtifact,
    Indicator,
    IndicatorType,
    PublicIndicator,
    PublicReportSummary,
    ReportState,
    Severity,
    SourceConfig,
    SourceRegistry,
    Vulnerability,
)

TEST_UUID = UUID("00000000-0000-0000-0000-000000000001")
TEST_TIME = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _source(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "name": "Example Source",
        "type": "rss",
        "url": "https://example.com/feed",
        "category": "news",
    }
    source.update(overrides)
    return source


def test_current_source_registry_is_valid_and_backward_compatible() -> None:
    registry = load_source_registry()

    assert len(registry.sources) == 14
    assert registry.sources == tuple(
        sorted(registry.sources, key=lambda item: item.source_id)
    )
    assert all(source.enabled for source in registry.sources)
    assert all(source.timeout_seconds == 30 for source in registry.sources)
    assert all(source.max_response_bytes == 10_485_760 for source in registry.sources)
    assert registry.sources[0].source_type.value in {"rss", "json", "atom"}


@pytest.mark.parametrize(
    ("field", "value", "field_name"),
    [
        ("url", "not-a-url", "url"),
        ("timeout_seconds", 0, "timeout_seconds"),
        ("timeout_seconds", 301, "timeout_seconds"),
        ("max_response_bytes", 0, "max_response_bytes"),
        ("max_response_bytes", 104_857_601, "max_response_bytes"),
        ("category", "unknown", "category"),
        ("type", "unknown", "type"),
    ],
)
def test_invalid_source_fields_identify_file_source_and_field(
    tmp_path: Path, field: str, value: object, field_name: str
) -> None:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps([_source(**{field: value})]), encoding="utf-8")

    with pytest.raises(SourceConfigurationError) as raised:
        load_source_registry(path)

    message = str(raised.value)
    assert str(path) in message
    assert "Example Source" in message
    assert field_name in message


def test_secret_like_source_fields_are_rejected_without_echoing_value(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps([_source(adapter_settings={"api_key": "do-not-echo-this"})]),
        encoding="utf-8",
    )

    with pytest.raises(SourceConfigurationError) as raised:
        load_source_registry(path)

    message = str(raised.value)
    assert "secret-like" in message
    assert "api_key" in message
    assert "do-not-echo-this" not in message


@pytest.mark.parametrize(
    ("indicator_type", "value", "normalized"),
    [
        (IndicatorType.IPV4, "192.168.1.1", "192.168.1.1"),
        (IndicatorType.IPV6, "2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
        (IndicatorType.DOMAIN, "Example.COM.", "example.com"),
        (IndicatorType.MD5, "A" * 32, "a" * 32),
        (IndicatorType.SHA1, "B" * 40, "b" * 40),
        (IndicatorType.SHA256, "C" * 64, "c" * 64),
        (IndicatorType.CVE, "cve-2026-1234", "CVE-2026-1234"),
    ],
)
def test_indicator_normalization_is_type_specific(
    indicator_type: IndicatorType, value: str, normalized: str
) -> None:
    indicator = Indicator(
        indicator_id=TEST_UUID,
        indicator_type=indicator_type,
        value=value,
    )
    assert indicator.value == normalized
    assert indicator.normalized_value == normalized


@pytest.mark.parametrize(
    ("indicator_type", "value"),
    [
        (IndicatorType.IPV4, "999.1.1.1"),
        (IndicatorType.IPV6, "192.168.1.1"),
        (IndicatorType.MD5, "g" * 32),
        (IndicatorType.SHA1, "a" * 39),
        (IndicatorType.SHA256, "a" * 63),
        (IndicatorType.CVE, "CVE-26-1"),
    ],
)
def test_invalid_indicator_values_are_rejected(
    indicator_type: IndicatorType, value: str
) -> None:
    with pytest.raises(ValidationError):
        Indicator(indicator_id=TEST_UUID, indicator_type=indicator_type, value=value)


def test_cve_and_versioned_schema_round_trip() -> None:
    vulnerability = Vulnerability(
        vulnerability_id=TEST_UUID,
        cve_id=" cve-2026-12345 ",
        published_at=TEST_TIME,
        confidence=0.75,
    )

    payload = json.loads(vulnerability.stable_json())
    restored = Vulnerability.model_validate_json(vulnerability.stable_json())

    assert payload["schema_version"] == "1.0"
    assert payload["cve_id"] == "CVE-2026-12345"
    assert restored == vulnerability


def test_confidence_and_severity_are_separate_validated_fields() -> None:
    with pytest.raises(ValidationError):
        Vulnerability(
            vulnerability_id=TEST_UUID, cve_id="CVE-2026-1234", confidence=1.1
        )
    with pytest.raises(ValidationError):
        Vulnerability(
            vulnerability_id=TEST_UUID, cve_id="CVE-2026-1234", confidence=-0.1
        )

    vulnerability = Vulnerability(
        vulnerability_id=TEST_UUID,
        cve_id="CVE-2026-1234",
        confidence=0.2,
        severity=Severity.CRITICAL,
    )
    assert vulnerability.confidence == 0.2
    assert vulnerability.severity is Severity.CRITICAL


def test_stable_serialization_and_deterministic_source_order() -> None:
    first = SourceConfig(**_source(name="Zulu", tags=("b", "a")))
    second = SourceConfig(**_source(name="Alpha", tags=("a", "a")))
    registry = SourceRegistry(sources=(first, second))

    assert registry.sources[0].name == "Alpha"
    assert registry.sources[0].tags == ("a",)
    assert registry.stable_json() == registry.stable_json()
    assert source_configuration_hash(registry) == source_configuration_hash(registry)


def test_public_indicator_and_report_exclude_private_fields() -> None:
    assert not {"value", "normalized_value", "suppression_reason"}.intersection(
        PublicIndicator.model_fields
    )
    assert not {"report_id", "source_document_ids", "analytical_caveats"}.intersection(
        PublicReportSummary.model_fields
    )

    public = PublicReportSummary(
        public_id="r-1",
        slug="example-report",
        headline="Example public CTI report",
        severity=Severity.HIGH,
        confidence=0.8,
        state=ReportState.PUBLISHED,
        last_updated_at=TEST_TIME,
    )
    assert "analytical_caveats" not in public.stable_json()


def test_detection_artifact_hash_is_deterministic() -> None:
    artifact = DetectionArtifact(
        detection_id=TEST_UUID,
        report_version_id=UUID("00000000-0000-0000-0000-000000000002"),
        detection_type="sigma",
        title="Example",
        content="selection: {}",
    )
    assert len(artifact.artifact_hash or "") == 64
    assert (
        artifact.artifact_hash
        == DetectionArtifact(
            detection_id=TEST_UUID,
            report_version_id=UUID("00000000-0000-0000-0000-000000000002"),
            detection_type="sigma",
            title="Example",
            content="selection: {}",
        ).artifact_hash
    )


def test_cli_source_validation_success_and_failure(tmp_path: Path) -> None:
    runner = CliRunner()
    success = runner.invoke(cli_app, ["sources", "validate"])
    assert success.exit_code == 0
    assert "Validated 14 source configurations" in success.stdout

    invalid_path = tmp_path / "bad-sources.json"
    invalid_path.write_text(json.dumps([_source(type="unknown")]), encoding="utf-8")
    failure = runner.invoke(
        cli_app, ["sources", "validate", "--path", str(invalid_path)]
    )
    assert failure.exit_code == 1
    assert str(invalid_path) in failure.output
    assert "type" in failure.output
