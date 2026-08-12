---
name: threat-enrichment
description: Queries external OSINT APIs (AbuseIPDB, VirusTotal, AlienVault OTX, CISA KEV) to attach risk scores and telemetry context to raw IoCs.
---

# 🛡️ threat-enrichment // API Lookups & Reputation Scoring Skill

## Overview
Raw IoCs (such as an isolated IP address or file hash) lack critical context. The `threat-enrichment` skill queries external OSINT APIs (such as AbuseIPDB, VirusTotal, AlienVault OTX, and CISA KEV) to assess reputation scores, malicious flags, ASN details, and threat actor attribution before dispatching alerts.

## Why Create It
- Distinguishes high-risk malicious infrastructure from benign CDNs, DNS resolvers, or Cloud proxies.
- Quantifies risk via EPSS scores, VirusTotal detection ratios, and AbuseIPDB confidence scores.
- Enriches alerts dispatched to webhooks (Discord, Slack, Teams) with context.

## API Integration Matrix

| Target API | Query Parameter | Enriched Telemetry |
| :--- | :--- | :--- |
| **AbuseIPDB** | IPv4 / IPv6 | Abuse Confidence Score, ISP, Country, Total Reports |
| **VirusTotal** | MD5 / SHA256 / URL | Malicious Engine Detections, Threat Classification |
| **AlienVault OTX** | IP / Domain / Hash | Associated Pulse IDs, Threat Actor Tags |
| **CISA KEV** | CVE ID | Active Exploitation Status, Vendor Action Required |

## Step-by-Step Procedure
1. **Receive Sanitized IoCs:** Consume JSON IoC payload from `ioc-parser`.
2. **Execute Parallel Lookups:** Query OSINT endpoints using configured API keys or free public endpoints.
3. **Calculate Composite Risk Score:** Assign severity rating (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
4. **Format Enriched Payload:** Construct enriched threat digest for Webhook dispatchers and web portal database sync.
