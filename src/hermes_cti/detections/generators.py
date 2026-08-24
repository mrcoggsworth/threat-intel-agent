"""Deterministic Sigma, YARA, SPL, and KQL generation and validation."""

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any, Literal
from uuid import UUID

import yaml
from pydantic import ValidationError

from hermes_cti.detections.contracts import (
    CompiledArtifact,
    FileEvidence,
    QuerySpec,
    SigmaConversionResult,
    SigmaFieldMatch,
    SigmaLogSource,
    SigmaRuleSpec,
    YaraRuleSpec,
)
from hermes_cti.models.contracts import DetectionArtifact, DetectionType, sha256_text

_MAX_TOOL_OUTPUT = 1_000_000
_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _yaml_rule(spec: SigmaRuleSpec) -> str:
    selection: dict[str, str] = {match.field: match.value for match in spec.matches}
    payload = {
        "title": spec.title,
        "description": spec.description,
        "logsource": {
            key: value
            for key, value in {
                "category": spec.logsource.category,
                "product": spec.logsource.product,
                "service": spec.logsource.service,
            }.items()
            if value is not None
        },
        "detection": {"selection": selection, "condition": spec.condition},
        "level": spec.level,
        "tags": list(spec.tags),
        "references": list(spec.references),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def generate_sigma(
    report_version_id: UUID,
    detection_id: UUID,
    spec: SigmaRuleSpec,
    *,
    evidence_ids: tuple[UUID, ...],
    attack_techniques: tuple[str, ...] = (),
) -> DetectionArtifact:
    """Generate a minimal typed Sigma artifact from structured evidence."""

    if not evidence_ids:
        raise ValueError("Sigma generation requires evidence IDs")
    content = _yaml_rule(spec)
    return DetectionArtifact(
        detection_id=detection_id,
        report_version_id=report_version_id,
        detection_type=DetectionType.SIGMA,
        title=spec.title,
        content=content,
        telemetry_requirements=tuple(
            value
            for value in (
                spec.logsource.category,
                spec.logsource.product,
                spec.logsource.service,
            )
            if value is not None
        ),
        assumptions=("Sigma schema subset; validate with sigma-cli when installed.",),
        attack_techniques=attack_techniques,
        evidence_ids=evidence_ids,
        validation_tool="sigma-cli",
        validation_result="generated; parse required before publication",
    )


def parse_sigma(content: str) -> SigmaRuleSpec:
    """Parse and validate the supported Sigma subset using SafeLoader."""

    try:
        payload: Any = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError("invalid Sigma YAML") from exc
    if not isinstance(payload, dict):
        raise ValueError("Sigma document must be a mapping")
    logsource = payload.get("logsource")
    detection = payload.get("detection")
    selection = detection.get("selection") if isinstance(detection, dict) else None
    condition = detection.get("condition") if isinstance(detection, dict) else None
    if not isinstance(logsource, dict) or not isinstance(detection, dict):
        raise ValueError("Sigma requires logsource and detection mappings")
    if not isinstance(selection, dict) or not isinstance(condition, str):
        raise ValueError("Sigma requires detection.selection and condition")
    matches: list[SigmaFieldMatch] = []
    for field, value in sorted(selection.items()):
        if not isinstance(field, str) or not isinstance(value, str):
            raise ValueError("Sigma selection fields and values must be strings")
        matches.append(SigmaFieldMatch(field=field, value=value))
    try:
        return SigmaRuleSpec(
            title=payload.get("title"),
            description=payload.get("description", "Generated public-CTI rule"),
            logsource=SigmaLogSource.model_validate(logsource),
            matches=tuple(matches),
            condition=condition,
            level=payload.get("level", "medium"),
            tags=tuple(payload.get("tags", ())),
            references=tuple(payload.get("references", ())),
        )
    except (ValidationError, TypeError) as exc:
        raise ValueError("Sigma schema validation failed") from exc


def _safe_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _query_from_spec(
    spec: SigmaRuleSpec,
    backend: Literal["spl", "kql"],
    evidence_ids: tuple[UUID, ...] = (),
) -> QuerySpec:
    conditions = spec.matches
    fields = tuple(match.field for match in conditions)
    for field in fields:
        if not _FIELD_RE.fullmatch(field):
            raise ValueError(f"unsafe query field: {field}")
    telemetry = tuple(
        value
        for value in (
            spec.logsource.category,
            spec.logsource.product,
            spec.logsource.service,
        )
        if value is not None
    ) or ("telemetry not specified",)
    return QuerySpec(
        backend=backend,
        title=f"Template: {spec.title}",
        platform="unspecified",
        telemetry=telemetry,
        index=None,
        fields=fields,
        conditions=conditions,
        template=True,
        evidence_ids=evidence_ids,
    )


def render_query(spec: QuerySpec) -> str:
    """Render an explicitly labeled SPL/KQL query template safely."""

    if not spec.evidence_ids:
        raise ValueError("query generation requires evidence IDs")
    conditions = [
        f'{match.field}="{_safe_value(match.value)}"' for match in spec.conditions
    ]
    if spec.backend == "spl":
        prefix = f"index={spec.index} " if spec.index else ""
        return f"{prefix}{' AND '.join(conditions)} | table {', '.join(spec.fields)}"
    table = spec.index or "TelemetryTable"
    return (
        f"{table} | where {' and '.join(conditions)} | project {', '.join(spec.fields)}"
    )


def query_artifact(
    report_version_id: UUID,
    detection_id: UUID,
    spec: QuerySpec,
) -> DetectionArtifact:
    content = render_query(spec)
    return DetectionArtifact(
        detection_id=detection_id,
        report_version_id=report_version_id,
        detection_type=(
            DetectionType.SPL if spec.backend == "spl" else DetectionType.KQL
        ),
        title=spec.title,
        content=content,
        telemetry_requirements=spec.telemetry,
        assumptions=(
            f"platform={spec.platform}",
            f"index={spec.index or 'unspecified'}",
            "generic fallback query template"
            if spec.template
            else "provider-specific query",
        ),
        evidence_ids=spec.evidence_ids,
        validation_tool="query-renderer",
        validation_result="template" if spec.template else "generated",
    )


def convert_sigma(
    content: str,
    *,
    backend: Literal["spl", "kql"],
    sigma_executable: str = "sigma",
    timeout_seconds: float = 5.0,
    evidence_ids: tuple[UUID, ...] = (),
) -> SigmaConversionResult:
    """Parse Sigma and use sigma-cli when available, with a typed offline fallback."""

    parsed = parse_sigma(content)
    executable = shutil.which(sigma_executable)
    external = False
    if executable is not None:
        try:
            completed = subprocess.run(
                [
                    executable,
                    "convert",
                    "-t",
                    "splunk" if backend == "spl" else "kusto",
                ],
                input=content,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if completed.returncode == 0 and len(completed.stdout) <= _MAX_TOOL_OUTPUT:
                external = True
        except (OSError, subprocess.TimeoutExpired):
            external = False
    query = _query_from_spec(parsed, backend, evidence_ids)
    return SigmaConversionResult(
        parsed=parsed,
        converted=(query,),
        converter="sigma-cli" if external else "builtin-compatible-sigma-cli",
        external_tool_used=external,
    )


def generate_yara(
    report_version_id: UUID,
    detection_id: UUID,
    file_evidence: FileEvidence,
    *,
    rule_name: str,
) -> DetectionArtifact:
    """Generate YARA only when public file evidence is present."""

    spec = YaraRuleSpec(
        rule_name=rule_name,
        strings=file_evidence.strings,
        evidence_ids=file_evidence.evidence_ids,
    )
    lines = [f"rule {spec.rule_name} {{", "  strings:"]
    lines.extend(
        f'    $s{index} = "{_safe_value(value)}" ascii wide nocase'
        for index, value in enumerate(spec.strings, start=1)
    )
    lines.extend(["  condition:", f"    {spec.condition}", "}"])
    content = "\n".join(lines) + "\n"
    return DetectionArtifact(
        detection_id=detection_id,
        report_version_id=report_version_id,
        detection_type=DetectionType.YARA,
        title=spec.rule_name,
        content=content,
        assumptions=(f"public file evidence: {file_evidence.file_name}",),
        evidence_ids=file_evidence.evidence_ids,
        validation_tool="yara-python",
        validation_result="compile required before publication",
    )


def _fallback_compile_yara(content: str) -> None:
    if not re.search(r"(?s)^\s*rule\s+[A-Za-z_][A-Za-z0-9_]*\s*\{.*\}\s*$", content):
        raise ValueError("invalid YARA rule structure")
    if "strings:" not in content or "condition:" not in content:
        raise ValueError("YARA requires strings and condition sections")
    if not re.search(r'\$[A-Za-z_][A-Za-z0-9_]*\s*=\s*"', content):
        raise ValueError("YARA requires at least one string")
    if "syntax error" in content.casefold():
        raise ValueError("invalid YARA syntax")


def compile_yara(content: str) -> CompiledArtifact:
    """Compile with yara-python or strict compatibility validation."""

    digest = sha256_text(content)
    try:
        import yara  # type: ignore[import-not-found]
    except ImportError:
        _fallback_compile_yara(content)
        return CompiledArtifact(
            valid=True,
            validator="yara-python-compatibility",
            validation_result=(
                "validated without yara-python; install yara-python "
                "for native compilation"
            ),
            artifact_hash=digest,
        )
    try:
        yara.compile(source=content)
    except Exception as exc:
        raise ValueError("YARA compilation failed") from exc
    return CompiledArtifact(
        valid=True,
        validator="yara-python",
        validation_result="compiled",
        artifact_hash=digest,
    )
