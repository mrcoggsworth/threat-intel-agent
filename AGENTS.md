# Multi-Agent Collaboration Rules

## Roles & Responsibilities
- **Hermes Orchestrator (`main.py`)**: Coordinates daily collection jobs, invokes extraction pipelines, triggers playbook synthesis, and calls site builder.
- **Ingestion Subagent (`hermes.ingestion`)**: Handles network requests, RSS feed parsing, HTML/PDF scraping, and rate limiting.
- **Analysis Subagent (`hermes.analysis`)**: Handles regex IOC extraction, CVE enrichment via external APIs, and MITRE ATT&CK technique tagging.
- **Playbook Subagent (`hermes.playbooks`)**: Generates structured Sigma, YARA, Splunk SPL, and KQL detection rules alongside hunt playbooks.
- **Publisher Subagent (`hermes.publisher`)**: Rebuilds static portal pages, generates JSON feeds, and sends webhooks.

## CTI Operational Workflow

- Treat `config/sources.json` as the authoritative ingestion registry; do not duplicate or silently alter feed URLs in code or prompts.
- Apply source precedence by evidence quality: CISA and vendor advisories, original threat research, incident-response reporting, then general security news.
- For each research run, record source URL, publication time, collection time, and processing status. Deduplicate by canonical URL, advisory ID, CVE, and campaign identity before publishing.
- Run the applicable reusable skills from the active Hermes profile: `ioc-parser`, `threat-enrichment`, `sigma-rule-generator`, `yara-author`, `cti-analysis`, and `threat-hunting`. Do not claim a stage ran when its tool, API, credentials, or evidence was unavailable.
- Keep generated IoCs and detection artifacts machine-readable. Preserve provenance for every IoC, CVE, attribution claim, and mitigation.
- Generate Sigma/SPL/KQL, YARA, or a two-tiered hunt playbook (4-step modal summary and multi-phase deep dive) only when the input evidence supports it or the user requests it; otherwise state what is missing.
