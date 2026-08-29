---
name: threat-hunting
description: Produce a two-tiered evidence-backed threat-hunting playbook with rapid play-by-play and deep operational phases.
---

# Threat hunting

Synthesize a comprehensive, two-tiered threat hunting playbook:

1. **Rapid Play-by-Play Summary (`procedure`):**
   Provide a crisp 4-step summary sequence for rapid triage:
   (1) Scope and target identification
   (2) SIEM/EDR hunting logic & baseline search
   (3) Triage branch points & false-positive elimination
   (4) Containment & forensic validation

2. **In-Depth Operational Playbook (`execution_phases`):**
   Structure the deep-dive investigation into ordered operational phases:
   - **Phase 1: Pre-Hunt Preparation & Telemetry Baselines** (target log sources, prerequisite event IDs, baseline filters).
   - **Phase 2: Query Execution & Anomaly Sweeps** (broad discovery sweeps transitioning to filtered anomaly queries).
   - **Phase 3: Triage & Anomaly Confirmation** (distinguishing benign system/admin activity from true malicious indicators, pivot logic).
   - **Phase 4: Forensics & Evidence Preservation** (host memory/disk artifacts, volatile data to capture, and escalation criteria).

3. **Typed Queries (`typed_queries`):**
   Provide structured query objects specifying `language` (e.g. `kql`, `spl`, `sigma`, `esql`), `title`, `query`, `target_log_sources`, and `tuning_guidance`.

4. **Forensic Artifacts & Pivots (`forensic_artifacts`, `pivot_guidance`):**
   List concrete investigative pivot tips and specific forensic artifacts (e.g. MFT, Prefetch, PowerShell scriptblock logs) with supporting evidence IDs.

