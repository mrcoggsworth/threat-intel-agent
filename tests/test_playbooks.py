"""Unit tests for rule generation, syntax validation, and hunt playbooks."""

from __future__ import annotations

from hermes_cti.playbooks.hunt_playbook import generate_hunt_playbook
from hermes_cti.playbooks.rule_generator import (
    DetectionRuleBundle,
    generate_defender_kql,
    generate_elastic_kql,
    generate_sigma_rule,
    generate_splunk_spl,
    generate_yara_rule,
)
from hermes_cti.playbooks.validators import validate_sigma_rule, validate_yara_rule


def test_sigma_rule_generation_and_validation() -> None:
    title = "Suspicious PowerShell Download Cradle"
    description = "Detects PowerShell execution downloading remote payload"
    procs = ["powershell.exe", "pwsh.exe"]
    cmds = ["DownloadString", "Invoke-WebRequest", "iex"]
    tags = ["attack.execution", "attack.t1059.001"]

    sigma_yaml = generate_sigma_rule(
        title=title,
        description=description,
        process_names=procs,
        command_lines=cmds,
        tags=tags,
        severity="high",
    )

    assert "id:" in sigma_yaml
    assert "status: experimental" in sigma_yaml
    assert "powershell.exe" in sigma_yaml
    assert "DownloadString" in sigma_yaml

    valid, err = validate_sigma_rule(sigma_yaml)
    assert valid is True
    assert err is None


def test_splunk_spl_generation() -> None:
    procs = ["rundll32.exe", "regsvr32.exe"]
    cmds = ["setup.dll", "scrobj.dll"]
    iocs = ["198.51.100.10"]

    spl = generate_splunk_spl(process_names=procs, command_lines=cmds, iocs=iocs)

    assert "index=*" in spl or "index=main" in spl
    assert "EventCode=1 OR EventCode=4688" in spl
    assert "rundll32.exe" in spl
    assert "setup.dll" in spl
    assert "198.51.100.10" in spl
    assert "| table _time, host, user, Image, CommandLine" in spl


def test_kql_rule_generation() -> None:
    procs = ["mimikatz.exe"]
    cmds = ["sekurlsa::logonpasswords"]
    iocs = ["203.0.113.5"]

    defender_kql = generate_defender_kql(
        process_names=procs,
        command_lines=cmds,
        iocs=iocs,
    )
    assert "DeviceProcessEvents" in defender_kql
    assert "mimikatz.exe" in defender_kql
    assert "sekurlsa::logonpasswords" in defender_kql
    assert "203.0.113.5" in defender_kql

    elastic_kql = generate_elastic_kql(
        process_names=procs,
        command_lines=cmds,
        iocs=iocs,
    )
    assert "process.name :" in elastic_kql
    assert "mimikatz.exe" in elastic_kql
    assert "process.command_line :" in elastic_kql


def test_yara_rule_generation_and_compilation() -> None:
    rule_name = "APT_Backdoor_Loader_2026"
    description = "Detects in-memory reflective DLL loader"
    strings = ["ReflectiveLoader", "VirtualAllocEx", "WriteProcessMemory"]
    hex_patterns = ["4D 5A 90 00 03 00 00 00"]

    yara_code = generate_yara_rule(
        rule_name=rule_name,
        description=description,
        strings=strings,
        hex_patterns=hex_patterns,
        score=90,
    )

    assert "rule APT_Backdoor_Loader_2026" in yara_code
    assert "$hex1 = { 4D 5A 90 00 03 00 00 00 }" in yara_code
    assert "ReflectiveLoader" in yara_code
    assert "condition:" in yara_code

    valid, err = validate_yara_rule(yara_code)
    assert valid is True
    assert err is None


def test_two_tiered_hunt_playbook_structure() -> None:
    bundle = DetectionRuleBundle(
        sigma_yaml="title: test",
        splunk_spl="index=*",
        defender_kql="DeviceProcessEvents",
        elastic_kql="process.name: test",
        yara_rule="rule test { condition: true }",
        mitre_technique_id="T1059.001",
        severity="high",
    )

    playbook = generate_hunt_playbook(
        threat_title="Operation BlackSun Campaign",
        summary="Targeted spearphishing leading to lateral movement",
        techniques=["T1566.001", "T1059.001"],
        iocs={"ipv4": ["198.51.100.22"], "domains": ["c2-evil.com"]},
        detection_bundle=bundle,
    )

    assert "summary_playbook" in playbook
    summary_pb = playbook["summary_playbook"]
    assert "step_1" in summary_pb
    assert "step_2" in summary_pb
    assert "step_3" in summary_pb
    assert "step_4" in summary_pb
    assert summary_pb["step_1"]["title"] == "Threat Scoping & Telemetry Check"
    assert summary_pb["step_2"]["splunk_spl"] == "index=*"

    assert "deep_dive_phases" in playbook
    phases = playbook["deep_dive_phases"]
    assert "phase_1" in phases
    assert "phase_2" in phases
    assert "phase_3" in phases
    assert "phase_4" in phases


def test_invalid_rules_validation_errors() -> None:
    invalid_sigma = "invalid: [yaml: broken"
    valid, err = validate_sigma_rule(invalid_sigma)
    assert valid is False
    assert err is not None

    invalid_yara = "rule broken_yara { condition: undefined_identifier }"
    valid_y, err_y = validate_yara_rule(invalid_yara)
    assert valid_y is False
    assert err_y is not None
