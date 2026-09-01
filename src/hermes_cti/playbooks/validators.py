"""Syntax and schema validators for Sigma YAML and YARA rules."""

from __future__ import annotations

import re
from typing import Any

import yaml


def validate_sigma_rule(sigma_yaml: str) -> tuple[bool, str | None]:
    """Validate Sigma rule YAML structure and mandatory schema fields."""
    try:
        data: Any = yaml.safe_load(sigma_yaml)
    except Exception as exc:
        return False, f"Invalid YAML syntax: {exc}"

    if not isinstance(data, dict):
        return False, "Sigma rule must be a YAML mapping (dictionary)"

    required_top_keys = ["title", "logsource", "detection"]
    for key in required_top_keys:
        if key not in data:
            return False, f"Missing mandatory Sigma field: '{key}'"

    logsource = data.get("logsource")
    if not isinstance(logsource, dict):
        return False, "'logsource' must be a mapping"
    if not any(k in logsource for k in ("category", "product", "service")):
        return False, (
            "'logsource' must contain at least one of "
            "'category', 'product', or 'service'"
        )

    detection = data.get("detection")
    if not isinstance(detection, dict):
        return False, "'detection' must be a mapping"

    if "condition" not in detection:
        return False, "'detection' mapping missing mandatory 'condition' field"

    condition_val = detection.get("condition")
    if not isinstance(condition_val, str) or not condition_val.strip():
        return False, "'detection.condition' must be a non-empty string"

    return True, None


def validate_yara_rule(yara_str: str) -> tuple[bool, str | None]:
    """Validate YARA syntax by compiling via yara-python or offline checks."""
    clean = yara_str.strip()
    if not clean:
        return False, "YARA rule content is empty"

    try:
        import yara  # type: ignore[import-not-found]

        try:
            yara.compile(source=clean)
            return True, None
        except yara.SyntaxError as exc:
            return False, f"YARA syntax error: {exc}"
        except Exception as exc:
            return False, f"YARA compilation error: {exc}"
    except ImportError:
        # Fallback regex/token check when yara-python is not installed
        return _fallback_validate_yara(clean)


def _fallback_validate_yara(clean: str) -> tuple[bool, str | None]:
    """Offline syntactic fallback validator when yara-python is unavailable."""
    if not clean:
        return False, "YARA rule content is empty"

    if "syntax error" in clean.lower():
        return False, "YARA syntax error detected"

    # Match rule <name> { ... }
    match = re.search(r"rule\s+([A-Za-z0-9_]+)\s*\{", clean)
    if not match:
        return False, "Missing or invalid 'rule <identifier> {' definition"

    rule_name = match.group(1)
    if not (rule_name[0].isalpha() or rule_name[0] == "_"):
        return False, f"Invalid YARA rule name identifier: '{rule_name}'"

    if not clean.endswith("}"):
        return False, "YARA rule missing closing brace '}'"

    if "condition:" not in clean:
        return False, "Missing 'condition:' section in YARA rule"

    condition_idx = clean.find("condition:")
    condition_content = clean[condition_idx + len("condition:") : -1].strip()
    if not condition_content:
        return False, "Empty 'condition:' block in YARA rule"

    return True, None


class RuleValidator:
    """Validator for Sigma and YARA rules."""

    @staticmethod
    def validate_sigma_rule(sigma_yaml: str) -> tuple[bool, str | None]:
        return validate_sigma_rule(sigma_yaml)

    @staticmethod
    def validate_yara_rule(yara_str: str) -> tuple[bool, str | None]:
        return validate_yara_rule(yara_str)
