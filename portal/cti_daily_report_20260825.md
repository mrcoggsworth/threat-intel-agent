# Hermes Daily CTI Briefing — 2026-08-25

**Collection window:** 2026-08-24 13:01:37Z to 2026-08-25 13:01:37Z  
**Assessment:** **CRITICAL**  
**Scope:** Enterprise-relevant vulnerabilities, active exploitation, and actionable threat research. Prior 24–48h memory/session review completed; repeated items are labeled **UPDATE**.

## BLUF

1. **NEW — Oracle HTTP Server/WebLogic Proxy Plug-in CVE-2026-21962:** CISA added the CVSS 10.0 flaw to KEV on August 24 based on active exploitation. Affected versions include 12.2.1.4.0, 14.1.1.0.0, and 14.1.2.0.0; CISA remediation due date is **2026-08-27**.[1][2][5]
2. **UPDATE — Zimbra CVE-2026-73570:** Shadowserver reporting cited by BleepingComputer identified **more than 270** compromised Internet-exposed Zimbra instances. This previously reported KEV item remains an active incident-response priority; the KEV due date was 2026-08-24.[1][3]
3. **NEW — miniOrange SAML SSO WordPress compromise path:** Active exploitation targets CVE-2026-61979 (CVSS 8.1) and CVE-2026-15981 (CVSS 9.8), enabling forged SAML assertions or malformed-signature bypass to log in as arbitrary WordPress users, including administrators. A public PoC is reported.[4][6][9]
4. **NEW — E4del/PINHOLE RAT delivery:** A campaign uses FTP banners as dead-drop resolvers to deliver two previously unreported Windows RATs. The chain uses PowerShell, MSXML2.XMLHTTP, Cloudflare Workers, and a Discord-masquerading Electron application.[7][8]

## Priority findings

| Status | Finding | Severity | Enrichment / exposure | Required action |
|---|---|---:|---|---|
| **NEW** | Oracle HTTP Server / WebLogic Proxy Plug-in `CVE-2026-21962` | **CRITICAL** | CVSS 10.0; EPSS 0.4323 (98.62 percentile, 2026-08-24); CISA KEV; active exploitation; due 2026-08-27 [11][15] | Patch affected Oracle components immediately; restrict management/application exposure; preserve HTTP and WebLogic logs for exploitation review. |
| **UPDATE** | Zimbra Collaboration Suite `CVE-2026-73570` | **CRITICAL** | CVSS 8.9; EPSS 0.01506 (72.40 percentile); CISA KEV; >270 exposed instances reportedly compromised; fixed in 10.1.20 [12][16] | Upgrade to 10.1.20 or later; isolate Internet-facing hosts; inspect SMTP/SNMP and child-process telemetry; rotate credentials if compromise is confirmed. |
| **NEW** | miniOrange SAML 2.0 SSO for WordPress `CVE-2026-61979` + `CVE-2026-15981` | **CRITICAL** | CVSS 8.1 / 9.8; EPSS 0.00264 / 0.00796; not in KEV; exploitation and PoC reported [13][14][17][18] | Inventory all seven product editions, including paid editions; apply the edition-specific fixes (Standard 17.0.5 / 17.0.6 as applicable); review SAML logins, administrator creation, and session cookies. |
| **NEW** | E4del / PINHOLE FTP-banner dead-drop campaign | **HIGH** | No CVE; no actor attribution verified; Windows RATs with PowerShell execution, persistence, reverse shell, screenshots, file transfer, and Cloudflare-proxied C2 | Hunt FTP connections followed by PowerShell/MSXML2.XMLHTTP; block or monitor listed infrastructure; isolate hosts with matching execution chains and collect memory before remediation. |

### Enterprise context — AI-enabled malware

Unit 42 analyzed 405 SHA-256 samples integrating AI in some capacity; only 12 appeared in its production telemetry, so the majority were research, validation, or proof-of-concept samples rather than confirmed enterprise campaigns.[10] Treat the accompanying hashes as **sample triage data**, not as evidence of current victimization or a named actor.

## ATT&CK mapping

| Finding | Techniques supported by observed behavior |
|---|---|
| Oracle CVE-2026-21962 | `T1190` Exploit Public-Facing Application |
| Zimbra CVE-2026-73570 | `T1190` Exploit Public-Facing Application; `T1059.004` Unix Shell (command-injection outcome; validate in host telemetry) |
| miniOrange SAML | `T1190` Exploit Public-Facing Application; `T1606.002` Forge Web Credentials: SAML Tokens; `T1078` Valid Accounts (post-bypass use of a victim identity) |
| E4del/PINHOLE | `T1059.001` PowerShell; `T1105` Ingress Tool Transfer; `T1036` Masquerading; `T1102.002` Bidirectional Communication; `T1219` Remote Access Software (RAT capability) |
| Unit 42 sample context | `T1059.001` PowerShell, `T1112` Modify Registry, `T1070.004` File Deletion, and `T1490` Inhibit System Recovery are reported for specific ransomware samples; do not generalize them to all 405 samples. |

## Deterministic IoCs

Parser output: `/home/cptcoggsworth/workspace/cti24/iocs_20260825.json`  
Raw extraction counts: **11 routable IPv4, 12 SHA-256, 7 CVE identifiers, 0 MD5, 0 IPv6, 0 registry keys**. Raw domain matches were sanitized and manually filtered to remove filenames, PDB paths, and article/vendor domains.

### Network indicators

| Source / confidence | Indicators |
|---|---|
| E4del/PINHOLE — reported infrastructure | `157.254.194.31:21`, `167.148.41.164:21`, `209.99.185.38:21`, `69.48.228.126:5000`, `cloudflare.milicare.in/app/c` |
| miniOrange — reported scanning IPs | `207.211.214.41`, `79.127.224.14`, `102.91.71.83`, `162.243.116.148`, `84.201.6.54`, `64.225.25.188` |
| Oracle article — historical scanner, **not confirmed current campaign IoC** | `193.24.123.42` |

Do not block solely on the historical Oracle IP without corroborating telemetry. Treat E4del/PINHOLE and miniOrange indicators as reported indicators requiring local validation.

### File hashes

The 12 SHA-256 values from Unit 42 are preserved in the machine-readable IoC file and should be loaded into EDR/SIEM as sample triage indicators. They are not reproduced inline to reduce transcription risk. No MD5 values were observed.

## Detection artifacts

Generated and syntax-validated artifacts:

- Sigma YAML (PyYAML parse validation):
  - `portal/sigma_oracle_weblogic.yml`
  - `portal/sigma_zimbra.yml`
  - `portal/sigma_miniorange.yml`
  - `portal/sigma_e4del_pinhole.yml`
- Splunk SPL: `portal/spl_20260825.txt`
- Elastic KQL: `portal/kql_20260825.txt`
- YARA: `portal/yara_20260825.yar` (**yara-python compile OK**; rules are triage-oriented and require sample validation)

## Four-step investigation playbook

### 1. Scope & target identification
- Inventory Oracle HTTP Server/WebLogic Proxy Plug-in versions, Zimbra versions and `zimbra-snmp`/SNMP configuration, and every WordPress instance carrying any miniOrange SAML edition.
- Identify Internet exposure, reverse proxies, load balancers, and affected service accounts.
- Tag assets by finding, exposure, patch state, and whether any listed IoC was observed.

### 2. SIEM/EDR hunting
- Deploy the four Sigma rules and corresponding SPL/KQL queries.
- For Oracle and Zimbra, pivot from inbound HTTP/SMTP/SNMP events to child processes, shell execution, outbound connections, and file writes.
- For miniOrange, correlate SAML endpoint requests with malformed-signature errors, administrator logins, password/session changes, and the six reported scanner IPs.
- For E4del/PINHOLE, hunt FTP connections followed by PowerShell, `MSXML2.XMLHTTP`, `%TEMP%u.cmd`, Electron/Discord masquerading, and Cloudflare Worker traffic.

### 3. Triage & containment
- Isolate suspected Zimbra, Oracle, WordPress, or Windows hosts from the network while preserving volatile evidence.
- Patch or remove vulnerable components; revoke active sessions and rotate credentials/tokens for confirmed compromise.
- Block or sinkhole confirmed malicious infrastructure only after validating ownership and avoiding the historical Oracle-IP false-positive risk.

### 4. Forensic validation
- Preserve web, SMTP, FTP, PowerShell, Sysmon, WordPress, SAML, and authentication logs across the relevant exposure windows.
- Capture memory and disk triage before cleanup; hash collected binaries and compare against the Unit 42 sample set.
- Validate no persistence, unauthorized administrator, modified SAML configuration, new scheduled task/service, web shell, or cloud credential access remains.

## Collection caveats and exclusions

- The CISA KEV JSON was queried directly and contains `CVE-2026-21962` (added 2026-08-24) and `CVE-2026-73570`; the generic collector's CISA date filter returned an empty entry list and was not treated as authoritative.
- Google TAG returned HTTP 404; SANS ISC and MSRC had parser failures; no claims were made from those feeds.
- Calix GS7 XGS router exposure, broad cybercrime arrests, consumer malware, and generic AI-vulnerability commentary were excluded from the enterprise-grade alert set.

## Sources

[1] https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json — CISA KEV catalog
[2] https://www.cisa.gov/news-events/alerts/2026/08/24/cisa-adds-one-known-exploited-vulnerability-catalog — CISA adds CVE-2026-21962
[3] https://www.bleepingcomputer.com/news/security/hackers-breached-over-270-zimbra-servers-in-ongoing-attacks — BleepingComputer Zimbra compromises
[4] https://www.bleepingcomputer.com/news/security/hackers-target-wordpress-sites-in-miniorange-auth-bypass-attacks — BleepingComputer miniOrange exploitation
[5] https://thehackernews.com/2026/08/actively-exploited-oracle-weblogic-flaw.html — The Hacker News Oracle WebLogic
[6] https://thehackernews.com/2026/08/attackers-target-miniorange-saml-flaws.html — The Hacker News miniOrange
[7] https://thehackernews.com/2026/08/e4del-and-pinhole-rats-turn-ftp-banners.html — The Hacker News E4del/PINHOLE
[8] https://socradar.io/blog/ftp-banners-new-dead-drop-resolver-rats — SOCRadar FTP banner RAT research
[9] https://patchstack.com/articles/one-slug-seven-editions-the-miniorange-saml-sso-bug-that-let-anyone-log-in-as-your-wordpress-admin — Patchstack miniOrange analysis
[10] https://unit42.paloaltonetworks.com/ai-enabled-malware-analysis — Unit 42 AI-enabled malware
[11] https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-21962 — NVD CVE-2026-21962
[12] https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-73570 — NVD CVE-2026-73570
[13] https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-15981 — NVD CVE-2026-15981
[14] https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2026-61979 — NVD CVE-2026-61979
[15] https://api.first.org/data/v1/epss?cve=CVE-2026-21962 — FIRST EPSS CVE-2026-21962
[16] https://api.first.org/data/v1/epss?cve=CVE-2026-73570 — FIRST EPSS CVE-2026-73570
[17] https://api.first.org/data/v1/epss?cve=CVE-2026-15981 — FIRST EPSS CVE-2026-15981
[18] https://api.first.org/data/v1/epss?cve=CVE-2026-61979 — FIRST EPSS CVE-2026-61979
