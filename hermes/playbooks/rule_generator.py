"""Detection Rule Generator (Sigma, YARA, KQL, Splunk SPL)."""

from typing import Dict, List, Any


class RuleGenerator:
    """Generates detection rules in multiple query formats."""

    def generate_sigma_rule(self, title: str, iocs: Dict[str, List[str]]) -> str:
        """Generates a standard Sigma YAML detection rule."""
        return f"# Sigma Rule: {title}\n# Status: Draft"

    def generate_yara_rule(self, rule_name: str, strings: List[str]) -> str:
        """Generates a YARA rule for file/memory scanning."""
        return f"rule {rule_name} {{\n  strings:\n  condition:\n    any of them\n}}"
