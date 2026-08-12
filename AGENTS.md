# Multi-Agent Collaboration Rules

## Roles & Responsibilities
- **Hermes Orchestrator (`main.py`)**: Coordinates daily collection jobs, invokes extraction pipelines, triggers playbook synthesis, and calls site builder.
- **Ingestion Subagent (`hermes.ingestion`)**: Handles network requests, RSS feed parsing, HTML/PDF scraping, and rate limiting.
- **Analysis Subagent (`hermes.analysis`)**: Handles regex IOC extraction, CVE enrichment via external APIs, and MITRE ATT&CK technique tagging.
- **Playbook Subagent (`hermes.playbooks`)**: Generates structured Sigma, YARA, Splunk SPL, and KQL detection rules alongside hunt playbooks.
- **Publisher Subagent (`hermes.publisher`)**: Rebuilds static portal pages, generates JSON feeds, and sends webhooks.
