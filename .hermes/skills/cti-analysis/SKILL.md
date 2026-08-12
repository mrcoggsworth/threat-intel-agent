---
name: cti-analysis
description: Procedural guide for harvesting, validating, and scoring threat intelligence data.
---

# CTI Analysis Procedure

1. **Ingest Unstructured Feed:** Fetch raw content from security news, RSS feeds, or CVE databases.
2. **Extract IOCs:** Parse IP addresses, domain names, hashes, and URLs using regex patterns.
3. **Enrich Threat Telemetry:** Cross-reference extracted indicators with EPSS metrics, CVSS scores, and CISA KEV catalogs.
4. **ATT&CK Mapping:** Tag extracted techniques with MITRE ATT&CK enterprise tactic IDs.
