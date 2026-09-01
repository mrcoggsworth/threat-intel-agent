"""Synthesizers for Sigma YAML, Splunk SPL, Defender & Elastic KQL, and YARA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid5

import yaml

# Standard namespace for deterministic rule UUIDs
SIGMA_NAMESPACE = UUID("00ab0000-0000-0000-0000-000000000000")


@dataclass
class DetectionRuleBundle:
    """Bundle containing synthesized detection rules across SIEM and YARA formats."""

    sigma_yaml: str
    splunk_spl: str
    defender_kql: str
    elastic_kql: str
    yara_rule: str
    mitre_technique_id: str = ""
    severity: str = "high"


def _safe_escape_quotes(value: str) -> str:
    """Escape quotes and backslashes for safe query string insertion."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def generate_sigma_rule(
    title: str,
    description: str,
    process_names: list[str],
    command_lines: list[str],
    tags: list[str] | None = None,
    severity: str = "high",
    author: str = "Hermes Autonomous CTI Agent",
    rule_id: str | None = None,
    references: list[str] | None = None,
) -> str:
    """Generate valid YAML matching SigmaHQ specifications with deterministic ID."""
    rule_uuid = rule_id or str(uuid5(SIGMA_NAMESPACE, f"sigma:{title}"))
    tag_list = list(tags) if tags else []
    ref_list = list(references) if references else []

    selection: dict[str, Any] = {}
    if process_names:
        selection["Image|endswith"] = (
            process_names[0] if len(process_names) == 1 else list(process_names)
        )
    if command_lines:
        selection["CommandLine|contains"] = (
            command_lines[0] if len(command_lines) == 1 else list(command_lines)
        )
    if not selection:
        selection["CommandLine|contains"] = "*"

    payload: dict[str, Any] = {
        "title": title,
        "id": rule_uuid,
        "status": "experimental",
        "description": description,
        "author": author,
        "references": ref_list,
        "tags": tag_list,
        "logsource": {
            "category": "process_creation",
            "product": "windows",
        },
        "detection": {
            "selection": selection,
            "condition": "selection",
        },
        "falsepositives": [
            "Administrative maintenance scripts",
            "Legitimate software updates",
        ],
        "level": severity.lower(),
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def generate_splunk_spl(
    process_names: list[str],
    command_lines: list[str],
    iocs: list[str] | None = None,
) -> str:
    """Generate Splunk SPL query with index fallback and standard field projection."""
    index_clause = (
        "(index=* OR index=main OR index=windows) (EventCode=1 OR EventCode=4688)"
    )
    conditions: list[str] = []

    if process_names:
        escaped_names = [_safe_escape_quotes(p) for p in process_names]
        if len(escaped_names) == 1:
            conditions.append(
                f'(Image="*{escaped_names[0]}*" OR '
                f'NewProcessName="*{escaped_names[0]}*")'
            )
        else:
            sub = " OR ".join(
                f'Image="*{p}*" OR NewProcessName="*{p}*"' for p in escaped_names
            )
            conditions.append(f"({sub})")

    if command_lines:
        escaped_cmds = [_safe_escape_quotes(c) for c in command_lines]
        if len(escaped_cmds) == 1:
            conditions.append(
                f'(CommandLine="*{escaped_cmds[0]}*" OR '
                f'ProcessCommandLine="*{escaped_cmds[0]}*")'
            )
        else:
            sub = " OR ".join(
                f'CommandLine="*{c}*" OR ProcessCommandLine="*{c}*"'
                for c in escaped_cmds
            )
            conditions.append(f"({sub})")

    if iocs:
        escaped_iocs = [_safe_escape_quotes(ioc) for ioc in iocs]
        sub = " OR ".join(f'"{ioc}"' for ioc in escaped_iocs)
        conditions.append(f"({sub})")

    filter_clause = " AND ".join(conditions) if conditions else "CommandLine=*"
    return (
        f"{index_clause} {filter_clause} | table _time, host, user, Image, CommandLine"
    )


def generate_defender_kql(
    process_names: list[str],
    command_lines: list[str],
    iocs: list[str] | None = None,
) -> str:
    """Generate Microsoft Defender KQL query targeting DeviceProcessEvents."""
    conditions: list[str] = []

    if process_names:
        quoted = ", ".join(f"'{_safe_escape_quotes(p)}'" for p in process_names)
        conditions.append(f"FileName in~ ({quoted})")

    if command_lines:
        quoted = ", ".join(f"'{_safe_escape_quotes(c)}'" for c in command_lines)
        conditions.append(f"ProcessCommandLine has_any ({quoted})")

    if iocs:
        quoted = ", ".join(f"'{_safe_escape_quotes(ioc)}'" for ioc in iocs)
        conditions.append(f"ProcessCommandLine has_any ({quoted})")

    where_clause = (
        " or ".join(conditions) if conditions else "isnotempty(ProcessCommandLine)"
    )
    return (
        "DeviceProcessEvents\n"
        f"| where {where_clause}\n"
        "| project Timestamp, DeviceName, AccountName, FileName, "
        "ProcessCommandLine, InitiatingProcessCommandLine"
    )


def generate_elastic_kql(
    process_names: list[str],
    command_lines: list[str],
    iocs: list[str] | None = None,
) -> str:
    """Generate Elastic KQL (Kibana Query Language) query."""
    clauses: list[str] = []

    if process_names:
        quoted = " or ".join(f'"{_safe_escape_quotes(p)}"' for p in process_names)
        clauses.append(f"process.name : ({quoted})")

    if command_lines:
        quoted = " or ".join(f'"{_safe_escape_quotes(c)}"' for c in command_lines)
        clauses.append(f"process.command_line : ({quoted})")

    if iocs:
        quoted = " or ".join(f'"{_safe_escape_quotes(ioc)}"' for ioc in iocs)
        clauses.append(f"process.command_line : ({quoted})")

    return " and ".join(clauses) if clauses else "process.command_line : *"


def generate_yara_rule(
    rule_name: str,
    description: str,
    strings: list[str],
    hex_patterns: list[str] | None = None,
    score: int = 80,
    author: str = "Hermes Autonomous CTI Agent",
) -> str:
    """Generate a valid, compile-ready YARA rule with sanitized identifier."""
    sanitized_name = re.sub(r"[^A-Za-z0-9_]", "_", rule_name).strip("_")
    if not sanitized_name or not (
        sanitized_name[0].isalpha() or sanitized_name[0] == "_"
    ):
        sanitized_name = (
            f"Hermes_Rule_{sanitized_name}" if sanitized_name else "Hermes_Rule_Auto"
        )

    meta_block = [
        "    meta:",
        f'        description = "{_safe_escape_quotes(description)}"',
        f'        author = "{_safe_escape_quotes(author)}"',
        f"        score = {score}",
    ]

    string_block = ["    strings:", "        $magic = { 4D 5A }"]
    string_var_names: list[str] = []

    for idx, s in enumerate(strings, start=1):
        var_name = f"$s{idx}"
        escaped_val = _safe_escape_quotes(s)
        string_block.append(f'        {var_name} = "{escaped_val}" ascii wide nocase')
        string_var_names.append(var_name)

    hex_var_names: list[str] = []
    if hex_patterns:
        for idx, h in enumerate(hex_patterns, start=1):
            var_name = f"$hex{idx}"
            clean_hex = h.strip().strip("{}").strip()
            string_block.append(f"        {var_name} = {{ {clean_hex} }}")
            hex_var_names.append(var_name)

    cond_parts: list[str] = []
    if string_var_names:
        cond_parts.append(f"1 of ({', '.join(string_var_names)})")
    if hex_var_names:
        cond_parts.append(f"1 of ({', '.join(hex_var_names)})")

    if cond_parts:
        condition_logic = (
            f"uint16(0) == 0x5A4D and $magic at 0 and ({' or '.join(cond_parts)})"
        )
    else:
        condition_logic = "uint16(0) == 0x5A4D and $magic at 0"

    condition_block = ["    condition:", f"        {condition_logic}"]

    lines = [
        f"rule {sanitized_name} {{",
        *meta_block,
        "",
        *string_block,
        "",
        *condition_block,
        "}",
        "",
    ]
    return "\n".join(lines)


class RuleGenerator:
    """Synthesizer for SIEM rules, YARA signatures, and detection bundles."""

    @staticmethod
    def generate_sigma_rule(
        title: str,
        description: str,
        process_names: list[str],
        command_lines: list[str],
        tags: list[str] | None = None,
        severity: str = "high",
        author: str = "Hermes Autonomous CTI Agent",
        rule_id: str | None = None,
        references: list[str] | None = None,
    ) -> str:
        return generate_sigma_rule(
            title=title,
            description=description,
            process_names=process_names,
            command_lines=command_lines,
            tags=tags,
            severity=severity,
            author=author,
            rule_id=rule_id,
            references=references,
        )

    @staticmethod
    def generate_splunk_spl(
        process_names: list[str],
        command_lines: list[str],
        iocs: list[str] | None = None,
    ) -> str:
        return generate_splunk_spl(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )

    @staticmethod
    def generate_defender_kql(
        process_names: list[str],
        command_lines: list[str],
        iocs: list[str] | None = None,
    ) -> str:
        return generate_defender_kql(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )

    @staticmethod
    def generate_elastic_kql(
        process_names: list[str],
        command_lines: list[str],
        iocs: list[str] | None = None,
    ) -> str:
        return generate_elastic_kql(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )

    @staticmethod
    def generate_yara_rule(
        rule_name: str,
        description: str,
        strings: list[str],
        hex_patterns: list[str] | None = None,
        score: int = 80,
    ) -> str:
        return generate_yara_rule(
            rule_name=rule_name,
            description=description,
            strings=strings,
            hex_patterns=hex_patterns,
            score=score,
        )

    @classmethod
    def generate_bundle(
        cls,
        title: str,
        description: str,
        process_names: list[str],
        command_lines: list[str],
        strings: list[str],
        tags: list[str] | None = None,
        hex_patterns: list[str] | None = None,
        iocs: list[str] | None = None,
        mitre_technique_id: str = "",
        severity: str = "high",
    ) -> DetectionRuleBundle:
        """Create a complete multi-format detection bundle."""
        all_tags = list(tags) if tags else []
        if mitre_technique_id:
            tech_tag = f"attack.{mitre_technique_id.lower()}"
            if tech_tag not in all_tags:
                all_tags.append(tech_tag)

        sigma = cls.generate_sigma_rule(
            title=title,
            description=description,
            process_names=process_names,
            command_lines=command_lines,
            tags=all_tags,
            severity=severity,
        )
        spl = cls.generate_splunk_spl(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )
        defender_kql = cls.generate_defender_kql(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )
        elastic_kql = cls.generate_elastic_kql(
            process_names=process_names,
            command_lines=command_lines,
            iocs=iocs,
        )
        yara = cls.generate_yara_rule(
            rule_name=title,
            description=description,
            strings=strings,
            hex_patterns=hex_patterns,
        )
        return DetectionRuleBundle(
            sigma_yaml=sigma,
            splunk_spl=spl,
            defender_kql=defender_kql,
            elastic_kql=elastic_kql,
            yara_rule=yara,
            mitre_technique_id=mitre_technique_id,
            severity=severity,
        )
