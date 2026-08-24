# Hermes Daily CTI Briefing & Playbook Synthesis — 2026-08-20

**Collection time:** `2026-08-20T13:00:49Z`  
**Window:** `2026-08-19T13:00:49Z`–`2026-08-20T13:00:49Z`; 48-hour deduplication context  
**Assessment:** **CRITICAL**  
**Scope:** Enterprise web infrastructure, remote access, OT/ICS, AI/ML platforms, mission systems, and high-impact endpoint/server threats.

## BLUF

1. **UAT-10147 is operating a cross-platform post-compromise ecosystem against Internet-facing IIS and Linux servers.** Cisco Talos observed agentic-AI-assisted exploitation workflows, SPECTRE, a Linux kernel rootkit, BYOVD EDR neutralization, credential theft, and the routable download IP `139.180.197.150`. This is the most significant new campaign-level item.
2. **Zimbra Collaboration Suite `CVE-2026-73570` is being actively exploited.** The unauthenticated SNMP-notification command-injection flaw enables OS command execution as the `zimbra` user. Upgrade to `10.1.20+` and inspect the specified Jetty and `/tmp` paths.
3. **FUXA OT/SCADA vulnerabilities are under malicious scanning.** `CVE-2026-25895` enables unauthenticated arbitrary file writes/path traversal, while related FUXA flaws `CVE-2026-25939` and `CVE-2023-33831` expose authorization/RCE paths. Remove Internet exposure and upgrade to fixed versions.
4. **NASA/JPL AIT-GUI has a critical command-bus exposure with inconsistent advisory records.** `GHSA-p9r8-2q67-fp86` (Cycode: CVSS 9.4) and `CVE-2026-60112` (NVD: CVSS 9.3) describe unauthenticated session issuance and arbitrary spacecraft/instrument commands. The sources disagree on affected/fixed releases; treat AIT-GUI as potentially exposed until source-level validation is complete.
5. **CISA KEV status for MLflow `CVE-2026-64849` is a material UPDATE, not a new vulnerability.** CISA added it on 2026-08-19 with a federal due date of 2026-09-02. Prior reporting already identified active exploitation; prioritize public MLflow deployments and cloud credential rotation.
6. **Citrix NetScaler `CVE-2026-19490` authentication bypass and `CVE-2026-19489` DoS are new urgent patch items.** Citrix/BleepingComputer state that exploitation has not been reported for these two flaws, but NetScaler Gateway/ADC is high-value remote-access infrastructure and exposed instances are numerous.
7. **Elementor Pro `CVE-2026-32475` is a new pre-auth PHP upload/RCE issue.** It affects versions through `4.2.1`; Elementor released `4.2.2` on 2026-08-19. No active exploitation was reported in the collected source, so this is an urgent patch/watch item rather than an exploitation alert.

## Deduplication and provenance

- `.hermes/memories/MEMORY.md` records Microsoft July Patch Tuesday (`CVE-2026-56155`, `CVE-2026-56164`) and SharePoint `CVE-2026-55040`; none are repeated as new findings.
- The prior 2026-08-19 report already covered CISA AA26-231A, the four 2026-08-18 KEV additions, MLflow exploitation, Windchill/FlexPLM, and SilkParasite. Those items are suppressed except for **MLflow as a KEV/update state change**.
- Session history was searched for recent CVE, zero-day, and APT overlap. Previously reported Microsoft, SharePoint, Cisco ASA/FTD, Lazarus, Siemens S7, Windchill, SilkParasite, and MLflow items were treated as duplicates or updates.
- Source precedence: CISA and NVD/FIRST for vulnerability status and scoring; Cisco Talos, CERT Polska/BleepingComputer, Cycode/THN, and Citrix for technical reporting. The Hacker News is supplemental and does not override primary advisory data.
- Feed collection status: CISA KEV/advisories, Cisco Talos, Unit 42, Microsoft Threat Intelligence, SANS ISC, ZDI, Krebs, BleepingComputer, and the supplemental Hacker News feed were reachable; DFIR had no entries in the 48-hour window; Google TAG returned 404; MSRC was malformed; SentinelLabs and Red Canary returned no parseable recent entries.

## Priority findings

### 1. UAT-10147 / SPECTRE cross-platform intrusion ecosystem

| Field | Assessment |
|---|---|
| Status | **NEW — active observed intrusion activity** |
| Published | 2026-08-20 10:00 UTC (Cisco Talos) |
| Targets | Internet-facing IIS and Linux servers; government, education, media, technology, and gaming sectors |
| Actor | UAT-10147; Talos assesses a Chinese-speaking, financially motivated intrusion operator with moderate-to-high confidence |
| Tooling | SPECTRE backdoor; Specter Linux rootkit; BadIIS; QuasarRAT; Meterpreter; Metasploit; PentestGPT; DeepAudit; ysoserial |
| Observed behavior | Agentic-AI-assisted exploit refinement/reconnaissance/payload generation/validation; web-server RCE; EfsPotato; Defender exclusion changes; process injection; SAM/SYSTEM/SECURITY hive dumping; browser credential theft; BYOVD EDR blinding; Linux systemd/kernel-module persistence |
| Observed network IoC | `139.180.197.150` — Talos-described download server/open directory; validate ownership and current activity before blocking |
| Other observed artifacts | `adminapi.tippusoni.in/4/dll.zip`, `adminapi.tippusoni.in/4/user.txt`, `webhook.site` callback use, `X-ID` header, `/api/v1/register`, `/api/v1/output`, `acpi_pad.ko`, `hardware-monitor.service`, `RTCore64.sys`, `DBUtil_2_3.sys` |
| ATT&CK | `T1190`, `T1059.003`, `T1059.004`, `T1055`, `T1562.001`, `T1552.002`, `T1555.003`, `T1014`, `T1547.006`, `T1070.006`, `T1105`, `T1071.001`, `T1036` |

**Action:** Hunt for `certutil` retrieval, IIS/Windows Defender exclusion changes, unexpected IIS module/web-shell activity, vulnerable-driver loads, kernel-module/systemd persistence, `svchost.exe`/`RuntimeBroker.exe` injection, and suspicious outbound HTTP POSTs to the SPECTRE paths. Treat the Talos IP/domain as observed indicators, not proof of current C2 availability.

**Source:** [Cisco Talos — SPECTRE](https://blog.talosintelligence.com/uat-10147-deploys-spectre-a-cross-platform-implant-with-linux-rootkit-and-byovd-capabilities/) · [Cisco Talos — agentic-AI operations](https://blog.talosintelligence.com/uat-10147-chinese-speaking-adversary-integrates-agentic-ai-into-post-compromise-operations/)

### 2. Zimbra Collaboration Suite `CVE-2026-73570`

- **Status:** **NEW — active exploitation reported by CERT Polska**.
- **Impact:** Unauthenticated command injection in the optional `zimbra-snmp` component when SNMP notifications are enabled; crafted SMTP requests can execute OS commands as `zimbra`.
- **NVD:** CVSS **8.9**, vector `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:L`.
- **EPSS:** **0.00539**, **43.074th percentile**, 2026-08-19 snapshot. EPSS is not a safety signal when exploitation is directly reported.
- **Remediation:** Upgrade to ZCS `10.1.20+`; confirm whether `zimbra-snmp` and SNMP notifications are enabled; restrict exposure.
- **Triage:** Review unexpected Zimbra service restarts and files created by user `zimbra` during the last 30 days in `/opt/zimbra/jetty/webapps/`, `/opt/zimbra/jetty_base/webapps/`, and `/tmp/`.
- **ATT&CK:** `T1190` Exploit Public-Facing Application; `T1059.004` Unix Shell (post-exploitation behavior must be confirmed from process telemetry).

**Sources:** [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-73570) · [BleepingComputer/CERT Polska report](https://www.bleepingcomputer.com/news/security/critical-zimbra-rce-flaw-now-actively-exploited-in-attacks/)

### 3. FUXA OT/SCADA exploitation and scanning cluster

- **Status:** **NEW — malicious scanning observed; no RCE payload reported for the current `CVE-2026-25895` scanning activity**.
- `CVE-2026-25895`: unauthenticated remote path traversal/arbitrary file write through FUXA `<=1.2.9`; fixed in `1.2.10`. NVD CVSS **9.5**; EPSS **0.04742**, **91.144th percentile**.
- `CVE-2026-25939`: unauthenticated authorization bypass allowing arbitrary scheduler creation/modification in FUXA `1.2.8–1.2.10`; fixed in `1.2.11`. NVD CVSS **9.3**; EPSS **0.11393**, **95.641st percentile**.
- `CVE-2023-33831`: unauthenticated RCE through `/api/runscript` in FUXA 1.1.13. NVD CVSS **9.8**; EPSS **0.22707**, **97.538th percentile**. The reporting source cites exploitation activity as recent as 2026-08-17.
- **Mitigation:** Remove public exposure; upgrade to a supported release incorporating the fixes; isolate SCADA/HMI management; review for writes to `main.js`, scheduler changes, `/api/runscript` requests, and unexpected child processes.
- **ATT&CK:** `T1190`, `T1105` (where payload transfer is observed), `T1059.004` (only after process evidence confirms shell execution), `T1562.001` for defense-evasion actions if observed.

**Source:** [The Hacker News — MLflow/FUXA exploitation and scanning](https://thehackernews.com/2026/08/attackers-exploit-mlflow-ssrf-flaw-to.html) · [NVD CVE-2026-25895](https://nvd.nist.gov/vuln/detail/CVE-2026-25895)

### 4. NASA/JPL AIT-GUI command-bus exposure

- **Status:** **NEW — critical mission-system exposure; exploitation not reported**.
- **Observed capability:** Unauthenticated callers can obtain a session and issue arbitrary commands through `POST /cmd`; `/script/run` and `/seq` also expose script/path-traversal behavior in the reported chain.
- **Identifiers:** Cycode advisory `GHSA-p9r8-2q67-fp86` rates the chain **CVSS 9.4** and states versions `2.5.1` and earlier are affected with `2.5.2` as the stated fix. NVD separately records `CVE-2026-60112` at CVSS **9.3** for versions before `2.5.1`.
- **Evidence conflict:** THN’s source review reports unauthenticated session issuance still present in tagged `2.5.2` and notes that the records disagree. Do not mark this remediated solely from a version string; validate the actual source/build and command-bus network exposure.
- **EPSS for CVE-2026-60112:** **0.00408**, **34.207th percentile**, 2026-08-19 snapshot. No KEV entry.
- **Action:** Restrict AIT-GUI to localhost/approved management networks, require authenticated access at a trusted reverse proxy or equivalent control, test `/cmd`, `/script/run`, and `/seq`, and obtain an authoritative vendor fix statement.
- **ATT&CK:** `T1190`; `T1059.004` only when script execution is confirmed; `T1210` if the console is used to pivot into connected mission systems.

**Sources:** [Cycode/THN report](https://thehackernews.com/2026/08/nasa-ait-gui-flaws-could-let.html) · [NVD CVE-2026-60112](https://nvd.nist.gov/vuln/detail/CVE-2026-60112)

### 5. MLflow `CVE-2026-64849` — KEV status UPDATE

- **Status:** **UPDATE — previously reported exploitation; added to CISA KEV 2026-08-19**.
- **Impact:** Unauthenticated MLflow webhook-test SSRF can follow redirects to internal/cloud metadata services and return sensitive response data.
- **NVD:** CVSS **9.3**, vector `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N`.
- **EPSS:** **0.01109**, **63.280th percentile**, 2026-08-19 snapshot.
- **CISA KEV:** Added `2026-08-19`; federal due date **2026-09-02**; fixed in MLflow `3.15.0+`.
- **Action:** Upgrade, remove direct Internet exposure, restrict egress, block cloud metadata endpoints, search `/api/2.0/mlflow/webhooks/*/test`, and rotate any cloud credentials reachable from MLflow.
- **ATT&CK:** `T1190`, `T1552.005`, `T1046` only where scanning telemetry is present.

**Sources:** [CISA KEV JSON](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) · [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-64849) · [The Hacker News](https://thehackernews.com/2026/08/attackers-exploit-mlflow-ssrf-flaw-to.html)

### 6. Citrix NetScaler ADC/Gateway vulnerabilities

- **Status:** **NEW — urgent patch/watch; exploitation not reported for these two CVEs**.
- `CVE-2026-19490`: unauthenticated authentication bypass when configured as an AAA virtual server or Gateway with relevant SAML configuration. NVD CVSS **9.3** (CVSS 4.0); no EPSS score was returned by FIRST on 2026-08-19.
- `CVE-2026-19489`: unauthenticated memory-overflow DoS when SIP ALG is enabled on a large-scale NAT group. NVD CVSS **8.8**; no EPSS score was returned by FIRST.
- **Remediation:** Upgrade to NetScaler ADC/Gateway `14.1-73.32+` or `13.1-63.21+` (and applicable FIPS/NDcPP builds). Check for `add authentication samlAction`, AAA/VPN virtual-server configuration, and `add lsn group.*sipalg.*`.
- **ATT&CK:** `T1190` is an exposure mapping, not a claim of observed exploitation.

**Source:** [Citrix/BleepingComputer advisory report](https://www.bleepingcomputer.com/news/security/citrix-urges-admins-to-patch-new-netscaler-flaws-as-soon-as-possible/) · [NVD CVE-2026-19490](https://nvd.nist.gov/vuln/detail/CVE-2026-19490)

### 7. Elementor Pro `CVE-2026-32475`

- **Status:** **NEW — urgent patch/watch; no active exploitation reported in collected sources**.
- **Impact:** Unauthenticated duplicate multipart upload handling can bypass extension filtering and write a PHP file under `wp-content/uploads/elementor/forms/`.
- **NVD:** CVSS **9.0**, vector `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H`; no EPSS score was returned by FIRST on 2026-08-19.
- **Affected/fixed:** Elementor Pro through `4.2.1`; `4.2.2` released 2026-08-19.
- **Action:** Upgrade to `4.2.2+`, inspect Elementor form-upload directories for unexpected `.php` files, review web-server process creation and outbound connections, and audit WordPress admin/plugin changes.
- **ATT&CK:** `T1190`; `T1505.003` only if a PHP web shell is identified.

**Source:** [The Hacker News/Patchstack report](https://thehackernews.com/2026/08/elementor-pro-flaw-could-let.html) · [NVD CVE-2026-32475](https://nvd.nist.gov/vuln/detail/CVE-2026-32475)

## Deterministic IoC and artifact extraction

Extraction was run against normalized article text for the selected findings. Defanging handled `hxxp`/`hxxps`, `[.]`, `(.)`, and `[:]`; private, localhost, and non-routable IPs were excluded.

```json
{
  "ipv4": ["139.180.197.150"],
  "ipv6": [],
  "md5": [],
  "sha256": [],
  "domains": [
    "adminapi.tippusoni.in",
    "webhook.site"
  ],
  "urls": [
    "https://adminapi.tippusoni.in/4/dll.zip",
    "https://adminapi.tippusoni.in/4/user.txt"
  ],
  "cves": [
    "CVE-2026-19489", "CVE-2026-19490", "CVE-2026-25895",
    "CVE-2026-25939", "CVE-2026-32475", "CVE-2026-60112",
    "CVE-2026-64849", "CVE-2026-73570", "CVE-2023-33831",
    "CVE-2019-16098", "CVE-2021-21551"
  ],
  "ghsas": ["GHSA-p9r8-2q67-fp86"],
  "registry_keys_and_paths": [
    "HKLM\\SAM\\SAM", "HKLM\\SYSTEM", "HKLM\\SECURITY",
    "C:\\Windows\\System32\\drivers\\etc\\hosts:cache",
    "acpi_pad.ko", "hardware-monitor.service"
  ],
  "high_signal_artifacts": [
    "SPECTRE", "Specter", "RTCore64.sys", "DBUtil_2_3.sys",
    "X-ID", "/api/v1/register", "/api/v1/output",
    "C:\\ProgramData\\dll.zip", "C:\\ProgramData\\user.bat",
    "/opt/zimbra/jetty/webapps/", "/opt/zimbra/jetty_base/webapps/",
    "/api/2.0/mlflow/webhooks/*/test", "wp-content/uploads/elementor/forms/*.php"
  ]
}
```

`CVE-2026-73570` and `CVE-2026-25939` are listed once in the normalized machine-readable output; the prose above preserves their contextual relationships. The domains and URL paths are reported as observed in Talos material; `webhook.site` is a shared service and should not be blocked globally without token/path context.

### Enrichment availability

- **CISA KEV:** Queried successfully. `CVE-2026-64849` is present with due date `2026-09-02`; the other current candidates above were not present in catalog version `2026.08.19`.
- **NVD:** Queried successfully for CVSS/vector/description data.
- **FIRST EPSS:** Queried successfully. Scores are included where returned; NetScaler and Elementor records had no EPSS record in the 2026-08-19 response.
- **AbuseIPDB:** Not queried for a reputation claim because no API credential was assumed; the one IP is a Talos-observed campaign indicator, not an AbuseIPDB score.
- **VirusTotal/OTX:** No credentials were assumed. No engine detections, OTX pulses, or attribution scores are claimed.

## Detection rule synthesis

### Sigma 1 — UAT-10147 Windows download and defense-evasion chain

```yaml
title: UAT-10147 IIS Post-Compromise Download and Defender Exclusion Activity
id: 0d0b5df9-7a2c-4f6e-b4cb-2ee0a8d3e2b1
status: experimental
description: Detects command execution patterns reported by Cisco Talos for UAT-10147, including certutil retrieval from the observed download host and Defender exclusion changes around IIS directories.
author: Hermes Autonomous CTI Agent
references:
  - https://blog.talosintelligence.com/uat-10147-chinese-speaking-adversary-integrates-agentic-ai-into-post-compromise-operations/
tags:
  - attack.execution
  - attack.t1059.003
  - attack.ingress-tool-transfer
  - attack.t1105
  - attack.defense-evasion
  - attack.t1562.001
logsource:
  category: process_creation
  product: windows
detection:
  selection_download:
    Image|endswith:
      - '\\certutil.exe'
    CommandLine|contains:
      - 'adminapi.tippusoni.in'
      - 'dll.zip'
      - 'user.txt'
  selection_exclusion:
    Image|endswith:
      - '\\powershell.exe'
      - '\\cmd.exe'
    CommandLine|contains:
      - 'Windows Defender\\Exclusions'
      - 'inetsrv'
  condition: selection_download or selection_exclusion
falsepositives:
  - Authorized IIS administration and malware-analysis labs
level: high
```

**Splunk SPL:**

```splunk
index=* (EventCode=4688 OR source="XmlWinEventLog:Microsoft-Windows-Sysmon/Operational")
(Image="*\\certutil.exe" AND (CommandLine="*adminapi.tippusoni.in*" OR CommandLine="*dll.zip*" OR CommandLine="*user.txt*"))
OR ((Image="*\\powershell.exe" OR Image="*\\cmd.exe") AND CommandLine="*Windows Defender\\Exclusions*" AND CommandLine="*inetsrv*")
| stats count min(_time) as first_seen max(_time) as last_seen values(Computer) as hosts values(User) as users values(CommandLine) as command_lines by Image
| sort - last_seen
```

**Elastic KQL:**

```kql
event.category: process and ((process.name: "certutil.exe" and (process.command_line: "*adminapi.tippusoni.in*" or process.command_line: "*dll.zip*" or process.command_line: "*user.txt*")) or ((process.name: "powershell.exe" or process.name: "cmd.exe") and process.command_line: "*Windows Defender\\Exclusions*" and process.command_line: "*inetsrv*"))
```

### Sigma 2 — SPECTRE/Specter persistence and BYOVD artifacts

```yaml
title: SPECTRE Cross-Platform Rootkit and BYOVD Artifact Activity
id: 6a0e9fc4-174c-42a1-9a4c-4d22a813f6f3
status: experimental
description: Detects high-signal file and service artifacts reported by Cisco Talos for UAT-10147 SPECTRE/Specter. Tune paths to approved software inventories.
author: Hermes Autonomous CTI Agent
references:
  - https://blog.talosintelligence.com/uat-10147-deploys-spectre-a-cross-platform-implant-with-linux-rootkit-and-byovd-capabilities/
tags:
  - attack.persistence
  - attack.t1547.006
  - attack.defense-evasion
  - attack.t1014
  - attack.t1562.001
logsource:
  category: file_event
  product: linux
detection:
  selection:
    TargetFilename|endswith:
      - '/acpi_pad.ko'
      - '/hardware-monitor.service'
  condition: selection
falsepositives:
  - Approved kernel modules and hardware-monitor services; validate package provenance
level: critical
```

**Splunk SPL:**

```spl
index=* (sourcetype=linux:audit OR sourcetype=linux:syslog OR source="auditd")
(TargetFilename="*/acpi_pad.ko" OR TargetFilename="*/hardware-monitor.service" OR file_path="*/acpi_pad.ko" OR file_path="*/hardware-monitor.service")
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(user) as users values(process) as processes by TargetFilename, file_path
| sort - last_seen
```

**Elastic KQL:**

```kql
host.os.type: linux and (file.name: "acpi_pad.ko" or file.name: "hardware-monitor.service")
```

### Sigma 3 — Zimbra suspicious child process and artifact activity

```yaml
title: Zimbra Suspicious Command Execution After CVE-2026-73570 Exploitation
id: 89dfd8f5-4e52-4c90-a6f0-7a2b8bc8a1ce
status: experimental
description: Detects shell or downloader processes launched in a Zimbra service context. Correlate with SMTP/SNMP requests and creation of files in Zimbra web roots or /tmp.
author: Hermes Autonomous CTI Agent
references:
  - https://nvd.nist.gov/vuln/detail/CVE-2026-73570
  - https://www.bleepingcomputer.com/news/security/critical-zimbra-rce-flaw-now-actively-exploited-in-attacks/
tags:
  - attack.initial-access
  - attack.t1190
  - attack.execution
  - attack.t1059.004
logsource:
  category: process_creation
  product: linux
detection:
  selection_parent:
    ParentImage|contains:
      - '/zimbra/'
      - 'zimbra'
  selection_child:
    Image|endswith:
      - '/sh'
      - '/bash'
      - '/curl'
      - '/wget'
      - '/python'
      - '/perl'
  condition: selection_parent and selection_child
falsepositives:
  - Approved Zimbra maintenance and diagnostics; require change-ticket correlation
level: high
```

**Splunk SPL:**

```spl
index=* (sourcetype=linux:audit OR sourcetype=process_creation)
(parent_process_name="*zimbra*" OR ParentImage="*/zimbra/*" OR user="zimbra")
(process_name IN ("sh","bash","curl","wget","python","perl") OR Image IN ("*/sh","*/bash","*/curl","*/wget","*/python","*/perl"))
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(command_line) as command_lines by user, process_name, ParentImage
| sort - last_seen
```

**Elastic KQL:**

```kql
host.os.type: linux and (user.name: "zimbra" or process.parent.name: "zimbra") and process.name: ("sh" or "bash" or "curl" or "wget" or "python" or "perl")
```

### Sigma 4 — FUXA and MLflow exposed endpoint hunting

```yaml
title: Exposed MLflow or FUXA High-Risk Endpoint Activity
id: 2f16dbbb-0f84-4fae-9bc8-0d4b65af91f7
status: experimental
description: Detects endpoint requests associated with actively scanned or exploited MLflow and FUXA vulnerabilities. Correlate with response status, redirects, file writes, and cloud metadata egress.
author: Hermes Autonomous CTI Agent
references:
  - https://nvd.nist.gov/vuln/detail/CVE-2026-64849
  - https://nvd.nist.gov/vuln/detail/CVE-2026-25895
  - https://thehackernews.com/2026/08/attackers-exploit-mlflow-ssrf-flaw-to.html
tags:
  - attack.initial-access
  - attack.t1190
  - attack.credential-access
  - attack.t1552.005
logsource:
  category: webserver
  product: generic
detection:
  selection_mlflow:
    cs-method: POST
    cs-uri-stem|contains: '/api/2.0/mlflow/webhooks/'
    cs-uri-stem|endswith: '/test'
  selection_fuxa:
    cs-method: POST
    cs-uri-stem|contains:
      - '/api/runscript'
      - '../'
      - '..%2f'
  condition: selection_mlflow or selection_fuxa
falsepositives:
  - Authorized MLflow webhook tests or FUXA engineering operations
level: high
```

**Splunk SPL:**

```spl
index=* (uri_path="*/api/2.0/mlflow/webhooks/*/test" OR uri_path="*/api/runscript*" OR uri_path="*../*" OR uri_path="*..%2f*")
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(http_status) as statuses values(user_agent) as user_agents by host, uri_path, http_method
| sort - last_seen
```

**Elastic KQL:**

```kql
(event.dataset: web or event.category: web) and http.request.method: POST and (url.path: "/api/2.0/mlflow/webhooks/*/test" or url.path: "/api/runscript*" or url.path: "*../*" or url.path: "*..%2f*")
```

### Additional hunt queries

```splunk
index=* (uri_path="*/cmd" OR uri_path="*/script/run" OR uri_path="*/seq") (http_method=POST OR method=POST)
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(status) as statuses by host, uri_path
| sort - last_seen
```

```kql
(event.dataset: web or event.category: web) and http.request.method: POST and url.path: ("/cmd" or "/script/run" or "/seq")
```

```splunk
index=* (uri_path="*/wp-content/uploads/elementor/forms/*.php" OR file_path="*wp-content/uploads/elementor/forms/*.php")
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(process) as processes by host, uri_path, file_path
| sort - last_seen
```

## YARA disposition and rules

The corpus contains file artifacts and high-signal strings, so triage rules are provided. They are **not** a substitute for sample-based validation and should not be used as sole blocking signatures.

```yara
rule Hermes_UAT10147_SPECTRE_Windows {
    meta:
        description = "Triage rule for Windows SPECTRE/BYOVD artifacts reported by Cisco Talos"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://blog.talosintelligence.com/uat-10147-deploys-spectre-a-cross-platform-implant-with-linux-rootkit-and-byovd-capabilities/"
        date = "2026-08-20"
        confidence = "medium; validate against samples"
    strings:
        $pe = { 4D 5A }
        $s_spectre = "SPECTRE" ascii wide nocase
        $s_rtcore = "RTCore64.sys" ascii wide nocase
        $s_dbutil = "DBUtil_2_3.sys" ascii wide nocase
        $s_ads = "hosts:cache" ascii wide nocase
        $s_api = "/api/v1/register" ascii wide
    condition:
        $pe at 0 and 2 of ($s_*)
}

rule Hermes_UAT10147_Specter_Linux {
    meta:
        description = "Triage rule for Specter Linux rootkit persistence artifacts reported by Cisco Talos"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://blog.talosintelligence.com/uat-10147-deploys-spectre-a-cross-platform-implant-with-linux-rootkit-and-byovd-capabilities/"
        date = "2026-08-20"
        confidence = "medium; validate against samples"
    strings:
        $elf = { 7F 45 4C 46 }
        $l_specter = "Specter" ascii wide nocase
        $l_ko = "acpi_pad.ko" ascii wide nocase
        $l_service = "hardware-monitor.service" ascii wide nocase
        $l_rootkit = "rootkit_persist" ascii wide nocase
    condition:
        $elf at 0 and 2 of ($l_*)
}
```

No hash-based block is justified: deterministic extraction produced **zero MD5/SHA256 hashes**.

## Four-step cyber investigation playbook

### 1. Scope & target identification

- Inventory Internet-facing IIS/Linux servers, Zimbra servers, FUXA/SCADA HMIs, MLflow tracking servers, AIT-GUI deployments, NetScaler ADC/Gateway appliances, and Elementor Pro WordPress sites.
- Identify version/build, network exposure, authentication boundary, remote-management paths, service accounts, and connected OT/mission systems.
- For UAT-10147, scope hosts with IIS modules, unusual Defender exclusions, vulnerable drivers, kernel modules, systemd units, and outbound connections to `139.180.197.150` or `adminapi.tippusoni.in`.
- For CISA KEV MLflow, track public exposure and the 2026-09-02 federal remediation deadline; do not treat EPSS as a substitute for exploitation evidence.

### 2. SIEM/EDR hunting methodology

- Deploy the Sigma/SPL/KQL rules above and correlate source IP, host, user, parent/child process, HTTP status, request body/path, file creation, and first/last-seen timestamps.
- Hunt UAT-10147 command lines (`certutil`, `EfsPotato`, Defender exclusions), IIS module/web-shell changes, `RTCore64.sys`/`DBUtil_2_3.sys`, process injection, SAM hive saves, browser credential-store reads, `acpi_pad.ko`, `hardware-monitor.service`, and SPECTRE HTTP POST paths.
- Hunt Zimbra restarts, `zimbra`-owned files in the reported directories, SMTP/SNMP anomalies, and child shells/downloaders.
- Hunt FUXA path traversal, `/api/runscript`, arbitrary `main.js` writes, scheduler modifications, and HMI process creation. Hunt MLflow webhook-test redirects and egress to metadata services.
- Hunt AIT-GUI `/cmd`, `/script/run`, and `/seq` POSTs; inspect command-bus logs and operator browser telemetry. Hunt Elementor PHP file creation in form-upload paths.

### 3. Triage & containment

- Isolate suspected servers while preserving volatile and application evidence; coordinate with plant/mission owners before disrupting OT or spacecraft command infrastructure.
- Patch/upgrade: Zimbra `10.1.20+`; FUXA `1.2.10+` and `1.2.11+` for the respective issues; MLflow `3.15.0+`; NetScaler recommended builds; Elementor Pro `4.2.2+`. For AIT-GUI, validate the actual patched source/build because public records conflict.
- Remove direct Internet exposure from FUXA, MLflow, AIT-GUI, Zimbra administration, and OT/mission interfaces; restrict egress and block cloud metadata access from MLflow.
- If UAT-10147 is suspected, disable unauthorized IIS modules/services, quarantine vulnerable-driver artifacts, rotate LDAP/cloud/browser/application credentials, and preserve kernel/EDR telemetry before reboot.

### 4. Forensic validation

- Preserve firewall, reverse-proxy, SMTP/SNMP, web, cloud, EDR, Windows event, Linux audit, NetScaler, WordPress, OT/HMI, AIT-GUI, and command-bus logs with synchronized timestamps.
- Confirm exploitation versus scanning by correlating request paths, successful responses, process lineage, file writes, service/kernel changes, credential use, cloud metadata responses, and post-exploitation access.
- Hash and preserve suspicious IIS modules, JSP/PHP files, FUXA/MLflow artifacts, drivers, kernel modules, systemd units, and scripts for offline analysis. Do not infer hashes from filenames.
- Validate remediation with external exposure rescans, version/build verification, clean configuration comparisons, credential-use review, command-bus/PLC integrity checks, and owner-approved return-to-service decisions.

## Source register

| Source | Publication/collection | Use |
|---|---|---|
| CISA KEV JSON | Catalog `2026.08.19`, collected 2026-08-20 | KEV state and due date for MLflow |
| CISA Cybersecurity Advisories RSS | Collected 2026-08-20 | Advisory stream and feed health |
| Cisco Talos | 2026-08-20 10:00 UTC | UAT-10147, SPECTRE, rootkit/BYOVD, AI-assisted operations |
| BleepingComputer / CERT Polska | 2026-08-20 | Zimbra active exploitation; Citrix NetScaler patch advisory |
| The Hacker News / Cycode | 2026-08-20 | AIT-GUI command-bus exposure; Elementor; MLflow/FUXA reporting |
| NVD CVE API | Collected 2026-08-20 | CVSS, vectors, descriptions, publication data |
| FIRST EPSS API | 2026-08-20 | EPSS snapshots dated 2026-08-19 |
| Source registry | `code/threat-intel-agent/config/sources.json` | Authoritative ingestion configuration |

**Analytic caveats:** Attribution is reported as Talos assessment where stated, not independently established here. The `139.180.197.150` and `adminapi.tippusoni.in` indicators are observed in Talos reporting; current ownership/reputation was not independently enriched because no reputation API credentials were available. No YARA rule should be promoted without sample validation. 
