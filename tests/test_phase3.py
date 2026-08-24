"""Offline tests for deterministic Phase 3 extraction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from typer.testing import CliRunner

from hermes_cti.cli.main import app as cli_app
from hermes_cti.extraction import (
    ExtractionConfig,
    ExtractionLimitError,
    IPExclusionClass,
    extract_document,
    refang_text,
    to_csv,
    to_json,
)
from hermes_cti.models.contracts import (
    DocumentType,
    SourceDocument,
    sha256_text,
)

DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000301")
RAW_ID = UUID("00000000-0000-0000-0000-000000000302")


def document(text: str) -> SourceDocument:
    return SourceDocument(
        source_document_id=DOCUMENT_ID,
        source_id="fixture",
        raw_artifact_id=RAW_ID,
        canonical_url="https://source.example.test/article",
        title="Fixture",
        retrieved_at=datetime(2026, 2, 5, tzinfo=UTC),
        normalized_text=text,
        document_type=DocumentType.ARTICLE,
        normalized_content_hash=sha256_text(text),
        parse_version="test",
    )


def values(result):
    return [
        (item.indicator_type.value, item.normalized_value)
        for item in result.observations
    ]


def test_refang_variants_do_not_change_unrelated_text() -> None:
    value = "hxxps://evil[.]example[:]8443/x and already https://safe.example/x"
    assert (
        refang_text(value)
        == "https://evil.example:8443/x and already https://safe.example/x"
    )
    assert refang_text("hxxpish [x] (y) {z}") == "hxxpish [x] (y) {z}"


def test_urls_keep_exact_defanged_evidence_span_and_hide_nested_domain() -> None:
    text = "See hxxps://evil[.]example:8443/a?q=1#frag."
    result = extract_document(document(text))
    assert values(result) == [("url", "https://evil.example:8443/a?q=1#frag")]
    observation = result.observations[0]
    assert (
        text[observation.start_offset : observation.end_offset]
        == observation.original_display_value
    )
    assert (
        observation.original_display_value == "hxxps://evil[.]example:8443/a?q=1#frag"
    )
    assert observation.validation_state.value == "validated"


@pytest.mark.parametrize("value", ["8.8.8.8", "1.2.3.4"])
def test_valid_ipv4_is_extracted(value: str) -> None:
    result = extract_document(document(value))
    assert values(result) == [("ipv4", value)]


def test_invalid_ipv4_octets_are_rejected() -> None:
    result = extract_document(document("999.1.1.1 256.10.10.10 1.2.3.999"))
    assert not result.observations


@pytest.mark.parametrize("value", ["2001:0DB8:0:0:0:0:0:1", "2001:4860:4860::8888"])
def test_ipv6_is_validated_and_compressed(value: str) -> None:
    result = extract_document(document(value))
    if value.startswith("2001:0DB8"):
        assert result.suppressed_observations[0].normalized_value == "2001:db8::1"
    else:
        assert values(result) == [("ipv6", "2001:4860:4860::8888")]


def test_invalid_ipv6_is_rejected() -> None:
    result = extract_document(document("2001:db8:::1 2001:gggg::1"))
    assert not result.observations


def test_ip_exclusion_is_configurable_and_auditable() -> None:
    default_result = extract_document(document("192.168.1.10 127.0.0.1 8.8.8.8"))
    assert values(default_result) == [("ipv4", "8.8.8.8")]
    assert {
        item.suppression_reason for item in default_result.suppressed_observations
    } == {
        "excluded_ip_private",
        "excluded_ip_loopback",
    }
    allowed = extract_document(
        document("192.168.1.10"),
        ExtractionConfig(excluded_ip_classes=()),
    )
    assert values(allowed) == [("ipv4", "192.168.1.10")]
    docs = extract_document(
        document("192.0.2.10 224.0.0.1 ::"),
        ExtractionConfig(
            excluded_ip_classes=(
                IPExclusionClass.DOCUMENTATION,
                IPExclusionClass.MULTICAST,
                IPExclusionClass.UNSPECIFIED,
            )
        ),
    )
    assert not docs.observations
    assert len(docs.suppressed_observations) == 3


def test_url_validation_handles_idna_and_rejects_credentials_or_invalid_scheme() -> (
    None
):
    text = (
        "https://bücher.example:443/path?q=one#frag "
        "https://user:pass@example.com/a ftp://example.com/a"
    )
    result = extract_document(document(text))
    assert [
        item.normalized_value
        for item in result.observations
        if item.indicator_type.value == "url"
    ] == ["https://xn--bcher-kva.example:443/path?q=one#frag"]
    assert all(
        item.normalized_value != "https://example.com/a" for item in result.observations
    )


def test_hash_boundaries_and_hash_like_ordinary_text() -> None:
    md5 = "0123456789abcdef0123456789abcdef"
    sha1 = "0123456789abcdef0123456789abcdef01234567"
    sha256 = "0123456789abcdef" * 4
    text = f"{md5} {sha1} {sha256} deadbeefdeadbeefdeadbeefdeadbeef"
    result = extract_document(document(text))
    assert values(result) == [
        ("md5", md5),
        ("sha1", sha1),
        ("sha256", sha256),
    ]


def test_cves_are_separate_and_normalized() -> None:
    result = extract_document(document("cve-2026-1234 CVE 2026 1234 CVE_2027_00001"))
    assert not any(item.indicator_type.value == "cve" for item in result.observations)
    assert [
        (item.normalized_value, item.original_display_value)
        for item in result.cve_candidates
    ] == [
        ("CVE-2026-1234", "cve-2026-1234"),
        ("CVE-2027-00001", "CVE_2027_00001"),
    ]


def test_paths_and_registry_are_distinct_and_overlap_is_deduplicated() -> None:
    text = r"HKLM\Software\Bad\Run C:\Windows\System32\bad.exe /var/tmp/bad.bin"
    result = extract_document(document(text))
    assert values(result) == [
        ("registry_path", r"HKLM\Software\Bad\Run"),
        ("file_path", r"C:\Windows\System32\bad.exe"),
        ("file_path", "/var/tmp/bad.bin"),
    ]


def test_email_requires_configuration_and_unicode_punctuation_is_safe() -> None:
    text = "Contact analyst@example.com, and see evil[.]example。"
    assert not any(
        item.indicator_type.value == "email"
        for item in extract_document(document(text)).observations
    )
    result = extract_document(document(text), ExtractionConfig(extract_email=True))
    assert ("email", "analyst@example.com") in values(result)
    assert ("domain", "evil.example") in values(result)


def test_domain_suppression_is_configurable() -> None:
    result = extract_document(
        document("benign.example.com malicious.example.net"),
        ExtractionConfig(suppressed_domains=("example.com",)),
    )
    assert values(result) == [("domain", "malicious.example.net")]
    assert result.suppressed_observations[0].suppression_reason == "suppressed_domain"


def test_large_input_limit_is_enforced_without_network_access() -> None:
    with pytest.raises(ExtractionLimitError):
        extract_document(document("x" * 101), ExtractionConfig(max_input_chars=100))
    result = extract_document(
        document("8.8.8.8 " * 1000), ExtractionConfig(max_input_chars=10_000)
    )
    assert len(result.observations) == 1


def test_ordering_json_and_csv_are_deterministic() -> None:
    result = extract_document(document("CVE-2026-1234 8.8.8.8 example.com"))
    assert [item.start_offset for item in result.observations] == sorted(
        item.start_offset for item in result.observations
    )
    assert to_json(result) == to_json(
        extract_document(document("CVE-2026-1234 8.8.8.8 example.com"))
    )
    payload = json.loads(to_json(result))
    assert list(payload) == [
        "schema_version",
        "source_document_id",
        "observations",
        "cve_candidates",
        "suppressed_observations",
    ]
    assert to_csv(result).splitlines()[0].startswith("record_type,indicator_type")


def test_cli_extracts_from_stdin_in_json_and_csv() -> None:
    runner = CliRunner()
    json_result = runner.invoke(cli_app, ["extract"], input="8.8.8.8 CVE-2026-1234")
    assert json_result.exit_code == 0, json_result.stdout
    assert (
        json.loads(json_result.stdout)["observations"][0]["normalized_value"]
        == "8.8.8.8"
    )
    csv_result = runner.invoke(cli_app, ["extract", "--format", "csv"], input="8.8.8.8")
    assert csv_result.exit_code == 0, csv_result.stdout
    assert "indicator,ipv4,8.8.8.8" in csv_result.stdout
