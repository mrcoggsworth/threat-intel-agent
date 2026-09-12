---
name: cti-analysis
description: Structure public CTI analysis from evidence through ATT&CK mapping.
---

# CTI Analysis

Structure high-fidelity cyber threat intelligence reports, enrich vulnerabilities and indicators, and map behaviors to MITRE ATT&CK techniques with rigorous provenance.

## Operational Workflow & Tooling

### 1. Health & Backend Check
Before processing evidence, verify service connectivity and token validity:
```bash
hermes-cti analyst health
```

### 2. Identifier Sequence Resolution
When synthesizing a new report, query the next public ID dynamically:
```bash
hermes-cti analyst next-public-id
```
Never guess or hardcode sequence numbers (e.g. `PUB-2026-001`) without querying existing records.

### 3. Sourced Evidence Attribution
- Review raw documents from the daily ingestion run across all active threat feeds.
- Every indicator, vulnerability, ATT&CK mapping, and remediation step must link back to one or more `evidence_id` values.
- Maintain high precision: extract root causes (CWEs, memory corruption, command injection), parent/child telemetry anomalies, and observable network/host artifacts.

### 4. Grounding and Factuality
- Strictly separate public factual reporting from analytical hypothesis.
- Never assert internal environment exposure or compromised hosts.
- Validate report bundles locally using `hermes-cti analyst validate-bundle <bundle.json>` before publication.
