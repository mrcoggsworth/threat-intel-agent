# Hermes Daily CTI Briefing & Playbook Synthesis — 2026-08-24

**Collection time:** `2026-08-24T13:02:13Z`  
**Window:** `2026-08-23T13:02:13Z`–`2026-08-24T13:02:13Z`  
**Deduplication context:** prior 48 hours, `.hermes/memories/MEMORY.md`, and recent CTI sessions  
**Assessment:** **HIGH — 2 net-new qualifying items; 1 critical carry-forward update**  
**Scope:** Enterprise identity infrastructure, government/IT targets, Windows endpoints, and Internet-facing services.

## BLUF

1. **NEW — Keycloak `CVE-2026-18963`: critical unauthenticated account takeover.** Red Hat describes improper state validation in the reset-credentials flow; an attacker can bypass the emailed action token and set a new password for any account, including administrative accounts.[2][3]

   Red Hat rates it **CVSS 9.1 Critical** with vector `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`.[3][4]

   Upgrade upstream Keycloak to **26.7.2** or apply the applicable RHBK fixes; if immediate upgrade is impossible, disable “Forgot password” across every realm.[2][3]
2. **NEWLY SURFACED — Operation QUICSILVER / QUICAgent.** Seqrite reports a China-nexus campaign, with moderate confidence, targeting Myanmar government personnel through VHD/JPEG lures, malicious LNK execution via `ftp.exe`, split-payload reconstruction, and a Go backdoor with QUIC/HTTP3 C2, RC4-encrypted traffic, command execution, file transfer, and Startup-folder persistence.[1]
3. **UPDATE — Zimbra `CVE-2026-73570` remains an active-exploitation emergency.** CISA’s KEV record carries a remediation due date of **2026-08-24**; BleepingComputer reports CISA’s three-day patching order for U.S. government agencies.[6][7] This is not a new finding today and is retained as a deadline/status update only.

## Deduplication and validation

- The prior 2026-08-23 briefing reported no new qualifying enterprise threats. Previously reported TrueConf, GitLab, Rust crates.io/RedC2, SynkLoader, BTR.sys, AWS-key exposure, Entra ID, Zimbra, and UAT-10147/SPECTRE items were suppressed as duplicates or carry-forward context.[1][6]
- The 24-hour registered-feed collection produced 11 time-window entries. CISA KEV and CISA advisories returned successfully with no new catalog/advisory entry in the window; DFIR, Talos, Unit 42, Microsoft Threat Intelligence, SentinelLabs, Red Canary, Krebs, and BleepingComputer were reachable. Google TAG returned HTTP 404, ZDI returned HTTP 502, and MSRC returned HTTP 200 with malformed XML. SANS ISC returned parseable entries in this run; the supplemental Hacker News feed supplied the Keycloak and QUICSILVER notices.[2][6][8]
- **Excluded:** ToxicPanda Android malware (consumer/mobile focus; enterprise relevance not established), DOUBLECUP’s SANS note (useful Windows-loader technique but no enterprise targeting or campaign telemetry sufficient for a priority item), WPF printing/PDF-export and gaming breakage (availability/compatibility issues), and UAT-10147/SPECTRE (duplicate re-publication).[8]
- Source precedence: Red Hat/NVD/FIRST/CISA supplied vulnerability and scoring data.[2][3][4]
- Seqrite supplied QUICSILVER technical details and the attribution assessment.[1]
- BleepingComputer supplied the CISA/Zimbra operational update.[6][7]
- SANS supplied the DOUBLECUP exclusion context.[8]

## Priority findings

### 1. Keycloak `CVE-2026-18963` — unauthenticated account takeover

| Field | Assessment |
|---|---|
| Status | **NEW — critical patch item; exploitation not established** |
| First observed in current feed window | 2026-08-24, supplemental THN notice |
| Affected technology | Keycloak identity and access management; Red Hat build of Keycloak (RHBK) product records require deployment-specific validation |
| Impact | Improper reset-credentials state validation lets an unauthenticated attacker bypass the emailed action token and directly set a victim’s password; administrative accounts are included in the reported impact.[2][3][4] |
| CVSS | 9.1 Critical; `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N`.[3][4] |
| EPSS | `0.003910000` (0.391%); percentile `0.324170000` (32.417%); FIRST snapshot date `2026-08-23`.[5] |
| KEV | Not present in the current CISA KEV catalog query; this does **not** imply safety or absence of exploitation outside the catalog.[6] |
| Exploitation status | THN reports no evidence of exploitation and no verified public exploit as of 2026-08-24.[2] |
| Fixed versions | Upstream Keycloak `26.7.2`; RHBK 26.4 operator bundle `26.4.15-1` / images `26.4-23`; RHBK 26.6 operator bundle `26.6.6-1` / containers `26.6-12`.[2] |
| Temporary mitigation | Disable `Realm settings → Login → Forgot password` for all realms until fixed versions are deployed.[3] |
| ATT&CK | `T1190` (Exploit Public-Facing Application); `T1078` is conditional and should be applied only when post-reset use of the account is confirmed. |

**Priority actions:** inventory Keycloak/RHBK versions and Internet exposure; upgrade; disable the forgot-password flow where patching is delayed; review reset-credential requests, password changes, source IPs, user-agent anomalies, and privileged-account activity. Treat successful password resets without the expected email-token sequence as a high-confidence incident lead.[2][3]

### 2. Operation QUICSILVER / QUICAgent

| Field | Assessment |
|---|---|
| Status | **NEWLY SURFACED — active espionage campaign; original Seqrite disclosure dated 2026-08-17** |
| Victimology | Myanmar government personnel/diplomatic and IT/cybersecurity-related targets; government-themed Burmese-language graduation/official-document lures.[1] |
| Attribution | Seqrite assesses **China-nexus with moderate confidence**; this is a vendor assessment, not an independently established attribution.[1] |
| Initial access | VHD file disguised as JPEG; malicious `TrainingAnnouncement.pdf.lnk` masquerading as a PDF; user execution.[1] |
| Execution | LNK launches signed `ftp.exe` with `-s:` to execute a local script; `copy /b` reconstructs a payload from `header.doc` and `body.doc` into `%LOCALAPPDATA%\\Windowsupdate.exe`.[1] |
| Payload | Custom 64-bit Go 1.20 backdoor `QUICAgent`; sandbox delay and 1,000 SHA-256 iterations; system-information and username collection; five operator commands: `shell`, `set_heartbeat`, `upload`, `download`, `list_dir`.[1] |
| C2 | Cloudflare Workers dead-drop resolution; final hostname `register[.]mediumser[.]com`; QUIC/HTTP3 over UDP/443; RC4-encrypted JSON beacons every five seconds.[1] |
| Persistence | PowerShell-generated `SystemIn.lnk` in the current user’s Startup folder, pointing to `Windowsupdate.exe`.[1] |
| ATT&CK | `T1566.001`, `T1204.002`, `T1059.001`, `T1218`, `T1027.009`, `T1036.008`, `T1070.004`, `T1547.001`, `T1082`, `T1083`, `T1102.001`, `T1041`.[1] |

**Priority actions:** hunt for LNK files launched through `ftp.exe`, `ftp.exe -s:` command lines, `copy /b` reconstruction, `Windowsupdate.exe`, `create_lnk_*.ps1`, `SystemIn.lnk`, and QUIC/UDP-443 connections to the observed infrastructure. Preserve VHDs and endpoint telemetry before deletion; block or sinkhole only after ownership and business-use validation because Cloudflare/Akamai infrastructure can be shared.[1]

### 3. Zimbra `CVE-2026-73570` — KEV deadline/status update

- **Status:** **UPDATE, not new.** CISA’s catalog identifies Zimbra Collaboration Suite OS command injection and sets `dueDate` to `2026-08-24`; BleepingComputer reports CISA ordered U.S. government agencies to patch within three days.[6][7]
- **Action:** verify `10.1.20+` deployment, Internet exposure, optional `zimbra-snmp`/SNMP-notification configuration, and post-exploitation telemetry. Retain the prior report’s Zimbra Sigma/SPL/KQL package.[6][7]

## Deterministic IoC extraction

Extraction ran against normalized, refanged Seqrite and Keycloak evidence with deduplication and routable-IP filtering. The machine-readable output is [`iocs_20260824.json`](iocs_20260824.json).[1][2]

```json
{
  "ipv4": ["104.64.211.22", "38.60.244.141"],
  "ipv6": [],
  "md5": [],
  "sha256_count": 8,
  "domains": [
    "appupdate.0cmds20cj2cdf8.workers.dev",
    "maui-cocktailbar.com",
    "mediumser.com",
    "register.mediumser.com",
    "regupdate.eamakfu49dc28wa.workers.dev"
  ],
  "urls": [
    "https://appupdate.0cmds20cj2cdf8.workers.dev/A3cmf0q9ASCion",
    "https://regupdate.eamakfu49dc28wa.workers.dev/vere0zme82cadre"
  ],
  "cves": ["CVE-2026-18963"],
  "registry_keys": []
}
```

The eight SHA-256 values and observed file/artifact names are preserved in the JSON output; do not infer a hash-to-file mapping beyond the explicit Seqrite table. The two IPs are source-observed infrastructure indicators, not proof of current C2 activity.[1]

## Enrichment and risk scoring

| Observable | Result | Disposition |
|---|---|---|
| `CVE-2026-18963` | NVD/Red Hat: CVSS 9.1 Critical; FIRST EPSS 0.00391, 32.417th percentile.[3][4][5] | **HIGH** due to unauthenticated total-impact account takeover despite low EPSS and no reported exploitation. |
| CISA KEV | `CVE-2026-18963` absent from current catalog query; `CVE-2026-73570` remains listed with due date 2026-08-24.[6] | Keycloak is patch/watch; Zimbra is deadline-critical. |
| `104.64.211.22` | OTX public lookup: reputation `0`, three pulse associations; ASN shown as Akamai. Pulse associations include QUICSILVER-related names.[9] | **Observed campaign IOC;** OTX reputation `0` is not a benign verdict and shared hosting requires validation. |
| `38.60.244.141` | OTX public lookup: reputation `0`, six pulse associations; ASN shown as Cogent. Pulse associations include QUICSILVER-related names.[10] | **Historical campaign IOC;** use for retrospective DNS/proxy/hunt enrichment. |
| AbuseIPDB / VirusTotal | Requests returned HTTP 401 without configured credentials. | No AbuseIPDB confidence, VT detections, or reputation claims are made. |
| Attribution | Seqrite’s China-nexus assessment is moderate confidence.[1] | Reported assessment only; no independent attribution claim. |

## Detection rule synthesis

Validated artifacts:

- [`sigma_quicsilver.yml`](sigma_quicsilver.yml) — YAML parsed successfully; Sigma CLI was not available in the runtime, so full backend compilation was not claimed.[1]
- [`sigma_keycloak.yml`](sigma_keycloak.yml) — YAML parsed successfully; same Sigma CLI limitation.[2][3]
- [`yara_quicsilver.yar`](yara_quicsilver.yar) — compiled successfully with `yara-python` (`yara-syntax-ok`). It is **triage-only** and sample validation is still required.[1]

### Splunk SPL — QUICSILVER process chain

```spl
index=* (EventCode=4688 OR sourcetype=XmlWinEventLog:Microsoft-Windows-Sysmon/Operational)
((Image="*\\ftp.exe" AND CommandLine="*-s:*")
 OR (Image IN ("*\\cmd.exe","*\\copy.exe") AND (CommandLine="*copy /b*" OR CommandLine="*header.doc*" OR CommandLine="*body.doc*" OR CommandLine="*Windowsupdate.exe*"))
 OR ((Image="*\\powershell.exe" OR Image="*\\pwsh.exe") AND (CommandLine="*create_lnk_*" OR CommandLine="*SystemIn.lnk*" OR CommandLine="*\\Startup\\*")))
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(user) as users values(CommandLine) as command_lines by Image
| sort - last_seen
```

### Elastic KQL — QUICSILVER process chain

```kql
event.category: process and ((process.name: "ftp.exe" and process.command_line: "*-s:*") or ((process.name: "cmd.exe" or process.name: "copy.exe") and (process.command_line: "*copy /b*" or process.command_line: "*header.doc*" or process.command_line: "*body.doc*" or process.command_line: "*Windowsupdate.exe*")) or ((process.name: "powershell.exe" or process.name: "pwsh.exe") and (process.command_line: "*create_lnk_*" or process.command_line: "*SystemIn.lnk*" or process.command_line: "*\\Startup\\*")))
```

### Splunk SPL — Keycloak reset flow

```splunk
index=* (uri_path="*reset-credentials*" OR url_path="*reset-credentials*") (http_method=POST OR method=POST)
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(http_status) as statuses values(user_agent) as user_agents values(user) as users by host, uri_path
| sort - last_seen
```

### Elastic KQL — Keycloak reset flow

```kql
(event.category: web or event.dataset: web) and http.request.method: POST and url.path: "*reset-credentials*"
```

### YARA disposition

The QUICAgent rule uses the PE header plus multiple source-observed strings (Workers endpoints, `register.mediumser.com`, `Windowsupdate.exe`, `SystemIn.lnk`, `RAT CA`, and the reported RC4 key). It is not a block signature and must be tested against known-good software and Seqrite samples before operational deployment.[1]

## Four-step cyber investigation playbook

### 1. Scope & target identification

- Inventory Keycloak upstream/RHBK deployments, version/build, realm configuration, Internet exposure, reverse proxies, identity-provider integrations, and privileged users.[2][3]
- Inventory Windows enterprise endpoints and servers that can receive VHD/JPEG/LNK attachments; prioritize government/IT business units and systems with outbound UDP/443.[1]
- Identify hosts with `ftp.exe` execution, Startup-folder modifications, VHD mounting, and `%LOCALAPPDATA%\\Windowsupdate.exe` creation.[1]
- Mark `104.64.211.22`, `38.60.244.141`, the two Workers URLs, and the listed domains as source-observed indicators requiring context-aware blocking/retrospective search.[1][9][10]

### 2. SIEM/EDR hunting methodology

- Deploy the two Sigma rules and queries above; correlate source IP, host, user, parent/child process, command line, file creation, signer, first/last seen, and HTTP response status.[1][2]
- For Keycloak, hunt `reset-credentials` POSTs, password changes within minutes of the request, missing/abnormal email-token events, privileged-account changes, new sessions, and downstream access using the reset account.[2][3]
- For QUICSILVER, hunt LNK→`ftp.exe -s:`→script/`copy /b`→`Windowsupdate.exe`, `create_lnk_*.ps1`, `SystemIn.lnk`, VHD mount events, and QUIC/UDP-443 connections to the observed infrastructure.[1]
- Search for the eight SHA-256 hashes, then validate each match against the explicit file-name mapping in the source-derived IoC JSON; do not treat a filename alone as malware evidence.[1]

### 3. Triage & containment

- Keycloak: restrict administrative access, disable forgot-password across realms if patching cannot complete immediately, upgrade to fixed builds, invalidate suspicious sessions, reset affected privileged credentials through a trusted channel, and preserve identity-provider/proxy logs.[2][3]
- QUICSILVER: isolate suspected endpoints without destroying evidence; block exact domains/URLs/IPs where operationally safe; quarantine VHD/LNK/payload artifacts; disable unauthorized Startup entries; and rotate credentials if the implant executed.[1]
- Zimbra: complete the CISA deadline action today, verify `10.1.20+`, restrict public exposure, and preserve the host for forensic triage if exploitation indicators exist.[6][7]

### 4. Forensic validation

- Preserve synchronized reverse-proxy, Keycloak, identity-provider, Windows Security/Sysmon, EDR, DNS, firewall, QUIC/HTTP3, and email-delivery logs.[1][2][3]
- Confirm Keycloak exploitation by correlating reset-flow state transitions, password-change events, action-token absence, source infrastructure, and post-reset authentication—not by the presence of a reset request alone.[2][3][4]
- Confirm QUICSILVER execution by validating the LNK target, `ftp.exe` parent/child lineage, `copy /b` reconstruction, PE metadata, Startup persistence, beacon timing, and encrypted QUIC traffic.[1]
- Hash and preserve VHDs, LNKs, reconstructed binaries, scripts, and suspicious Startup files for offline analysis; validate remediation with version/build checks, external exposure scans, credential-use review, and clean-baseline comparison.[1][2][3]

## Source register

- Registered feed collection: `collection_20260824.json`.
- Deterministic IoC output: `iocs_20260824.json`.
- Primary QUICSILVER research: Seqrite.[1]
- Keycloak reporting and vendor advisory: The Hacker News and Red Hat.[2][3]
- CVSS/vector and vulnerability record: NVD.[4]
- EPSS snapshot: FIRST.[5]
- KEV and Zimbra deadline: CISA and BleepingComputer.[6][7]
- DOUBLECUP exclusion context: SANS ISC.[8]
- Supplemental OTX lookups: `104.64.211.22` and `38.60.244.141`.[9][10]

## Sources

[1] https://www.seqrite.com/blog/operation-quicsilver-china-nexus-actor-targets-myanmar-diplomats-via-vhd-delivered-go-backdoor/  
[2] https://thehackernews.com/2026/08/critical-keycloak-password-reset-flaw.html  
[3] https://access.redhat.com/security/cve/cve-2026-18963  
[4] https://nvd.nist.gov/vuln/detail/CVE-2026-18963  
[5] https://api.first.org/data/v1/epss?cve=CVE-2026-18963  
[6] https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json  
[7] https://www.bleepingcomputer.com/news/security/cisa-orders-urgent-patching-of-actively-exploited-zimbra-flaw/  
[8] https://isc.sans.edu/diary/rss/33274  
[9] https://otx.alienvault.com/api/v1/indicators/IPv4/104.64.211.22/general  
[10] https://otx.alienvault.com/api/v1/indicators/IPv4/38.60.244.141/general  
