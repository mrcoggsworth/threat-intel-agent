# Hermes Daily CTI Briefing — 2026-08-26

**Collection window:** 2026-08-25 13:01:20Z to 2026-08-26 13:01:20Z  
**Assessment:** **CRITICAL**  
**Scope:** Enterprise-relevant active exploitation, AI infrastructure exposure, and high-value Windows/identity research. Prior report and 24–48h session/memory review completed; carried-forward items are not repeated as new findings.

## BLUF

1. **NEW / CRITICAL — Gitea `CVE-2026-60004`:** CISA added the Gitea code-injection flaw to KEV on **2026-08-25** based on active exploitation. The vulnerable `diffpatch` path can plant an executable Git hook and run shell commands as the Gitea service account. A reported incident deployed a miner-like dropper. **CISA due date: 2026-08-28.** Patch to **1.27.1+**, disable open registration unless required, and investigate exposed instances.
2. **NEW / HIGH — NVIDIA NemoClaw `CVE-2026-65105`:** NVD published a high-severity missing-authentication issue on **2026-08-25** affecting NemoClaw for Linux through version **0.0.25**. The published research describes an Ollama bind configuration that can expose port 11434 and permit browser/DNS-rebinding access to the inference API. NVD reports information disclosure and denial of service; the research additionally describes persistent chat-template poisoning. **No exploitation or KEV listing was verified.**
3. **NEW / HIGH research watch — SLEEPWALKER:** A previously undocumented Windows DLL backdoor uses ESET `ERAAgent.exe` side-loading, impersonates `dpapi.dll`, remains dormant in memory, and wakes on a crafted packet. It uses AES-256-CCM and a 23-instruction bytecode language. No victim, actor, campaign, or current exploitation was established; prioritize targeted ESET-agent environments because conventional outbound-connection hunting can miss it.
4. **24–48h context / HIGH — Mirage2FA:** ANY.RUN reporting cited by The Hacker News links the commercial AiTM phishing toolkit to **4,532 organization email domains** and **9,000+ potential compromise events**, with Microsoft 365 session-cookie theft and conventional MFA bypass. It is outside the strict 24h cutoff by approximately one hour at collection time and is therefore **not counted in the primary 24h total**, but remains an enterprise identity-hunting priority.

## Priority findings

| Status | Finding | Severity | Enrichment / confidence | Required action |
|---|---|---:|---|---|
| **NEW / KEV** | Gitea `CVE-2026-60004` | **CRITICAL** | CISA KEV; added 2026-08-25; due 2026-08-28; CVSS 9.8 reported by independent coverage; NVD/EPSS record not returned at query time | Upgrade to 1.27.1+; disable open registration and public exposure where unnecessary; review `diffpatch`, Git-hook, process, CPU, and outbound telemetry; rotate secrets after confirmed compromise. |
| **NEW** | NVIDIA NemoClaw `CVE-2026-65105` | **HIGH** | NVD CVSS 8.1, CWE-306; affected Linux 0–0.0.25; no EPSS record; not KEV; exploitation not reported | Upgrade per NVIDIA advisory; bind Ollama to loopback; block 11434 from untrusted networks; monitor `/api/create`, `/api/show`, model downloads, model deletions, and chat-template changes. |
| **NEW / RESEARCH WATCH** | SLEEPWALKER passive Windows backdoor | **HIGH** | Independent reverse-engineering report; no confirmed victims or attribution | Hunt unsigned `dpapi.dll` beside `ERAAgent.exe`, `dpapisvc.dll`, memory-resident modules, crafted-packet behavior, and anomalous named-pipe/TCP activity; preserve memory before cleanup. |
| **CONTEXT / 24–48H** | Mirage2FA Microsoft 365 AiTM campaign | **HIGH** | ANY.RUN reporting: 4,532 organization domains potentially linked and 9,000+ potential compromise events; contributed coverage, no actor attribution | Require phishing-resistant authentication; revoke sessions/tokens, not only passwords; correlate sign-ins, device/user-agent changes, impossible travel, and SSO-connected app access. |

## ATT&CK mapping

| Finding | Techniques supported by observed behavior |
|---|---|
| Gitea `CVE-2026-60004` | `T1190` Exploit Public-Facing Application; `T1059.004` Unix Shell; `T1203` Exploitation for Client Execution is **not** asserted because the service-side execution path is the supported behavior. |
| NemoClaw `CVE-2026-65105` | `T1189` Drive-by Compromise (browser-to-local service path); model metadata/configuration access is treated as collection against an inference service, without asserting `T1530` cloud-storage access. |
| SLEEPWALKER | `T1574.002` DLL Side-Loading; `T1055` Process Injection is **not** asserted without injection evidence; `T1027` Obfuscated/Compressed Files or Information (encrypted command bytecode); `T1105` Ingress Tool Transfer only if staged payload transfer is observed. |
| Mirage2FA | `T1539` Steal Web Session Cookie and `T1078.004` Valid Accounts: Cloud Accounts; do not infer a specific network-layer `T1557` sub-technique from the reporting alone. |

## Deterministic IoCs and artifacts

Parser output: `portal/iocs_20260826.json`  
Raw extraction across four selected articles: **0 routable IPv4, 0 IPv6, 0 MD5, 0 SHA-256, 0 malicious domains, 0 URLs, and 0 registry keys**. Current CVE identifiers retained after provenance filtering: **2** (`CVE-2026-60004`, `CVE-2026-65105`); **1** GHSA (`GHSA-rcr6-4jqh-j84m`). Historical/navigation matches (`CVE-2026-58231`, `CVE-2024-28224`) and platform/file-name domain matches were excluded.

### High-value artifact indicators

- Gitea: `diffpatch`, executable `git hook`, `DISABLE_REGISTRATION = false`, `ENABLE_OPENID_SIGNUP = true`
- NemoClaw/Ollama: `OLLAMA_HOST=0.0.0.0:11434`, `/api/create`, `/api/show`, `NEMOCLAW_OLLAMA_PROXY_SKIP_BIND_PROBE=1`
- SLEEPWALKER: `dpapi.dll`, `dpapisvc.dll`, `ERAAgent.exe`, AES-256-CCM, 23-instruction bytecode

These are behavioral/file artifacts, not confirmed customer-specific IoCs. Do not block the benign configuration strings without validating deployment context.

## Detection artifacts

Generated artifacts:

- Sigma YAML: `portal/sigma_gitea_cve_2026_60004.yml`, `portal/sigma_nemoclaw_cve_2026_65105.yml`, `portal/sigma_sleepwalker.yml`, `portal/sigma_mirage2fa.yml`
- Splunk SPL: `portal/spl_20260826.txt`
- Elastic KQL: `portal/kql_20260826.txt`
- YARA: `portal/yara_20260826.yar` (triage-oriented; compile validation required)

Field names are intentionally generic where source telemetry schemas differ. Validate against local CIM/ECS/Entra mappings before production deployment.

## Four-step investigation playbook

### 1. Scope & target identification
- Inventory Gitea versions and internet exposure; identify open registration, repository creation rights, and service-account privileges.
- Inventory NemoClaw/Linux deployments, Ollama bind addresses, port 11434 exposure, proxy-bypass settings, and model-template provenance.
- Identify Windows endpoints running ESET `ERAAgent.exe`; baseline signed modules and expected `dpapi.dll` location.
- For identity scope, identify Microsoft 365 tenants, authentication methods, session/token controls, and SSO-connected applications.

### 2. SIEM/EDR hunting methodologies
- Deploy the four Sigma rules and review `spl_20260826.txt` / `kql_20260826.txt` after field normalization.
- Gitea: pivot from `/diffpatch` requests to repository creation, Git-hook writes, child shells, CPU spikes, downloads, and outbound connections.
- NemoClaw: hunt non-loopback Ollama listeners, `/api/create` or model-management calls, unexpected model/template modifications, and browser-originated requests.
- SLEEPWALKER: inspect image-load telemetry, unsigned DLLs beside `ERAAgent.exe`, memory, named pipes, and inbound crafted-packet candidates; absence of egress is not exculpatory.
- Mirage2FA: correlate successful sign-ins with session-cookie/token events, user-agent/device changes, impossible travel, new OAuth/SSO access, and post-login mailbox/application activity.

### 3. Triage & containment
- Isolate suspected Gitea or Windows hosts while preserving volatile evidence; revoke sessions and rotate credentials/secrets for confirmed compromise.
- Patch Gitea and NemoClaw; restrict management/inference services to trusted networks and remove unnecessary open registration or proxy-bypass settings.
- For suspected SLEEPWALKER, capture memory and disk before deletion; quarantine only after collection and validation.
- For Mirage2FA, revoke cloud sessions/tokens, reset credentials, require phishing-resistant MFA, and review OAuth grants and mailbox rules.

### 4. Forensic validation
- Preserve Gitea web/API/audit logs, Git repositories, service-account activity, process trees, and network flow data.
- Record NemoClaw/Ollama configuration, model manifests, chat templates, browser history, DNS responses, and API access logs; compare with known-good templates.
- Hash collected DLLs and compare against the YARA triage rule only as a lead; verify signatures, load paths, memory behavior, and packet handling manually.
- Validate absence of unauthorized repositories/hooks, hidden model instructions, persistence, new identities, OAuth grants, forwarding rules, and post-compromise cloud activity.

## Collection and enrichment caveats

- **20** entries were collected from the 24h window across **15** configured/supplemental sources; only the four findings above met enterprise-grade filtering. The Gitea item was independently verified against the direct CISA alert and corrected direct KEV JSON parsing; the KEV JSON contains the Gitea record with due date 2026-08-28.
- Source status: **11 OK**, **4 unavailable/parse-failed** (Google TAG HTTP 404, Microsoft Threat Intelligence HTTP 403, SANS ISC malformed response, MSRC malformed response). No claims were made from failed feeds.
- AbuseIPDB, VirusTotal, and OTX were not queried because no network/hash indicators were available and no API credentials were configured. EPSS returned no record for the two current CVEs at query time.
- Mirage2FA is explicitly labeled 24–48h context; broad consumer/device fraud, Norway DDoS, general AI commentary, and non-actionable Windows privacy news were excluded.

## Sources

1. CISA, “CISA Adds One Known Exploited Vulnerability to Catalog” (2026-08-25): https://www.cisa.gov/news-events/alerts/2026/08/25/cisa-adds-one-known-exploited-vulnerability-catalog
2. CISA KEV JSON: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
3. The Hacker News, “Critical Gitea RCE Actively Exploited…” (2026-08-26): https://thehackernews.com/2026/08/critical-gitea-rce-actively-exploited.html
4. SecurityWeek, “CISA Warns of Exploited Gitea Vulnerability”: https://www.securityweek.com/cisa-warns-of-exploited-gitea-vulnerability/
5. NVD, `CVE-2026-65105`: https://nvd.nist.gov/vuln/detail/CVE-2026-65105
6. The Hacker News, “A Malicious Webpage Could Poison Your Local AI Model Behind NVIDIA NemoClaw” (2026-08-25): https://thehackernews.com/2026/08/a-malicious-webpage-could-poison-your.html
7. NVIDIA PSIRT reference: https://github.com/NVIDIA/product-security/tree/main/2026/5872
8. The Register, “You don't want this Sleepwalker backdoor…” (2026-08-24): https://www.theregister.com/security/2026/08/24/you-dont-want-this-sleepwalker-backdoor-on-your-windows-machine/5292021
9. SLEEPWALKER technical analysis: https://r136a1.dev/2026/08/24/sleepwalker-a-passive-backdoor-with-its-own-command-language/
10. The Hacker News, “Mirage2FA Surge Hits 4,500 US and EU Companies…” (2026-08-25): https://thehackernews.com/2026/08/mirage2fa-surge-hits-4500-us-and-eu.html
11. ANY.RUN, “Mirage2FA: A Phishing Threat to US Companies…”: https://any.run/cybersecurity-blog/mirage2fa-phishing-targets-us-companies/
12. Cisco Talos feed collection: https://blog.talosintelligence.com/rss/
13. Palo Alto Unit 42 feed collection: https://unit42.paloaltonetworks.com/feed/
14. BleepingComputer feed collection: https://www.bleepingcomputer.com/feed/
15. The Hacker News supplemental feed: https://feeds.feedburner.com/TheHackersNews
