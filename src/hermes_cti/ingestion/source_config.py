"""Typed, offline source-registry loading and validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from pydantic import TypeAdapter, ValidationError

from hermes_cti.core.exceptions import ConfigurationError
from hermes_cti.models.contracts import (
    JSONValue,
    ReliabilityClassification,
    SourceCategory,
    SourceConfig,
    SourceRegistry,
    sha256_text,
)

_SECRET_KEY = re.compile(
    r"(?i)(password|secret|token|api[_-]?key|credential|authorization|private[_-]?key)"
)


class SourceConfigurationError(ConfigurationError):
    """Safe source-config error identifying file, source, and field."""

    def __init__(
        self,
        path: Path,
        message: str,
        source_name: str | None = None,
        field_name: str | None = None,
    ) -> None:
        self.path = path
        self.source_name = source_name
        self.field_name = field_name
        location = str(path)
        if source_name:
            location += f" source '{source_name}'"
        if field_name:
            location += f" field '{field_name}'"
        super().__init__(f"{location}: {message}")


def default_sources_path() -> Path:
    """Resolve the repository source registry without accessing the network."""

    current = Path.cwd() / "config" / "sources.json"
    if current.is_file():
        return current
    return Path(__file__).resolve().parents[3] / "config" / "sources.json"


def _secret_field(value: JSONValue, path: str) -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if _SECRET_KEY.search(key):
                return child_path
            found = _secret_field(child, child_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _secret_field(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _safe_error_field(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "source"
    location = cast(tuple[object, ...], errors[0]["loc"])
    return ".".join(str(part) for part in location) or "source"


def _default_reliability(category: str, name: str) -> ReliabilityClassification:
    lowered_name = name.casefold()
    if lowered_name.startswith("cisa") or category in {
        SourceCategory.CERT_ADVISORIES.value,
        SourceCategory.VENDOR_ADVISORIES.value,
    }:
        return ReliabilityClassification.AUTHORITATIVE
    if category in {
        SourceCategory.THREAT_RESEARCH.value,
        SourceCategory.DETECTION_ENGINEERING.value,
    }:
        return ReliabilityClassification.PRIMARY_RESEARCH
    if category in {
        SourceCategory.INCIDENT_RESPONSE.value,
        SourceCategory.TACTICAL_IOCS.value,
    }:
        return ReliabilityClassification.INCIDENT_RESPONSE
    return ReliabilityClassification.GENERAL_NEWS


def _with_legacy_defaults(source: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Add typed defaults while accepting the original Phase 0 JSON shape."""

    normalized = dict(source)
    name_value = normalized.get("name")
    category_value = normalized.get("category")
    name = name_value if isinstance(name_value, str) else "unnamed source"
    category = category_value if isinstance(category_value, str) else ""
    normalized.setdefault("enabled", True)
    normalized.setdefault("polling_interval_seconds", 86_400)
    normalized.setdefault("timeout_seconds", 30.0)
    normalized.setdefault("max_response_bytes", 10_485_760)
    normalized.setdefault("reliability", _default_reliability(category, name).value)
    normalized.setdefault("tags", [])
    normalized.setdefault("adapter_settings", {})
    return normalized


def load_source_registry(path: Path | None = None) -> SourceRegistry:
    """Load and validate ``config/sources.json`` without fetching any source."""

    resolved_path = path or default_sources_path()
    if not resolved_path.is_file():
        raise SourceConfigurationError(resolved_path, "file does not exist")
    try:
        raw_sources = TypeAdapter(list[dict[str, JSONValue]]).validate_json(
            resolved_path.read_bytes()
        )
    except (OSError, ValueError, ValidationError) as exc:
        raise SourceConfigurationError(
            resolved_path, "top-level JSON must be an array of source objects"
        ) from exc

    parsed: list[SourceConfig] = []
    for index, raw_source in enumerate(raw_sources):
        source_name_value = raw_source.get("name")
        source_name = source_name_value if isinstance(source_name_value, str) else None
        secret_path = _secret_field(raw_source, f"sources[{index}]")
        if secret_path:
            raise SourceConfigurationError(
                resolved_path,
                "secret-like fields are not permitted in tracked source configuration",
                source_name,
                secret_path,
            )
        try:
            parsed.append(
                SourceConfig.model_validate(_with_legacy_defaults(raw_source))
            )
        except ValidationError as exc:
            raise SourceConfigurationError(
                resolved_path,
                "invalid source configuration",
                source_name,
                _safe_error_field(exc),
            ) from exc

    try:
        return SourceRegistry(sources=tuple(parsed))
    except ValidationError as exc:
        raise SourceConfigurationError(
            resolved_path, "source identifiers must be unique", field_name="source_id"
        ) from exc


def source_configuration_hash(registry: SourceRegistry) -> str:
    """Return a deterministic hash suitable for a future run manifest."""

    return sha256_text(registry.stable_json())
