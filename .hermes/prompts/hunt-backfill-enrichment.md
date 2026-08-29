You are the CTI-Hermes analyst controller operating under the cti-analyst profile.
Project root: /home/cptcoggsworth/code/threat-intel-agent
Scope: Public Cyber Threat Intelligence corpus and threat hunt enrichment.

Task Objective:
Perform a comprehensive threat hunt enrichment review across all active published reports (2024–2026 CVEs, threat campaigns, malware analyses, and supply chain advisories). Upgrade all legacy threat hunt structures to our two-tiered hunting schema.

Instructions:

1. Inventory & Evidence Ingestion:
   - Query the public report repository for published reports currently lacking detailed `execution_phases` or `typed_queries`.
   - Retrieve the underlying evidence items, technical analysis, and IOCs for each target report.

2. Synthesize Two-Tiered Threat Hunt Playbooks:
   For each report where evidence supports hypothesis-driven threat hunting, generate:
   
   A. Rapid Modal Triage Sequence (`procedure`):
      - A concise, 4-step play-by-play workflow suited for fast SOC modal review:
        1) Telemetry validation & baseline scoping
        2) Primary behavioral detection query execution
        3) Benign baseline / false-positive elimination
        4) Triage confirmation & escalation handover
        
   B. Syntax-Highlighted Structured Queries (`typed_queries`):
      - Provide production-ready queries with designated languages (e.g., `kql`, `spl`, `eql`, `sigma`).
      - Include `title`, `target_log_sources` (e.g., `DeviceProcessEvents`, `Sysmon Event 1`, `Security 4688`), and actionable `tuning_guidance` to filter out legitimate administrative noise.

   C. Multi-Phase Operational Deep Dive (`execution_phases`):
      - Phase 1: Baseline & Telemetry Scoping (log sources, coverage checks, normal traffic volume baselines).
      - Phase 2: Hypothesis Validation & Behavioral Sweep (hunting queries, anomalous process arguments, parent-child execution patterns).
      - Phase 3: Triage & False-Positive Elimination (whitelisting known signed software, benign updater patterns, hash validation).
      - Phase 4: Scope Expansion & Evidence Preservation (lateral movement checks, network beaconing correlation, persistence mechanisms).

   D. Forensic Artifact Preservation (`forensic_artifacts`):
      - Concrete host/network artifacts for responders to preserve (e.g., Prefetch, ShimCache, PowerShell 4104 logs, MFT records, memory dumps).

   E. Pivot Guidance (`pivot_guidance`):
      - Specific instructions for pivoting to secondary telemetry (e.g., correlating anomalous rundll32/powershell execution with Scheduled Task creation Event ID 4698 or outbound C2 network traffic).

3. Validation & Persistence:
   - Validate each enriched `ThreatHunt` object against the domain contract (`hermes_cti.models.contracts.ThreatHunt`).
   - Submit the updated report version proposals through the supported CTI reporting pipeline, preserving all existing evidence IDs and provenance links.
   - If an existing report lacks sufficient technical evidence to construct a full multi-phase hunt, maintain the existing baseline and log the missing requirements.

Output Summary:
Return a structured summary detailing:
- Total reports reviewed
- Total threat hunt playbooks successfully upgraded with multi-phase execution data
- Breakdown of generated detection query types (KQL, SPL, etc.)
- Any reports skipped due to insufficient behavioral evidence
