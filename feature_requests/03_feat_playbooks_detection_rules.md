# Worktree 3 Implementation Plan: Detection Rule Synthesis & Playbook Engine

## Branch & Worktree Configuration
- **Branch Name:** `feat/playbooks-detection-rules`
- **Worktree Directory:** `../threat-intel-agent-wt3`
- **Integration Merge Target:** `main` (Merge Phase 3, builds on Models and Extraction)
- **Authoritative Skill Context:** `.hermes/skills/sigma-rule-generator/SKILL.md`, `.hermes/skills/yara-author/SKILL.md`, `.hermes/skills/threat-hunting/SKILL.md`

---

## 1. Scope & Responsibilities

Worktree 3 is responsible for turning extracted CTI indicators and MITRE ATT&CK techniques into actionable detection rules and investigation playbooks:
1. **Multi-Format SIEM Rule Synthesis:** Generating standards-compliant **Sigma YAML**, **Splunk SPL**, **Microsoft Defender KQL**, and **Elastic KQL** detection queries with fallback indexing.
2. **YARA Signature Generation:** Creating valid, compile-ready YARA rules with PE headers, hex byte patterns, ASCII/wide string modifiers, and condition logic.
3. **Two-Tiered Hunt Playbooks:** Producing two-tiered investigation guides featuring a 4-step modal summary (Scoping $\rightarrow$ SIEM Query $\rightarrow$ Triage Branch $\rightarrow$ Containment) alongside deep-dive operational phases.
4. **Syntax & Schema Validators:** Offline validation ensuring synthesized Sigma rules have mandatory fields and YARA rules compile cleanly via `yara-python`.

---

## 2. File Ownership & Structural Layout

```text
src/
├── hermes/
│   └── playbooks/
│       ├── __init__.py
│       ├── rule_generator.py   # Synthesizers for Sigma YAML, Splunk SPL, KQL, and YARA
│       ├── hunt_playbook.py    # Two-tiered (4-step modal + deep-dive) hunt playbook builder
│       └── validators.py       # Syntax and schema validators for Sigma and YARA
tests/
└── test_playbooks.py           # Unit tests for rule generation, syntax validation, and playbooks
```

---

## 3. Step-by-Step Implementation Details

### Step 3.1: Worktree Initialization
```bash
git worktree add ../threat-intel-agent-wt3 -b feat/playbooks-detection-rules
cd ../threat-intel-agent-wt3
```

### Step 3.2: Module `src/hermes/playbooks/rule_generator.py`
Implement `RuleGenerator`:
- **Data Models:**
  ```python
  from dataclasses import dataclass, field


  @dataclass
  class DetectionRuleBundle:
      sigma_yaml: str
      splunk_spl: str
      defender_kql: str
      elastic_kql: str
      yara_rule: str
      mitre_technique_id: str = ""
      severity: str = "high"
  ```
- **Sigma YAML Generation:**
  - `def generate_sigma_rule(title: str, description: str, process_names: list[str], command_lines: list[str], tags: list[str], severity: str = "high", author: str = "Hermes Autonomous CTI Agent") -> str`
  - Generates valid YAML matching SigmaHQ specifications with `id` (UUIDv4), `status: experimental`, `logsource: {category: process_creation, product: windows}`, `detection: {selection: {...}, condition: selection}`, `level: ...`.
- **Splunk SPL Generation:**
  - `def generate_splunk_spl(process_names: list[str], command_lines: list[str], iocs: list[str] | None = None) -> str`
  - Generates query with index fallback: `(index=* OR index=main OR index=windows) (EventCode=1 OR EventCode=4688) ... | table _time, host, user, Image, CommandLine`.
- **Defender KQL & Elastic KQL Generation:**
  - `def generate_defender_kql(...) -> str`: `DeviceProcessEvents | where ProcessCommandLine has_any (...) or FileName in~ (...)`.
  - `def generate_elastic_kql(...) -> str`: `process.name : (...) and process.command_line : (...)`.
- **YARA Signature Generation:**
  - `def generate_yara_rule(rule_name: str, description: str, strings: list[str], hex_patterns: list[str] | None = None, score: int = 80) -> str`
  - Sanitizes rule name (alphanumeric and underscores), formats `$magic = { 4D 5A }`, string patterns with `ascii wide nocase`, and structured condition `uint16(0) == 0x5A4D and ...`.

### Step 3.3: Module `src/hermes/playbooks/hunt_playbook.py`
Implement `HuntPlaybookGenerator`:
- **Two-Tiered Playbook Schema:**
  - `def generate_hunt_playbook(threat_title: str, summary: str, techniques: list[str], iocs: dict[str, list[str]], detection_bundle: DetectionRuleBundle) -> dict[str, Any]`
  - Returns dictionary with:
    - `summary_playbook` (4-Step Modal Summary):
      1. **Step 1: Threat Scoping & Telemetry Check** (Identify target host pools, critical services, and data sources).
      2. **Step 2: SIEM Query Execution** (Execute primary Splunk SPL / Defender KQL hunt query).
      3. **Step 3: Triage & False-Positive Branching** (Filter legitimate IT automation and verify suspicious parent-child chains).
      4. **Step 4: Immediate Containment & Isolation** (Host network isolation, credential invalidation, and ticket escalation).
    - `deep_dive_phases`:
      - **Phase 1: Baseline & Pre-Hunt Telemetry Audit**
      - **Phase 2: Systematic Sweep & Anomaly Identification**
      - **Phase 3: Deep Forensics & Secondary Indicator Extraction**
      - **Phase 4: Eradication, Hardening & Detection Rule Deployment**

### Step 3.4: Module `src/hermes/playbooks/validators.py`
Implement `RuleValidator`:
- **Functionality:**
  - `def validate_sigma_rule(sigma_yaml: str) -> tuple[bool, str | None]`: Validates YAML formatting, schema keys (`title`, `logsource`, `detection`, `condition`), and returns status with error message if invalid.
  - `def validate_yara_rule(yara_str: str) -> tuple[bool, str | None]`: Validates syntax by compiling via `yara.compile(source=yara_str)` with regex syntax fallback if `yara-python` is unavailable.

---

## 4. Test Suite Requirements

### `tests/test_playbooks.py`
- `test_sigma_rule_generation_and_validation`: Verify Sigma rule YAML structure, UUID, and schema validity.
- `test_splunk_spl_generation`: Verify Splunk queries contain correct log sources, boolean logic, and table output.
- `test_kql_rule_generation`: Verify Defender and Elastic KQL queries format clauses correctly.
- `test_yara_rule_generation_and_compilation`: Verify YARA rule builds valid syntax and compiles cleanly using `yara-python`.
- `test_two_tiered_hunt_playbook_structure`: Ensure output dictionary contains both 4-step modal summary and 4 deep-dive operational phases.
- `test_invalid_rules_validation_errors`: Ensure malformed Sigma YAML or invalid YARA conditions return `(False, "error message")`.

---

## 5. Verification Commands

Run within `../threat-intel-agent-wt3`:
```bash
# Run playbooks test suite
uv run pytest tests/test_playbooks.py -v

# Code formatting and linting
uv run ruff check src/hermes/playbooks tests/test_playbooks.py
uv run ruff format --check src/hermes/playbooks tests/test_playbooks.py
```

---

## 6. Commit & Merge Instructions

1. Commit in worktree 3:
   ```bash
   git add src/hermes/playbooks tests/test_playbooks.py
   git commit -m "feat(playbooks): add Sigma, SPL, KQL, YARA rule generators, 2-tier hunt playbooks, and validators"
   ```
2. In main repository workspace:
   ```bash
   git merge feat/playbooks-detection-rules --no-ff -m "Merge branch 'feat/playbooks-detection-rules' (Phase 3)"
   ```
