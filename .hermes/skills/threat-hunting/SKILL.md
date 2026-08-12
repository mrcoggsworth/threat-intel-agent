---
name: threat-hunting
description: Procedural guide for synthesizing Sigma rules, YARA rules, and hunt playbooks.
---

# Threat Hunting Synthesis Procedure

1. **Analyze TTP Behavior:** Identify process execution, command-line arguments, registry modifications, or network connections.
2. **Synthesize Detection Rules:**
   - Write **Sigma** rules for log-based detection.
   - Write **YARA** rules for file artifact and memory scanning.
   - Write **KQL** and **Splunk SPL** queries for SIEM hunting.
3. **Generate Remediation Guide:** Document step-by-step containment, network isolation, and patch validation procedures.
