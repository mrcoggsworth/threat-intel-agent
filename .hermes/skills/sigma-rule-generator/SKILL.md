---
name: sigma-rule-generator
description: Converts unstructured threat intelligence and MITRE ATT&CK TTPs into production-ready Sigma rules, Splunk SPL, and Elastic KQL queries.
---

# ⚡ sigma-rule-generator // Threat Hunt Automation Skill

## Overview
The `sigma-rule-generator` skill translates unstructured threat intelligence write-ups into actionable detection logic. It maps extracted tactics, techniques, and procedures (TTPs) directly to the MITRE ATT&CK® framework and produces syntactically valid YAML-formatted **Sigma rules**, **Splunk SPL**, and **Elastic KQL** queries.

## Why Create It
- Converts static CTI reports into active SOC defense controls.
- Standardizes detection rule metadata, severity ratings, and MITRE tags.
- Provides immediate hunting queries ready for deployment into SIEM platforms.

## Rule Schema Template (Sigma YAML)

```yaml
title: Suspicious Process Execution - Extracted Threat Pattern
id: 00000000-0000-0000-0000-000000000000
status: experimental
description: Detects process creation events associated with newly analyzed threat campaign telemetry.
author: Hermes Autonomous CTI Agent
references:
    - https://hermes-cti-portal.local/advisories/latest
tags:
    - attack.execution
    - attack.t1059.001
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith:
            - '\powershell.exe'
            - '\cmd.exe'
        CommandLine|contains:
            - '-enc'
            - 'DownloadString'
    condition: selection
falsepositives:
    - Administrative maintenance scripts
level: high
```

## Step-by-Step Procedure
1. **Analyze TTP Telemetry:** Identify process command-lines, parent-child relationships, network connections, or registry modifications.
2. **Map MITRE ATT&CK IDs:** Identify specific Technique IDs (e.g., `T1059.001`, `T1055`).
3. **Synthesize Sigma YAML:** Generate YAML matching official Sigma HQ specification.
4. **Translate Queries:** Convert Sigma logic into native Splunk SPL and Elastic KQL strings.
5. **Validate Syntax:** Ensure fields and operators strictly match SIEM schema standards.
