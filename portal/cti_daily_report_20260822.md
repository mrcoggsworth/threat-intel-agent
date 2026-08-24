# Hermes Daily CTI Briefing & Playbook Synthesis — 2026-08-22

**Collection time:** `2026-08-22T13:01:07Z`  
**Window:** `2026-08-21T13:01:07Z`–`2026-08-22T13:01:07Z`  
**Deduplication context:** prior 48 hours plus `.hermes/memories/MEMORY.md` and recent session history  
**Assessment:** **CRITICAL**  
**Scope:** enterprise mail, cloud/IAM, software supply chain, developer infrastructure, Windows endpoint defense, and collaboration platforms.

## BLUF

1. **UPDATE — Zimbra `CVE-2026-73570` entered CISA KEV on 2026-08-21.** CISA sets a federal remediation deadline of **2026-08-24**. NVD describes unauthenticated OS command injection through SMTP/SNMP notification processing when the optional `zimbra-snmp` package is installed and SNMP notifications are enabled; NVD CVSS is **8.9**. Upgrade to **Zimbra 10.1.20 or the current vendor-supported fixed build**, restrict exposure, and perform compromise triage.
2. **NEW — 14 trojanized npm packages deliver the RedC2 4.0 Linux implant.** TrendAI observed import-time execution without an install hook; a transitive import is sufficient. RedShell supports shell access, credential collection, payload loading, persistence, tunneling, and exfiltration. A hardcoded C2 IP and 12 SHA-256 file hashes are available for immediate hunting.
3. **NEW — SynkLoader is being delivered through Microsoft Teams impersonation of corporate IT help desks.** Expel observed a fake Azure-hosted `PowerShell Cleaner` MSI, in-memory PowerShell/Python/C# execution, a fake Windows lock screen for password theft, scheduled-task persistence, and reverse-proxy tunneling into corporate networks. Expel recovered three C2 domains and 12 file/module hashes.
4. **NEW — Check Point disclosed weaponization of Microsoft Defender's signed BTR remediation driver.** The technique can perform arbitrary kernel-level file and registry operations and disable security tooling without a conventional memory-corruption exploit or external BYOVD. This is a high-confidence defensive-evasion watch item, not a confirmed exploitation campaign.
5. **NEW exposure intelligence — 768 live corporate AWS keys reportedly retain full account control.** Truffle Security re-verified 10,616 leaked keys; 88% still authenticated, including 526 root keys and 242 AdministratorAccess IAM keys linked to companies. No key material or customer-specific IoCs were published. Treat any matching internal credential as compromised.

## Deduplication and provenance

- Memory and session history were checked for CVEs, zero-days, APT/campaign names, and supply-chain incidents. Previously reported TrueConf `CVE-2026-72529/-72530`, GitLab `CVE-2026-19478`, Rust crates.io compromise, Entra `CVE-2026-69836`, `GHSA-864f-rcv7-6rh4`, Cisco Crosswork/Secure Workload, Zimbra exploitation, and prior Microsoft/SharePoint/Lazarus items were not reissued as new findings.
- Zimbra is explicitly labeled **UPDATE**, not new: prior reporting covered exploitation; CISA KEV status and the 2026-08-24 deadline are the material state change.
- Unit 42's 2026-08-21 SDLC/ChainDrop article is treated as context, not a new ChainDrop event; ChainDrop was previously disclosed outside this collection window.
- Source precedence: CISA/NVD/FIRST for vulnerability status and scoring; TrendAI, Expel, Check Point Research, and Truffle Security for original research; BleepingComputer and The Hacker News for corroboration.

## Priority findings

### 1. Zimbra `CVE-2026-73570` — **CRITICAL / UPDATE / CISA KEV**

| Field | Detail |
|---|---|
| Affected product | Zimbra Collaboration Suite before `10.1.20`, specifically the optional `zimbra-snmp` path with SNMP notifications enabled |
| Impact | Unauthenticated attacker can submit crafted SMTP input that reaches OS command execution as the `zimbra` user |
| NVD | CVSS `8.9`; `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:L`; CWE-78 |
| EPSS | `0.005390000` / `0.431830000` percentile, FIRST snapshot `2026-08-21` |
| KEV | Added `2026-08-21`; CISA due date `2026-08-24`; ransomware use `Unknown` |
| Action | Patch to `10.1.20` or current fixed vendor build; remove unnecessary Internet exposure; if exposed while unpatched, preserve mail/proxy/process evidence and review for command execution and new persistence |

**Detection posture:** ATT&CK `T1190` is supported for exposed self-hosted Zimbra. Do not treat a generic SMTP connection as exploitation; correlate with shell/process creation under the `zimbra` account, abnormal SNMP notification activity, and post-exploitation file or service changes.

**Sources:** [CISA KEV alert](https://www.cisa.gov/news-events/alerts/2026/08/21/cisa-adds-one-known-exploited-vulnerability-catalog) · [CISA KEV JSON](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) · [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-73570) · [Zimbra security advisories](https://wiki.zimbra.com/wiki/Zimbra_Security_Advisories) · [BleepingComputer exploitation report](https://www.bleepingcomputer.com/news/security/critical-zimbra-rce-flaw-now-actively-exploited-in-attacks/)

### 2. RedC2 4.0 via trojanized npm packages — **CRITICAL / NEW**

- **Evidence:** TrendAI analyzed 14 functional-looking date/calendar npm packages. Each bundles a Linux ELF payload; `dist/index.mjs` launches it at module import time, with no preinstall/postinstall hook and no exported function call required.
- **Package scope:** `streak-metrics-math@1.0.0/1.0.1`, `kit-map-vim@1.0.0`, `streak-map-cache@1.0.0`, `streak-map-kit@1.0.0`, `map-streak-kit@1.0.0`, `streak-cache-map@1.0.0`, `streak-calc-metrics@1.0.0`, `streak-calc-math@1.0.0`, `streak-math-abz@1.0.0`, `streak-metricsaz@1.0.0`, `streak-math-metrics@1.0.0`, `streak-metricazbd@1.0.0`, `streak-metricsazb@1.0.0`, `streak-kit-map@1.0.0`.
- **Capabilities:** RedShell Linux supports `/bin/sh` command execution, system/network discovery, SSH/browser/database credential collection, file transfer, bulk exfiltration, SOCKS5/TCP forwarding, in-memory execution, and persistence through cron, `~/.bashrc`, user systemd services, or XDG autostart. TrendAI describes Red Agent, an LLM-backed command layer exposed through `/ra`.
- **Infrastructure:** `217.60.77.63:8792`; C2 domains `neversoftmain[.]net`, `rootfarmapp[.]net`, and `tripinupdate[.]net`; `litterbox.catbox.moe` is cited for external file transfer. Block only after local validation/change control.
- **Action:** Search every `package-lock.json`, `npm-shrinkwrap.json`, SBOM, npm cache, CI runner, and developer workstation for the package names and suspicious `dist/*.bin`/`.dat` files. Preserve package caches and endpoint telemetry before cleanup. Review Node child processes, chmod of bundled binaries, outbound TLS/HTTP to the listed infrastructure, browser/SSH credential access, and cron/systemd/XDG persistence. Rotate secrets for any host that imported or executed an affected package.

**Sources:** [TrendAI primary research](https://www.trendaisecurity.com/en-us/resources-insights/trendai-security-blog/redc2-ai-powered-linux-implant) · [The Hacker News corroboration](https://thehackernews.com/2026/08/14-trojanized-npm-packages-drop-redc2.html)

### 3. SynkLoader Teams phishing — **HIGH / NEW**

- **Initial access:** attacker impersonates corporate IT support through Microsoft Teams and directs the user to an Azure Blob-hosted MSI named `331.msi` / `PowershellCleaner`.
- **Execution chain:** MSI extracts `cleaner.ps1`, `archive6.zip`, a Python runtime, malicious Python/C# components, and fake Microsoft runtime DLLs. PowerShell is executed in memory using obfuscated and AES-CBC/Base64-wrapped content.
- **Capabilities:** system/AD profiling, scheduled-task persistence, fake lock-screen credential capture (`PhishLocker`), reverse-proxy/tunneling (`TrafficRedirector`), interactive PowerShell shell, and VNC-like desktop control (`StreamMaster`). Expel recovered hands-on-keyboard activity against a controlled fake environment.
- **C2:** `neversoftmain[.]net`, `rootfarmapp[.]net`, `tripinupdate[.]net`; requests use a victim-specific path and encrypted beaconing. The Azure delivery URL is in the IoC JSON.
- **Action:** Search Teams messages and M365 audit logs for fake IT-helpdesk lures; hunt `msiexec.exe → powershell.exe → pythonw.exe` lineage, `cleaner.ps1`, `archive6.zip`, random `%AppData%` directories, scheduled tasks at logon/10:00, and connections to the three domains. Reset credentials entered into the fake lock screen; revoke sessions/tokens and isolate affected endpoints.

**Attribution:** Expel reports the activity and assesses possible ransomware/initial-access-broker use; no named actor is established.

**Sources:** [Expel primary research](https://expel.com/blog/synkloader-when-you-throw-in-everything-but-the-kitchen-sink/) · [BleepingComputer](https://www.bleepingcomputer.com/news/security/new-synkloader-malware-pushed-in-microsoft-teams-phishing-campaign/)

### 4. Microsoft Defender BTR.sys weaponization — **HIGH / NEW WATCH**

- Check Point Research reverse-engineered Defender's Boot-Time Removal driver and demonstrated arbitrary kernel-level file/registry operations via crafted encrypted transactions.
- The driver is Microsoft-signed and normally embedded in `MpEngine.dll`; the research describes randomized driver/service names, an NTFS alternate data stream `:changelist`, transient service loading, and self-cleanup. The technique can disable EDR/AV without relying on a conventional exploit or an externally sourced vulnerable driver.
- **Status discipline:** no enterprise exploitation campaign or CVE is established by the source. Do not block every legitimate Defender remediation event solely because `BTR.sys` appears.
- **Action:** alert on Defender remediation driver activity outside expected Defender workflows, especially randomized `.sys` files under `System32\drivers`, new `HKLM\SYSTEM\CurrentControlSet\Services\*` entries with `Args`, `:changelist` ADS use, `SeLoadDriverPrivilege`, and security-tool deletion. Validate signer, parent process, Defender event correlation, reboot timing, and transaction provenance.

**Source:** [Check Point Research — BTR Reforged](https://research.checkpoint.com/2026/btr-reforged-weaponizing-defenders-remediation-driver-as-a-kernel-operation-primitive/)

### 5. Exposed corporate AWS keys — **HIGH / NEW EXPOSURE INTELLIGENCE**

- Truffle Security re-verified **10,616** leaked AWS key pairs on 2026-08-10; **88%** still authenticated.
- Of the live business-linked keys, **526 were root keys** and **242 were IAM users with AdministratorAccess**, totaling **768 keys with full control of a company AWS account**. The population included **130 organization-management-account root keys**.
- The research publishes aggregate data only: no key material, account identifiers, or customer-specific IoCs. This is exposure intelligence, not evidence that a particular enterprise was compromised.
- **Action:** inventory and revoke exposed/root keys; rotate all credentials found in public repositories, datasets, Docker images, package registries, and CI logs; inspect CloudTrail for `GetCallerIdentity`, IAM enumeration, role assumption, new users/policies, unusual regions, data access, and cryptomining. Delete root access keys and enforce maximum key age/budget alerts.

**ATT&CK:** `T1078` is applicable only when a leaked credential is confirmed used as a valid account. Do not assert account compromise from the aggregate study alone.

**Sources:** [Truffle Security primary research](https://trufflesecurity.com/blog/leaked-corporate-aws-keys-held-full-admin-rights) · [BleepingComputer report](https://www.bleepingcomputer.com/news/security/hundreds-of-leaked-aws-keys-give-full-control-over-corporate-accounts/)

## Deterministic IoC and artifact extraction

Extraction was run against the selected technical corpus using the `ioc-parser` patterns, defanging normalization, deduplication, and private/loopback filtering. Full machine-readable output: [`iocs_20260822.json`](iocs_20260822.json).

```json
{
  "ipv4": ["217.60.77.63"],
  "ipv6": [],
  "md5": [],
  "sha256_count": 12,
  "domains": [
    "api.ipify.org",
    "filereserve.blob.core.windows.net",
    "litterbox.catbox.moe",
    "neversoftmain.net",
    "rootfarmapp.net",
    "tripinupdate.net"
  ],
  "urls": ["https://filereserve.blob.core.windows.net/vgnghuyk/331/331.msi"],
  "cves": ["CVE-2026-73570"],
  "registry_keys": [
    "HKLM\\SYSTEM\\CurrentControlSet\\Services\\mzqnjtaq",
    "HKLM\\SYSTEM\\CurrentControlSet\\Services\\{Random}\\Args"
  ]
}
```

`8.8.8.8` was excluded from the routable IoC set because the RedC2 analysis identifies it as a local UDP route probe, not attacker infrastructure. The `api.ipify.org` and `litterbox.catbox.moe` entries are shared/legitimate services observed in malware behavior; do not globally block without path, process, and campaign context. The 12 SHA-256 values are source-published SynkLoader file/module hashes; map each to its labeled artifact in the primary Expel research before enforcement.

## Enrichment and risk scoring

| Finding | CISA KEV | CVSS | EPSS | Reputation APIs | Risk |
|---|---|---:|---:|---|---|
| Zimbra `CVE-2026-73570` | Yes; added 2026-08-21; due 2026-08-24 | 8.9 | 0.00539 / 43.183 percentile | AbuseIPDB/VT/OTX not queried; no credentials assumed | **CRITICAL** |
| RedC2 npm compromise | No CVE/KEV record | N/A | N/A | OTX public endpoint: 3 pulses for `217.60.77.63`; 2 each for `neversoftmain.net`/`rootfarmapp.net`; IP reputation field `0`; no independent verdict | **CRITICAL** |
| SynkLoader | No CVE/KEV record | N/A | N/A | OTX public endpoint queried for shared C2 domains; pulse counts are context only | **HIGH** |
| BTR.sys weaponization | No CVE asserted by source | N/A | N/A | Not queried | **HIGH WATCH** |
| Exposed AWS keys | No CVE/KEV record | N/A | N/A | No key material published; no customer-specific lookup possible | **HIGH** |

NVD, FIRST EPSS, and the CISA KEV JSON were queried directly. The public AlienVault OTX indicator endpoint was queried for the RedC2 IP and two C2 domains; results are recorded as pulse-count/context telemetry only, not as an independent maliciousness verdict. AbuseIPDB and VirusTotal were **not queried** because API credentials were not available. EPSS does not override direct exploitation evidence or KEV status.

## ATT&CK mapping

| Finding | Supported techniques |
|---|---|
| Zimbra | `T1190` Exploit Public-Facing Application; command execution mapping requires endpoint confirmation |
| RedC2 | `T1195.002` Compromise Software Supply Chain; `T1059.004` Unix Shell; `T1105` Ingress Tool Transfer; `T1555.003` Credentials from Web Browsers; `T1543.002` Systemd Service; `T1053.003` Cron |
| SynkLoader | `T1566.002` Spearphishing Link; `T1059.001` PowerShell; `T1059.006` Python; `T1053.005` Scheduled Task/Job; `T1056.002` GUI Input Capture; `T1572` Protocol Tunneling |
| BTR.sys | `T1562.001` Impair Defenses; `T1543.003` Windows Service; `T1564.004` NTFS File Attributes; `T1070.004` File Deletion |
| AWS keys | `T1078` Valid Accounts only after confirmed use; no compromise is inferred from aggregate exposure data |

## Detection rule synthesis

### Sigma 1 — Zimbra post-exploitation shell

```yaml
title: Zimbra Service Account Shell After Internet-Facing Mail Exploit
id: 3fdb4f64-27d5-4ac7-8b1e-b8f33c2f5f92
status: experimental
description: Detects shell or downloader execution under the zimbra account. Correlate with exposed SMTP/SNMP activity for CVE-2026-73570; this is not an SMTP exploit signature by itself.
author: Hermes Autonomous CTI Agent
references:
  - https://www.cisa.gov/news-events/alerts/2026/08/21/cisa-adds-one-known-exploited-vulnerability-catalog
  - https://nvd.nist.gov/vuln/detail/CVE-2026-73570
tags:
  - attack.initial-access
  - attack.t1190
  - attack.execution
logsource:
  category: process_creation
  product: linux
detection:
  selection_user:
    User|contains: zimbra
  selection_image:
    Image|endswith:
      - /sh
      - /bash
      - /curl
      - /wget
  condition: selection_user and selection_image
falsepositives:
  - Approved Zimbra maintenance or backup jobs
level: critical
```

**Splunk SPL**

```splunk
index=* (user=zimbra OR uid_name=zimbra) (process_name IN ("sh","bash","curl","wget") OR process="*/sh" OR process="*/bash" OR process="*/curl" OR process="*/wget")
| stats count min(_time) as first_seen max(_time) as last_seen values(process) as processes values(process_command_line) as commands by host, user
| sort - last_seen
```

**Elastic KQL**

```kql
event.category: process and user.name: zimbra and process.name: ("sh" or "bash" or "curl" or "wget")
```

### Sigma 2 — RedC2 npm import-time payload

```yaml
title: RedC2 Linux Payload Launched From Node Package
id: 8cb39e17-f76a-4c03-90fc-0e8e8fdb2c08
status: experimental
description: Detects a Node.js process launching a bundled RedShell-style binary or package artifact reported by TrendAI.
author: Hermes Autonomous CTI Agent
references:
  - https://www.trendaisecurity.com/en-us/resources-insights/trendai-security-blog/redc2-ai-powered-linux-implant
tags:
  - attack.execution
  - attack.t1195.002
  - attack.t1059.004
logsource:
  category: process_creation
  product: linux
detection:
  selection_parent:
    ParentImage|endswith: /node
  selection_child:
    Image|endswith:
      - /math-core.bin
      - /math-calc.bin
      - /calc-math.dat
      - /calc-cache.bin
      - /calc.bin
      - /calc-mapping.bin
  selection_cmd:
    CommandLine|contains:
      - RedShell
      - streak-metrics-math
      - dist/index.mjs
  condition: selection_parent and selection_child and selection_cmd
falsepositives:
  - Approved native Node.js modules; validate package provenance and lockfiles
level: critical
```

**Splunk SPL**

```splunk
index=* (parent_process_name="node" OR ParentImage="*/node") (process_name IN ("math-core.bin","math-calc.bin","calc-math.dat","calc-cache.bin","calc.bin","calc-mapping.bin") OR process_path="*RedShell*")
| search command_line="*dist/index.mjs*" OR command_line="*streak-metrics-math*" OR command_line="*RedShell*"
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(command_line) as commands by process_name, parent_process_name
```

**Elastic KQL**

```kql
event.category: process and process.parent.name: "node" and process.command_line: ("*dist/index.mjs*" or "*streak-metrics-math*" or "*RedShell*") and process.name: ("math-core.bin" or "math-calc.bin" or "calc-math.dat" or "calc-cache.bin" or "calc.bin" or "calc-mapping.bin")
```

### Sigma 3 — SynkLoader multi-stage execution

```yaml
title: SynkLoader Teams Phishing Multi-Stage Execution
id: 94cce41c-43fd-4c23-9f80-6f9436fe0054
status: experimental
description: Detects the reported SynkLoader MSI-to-PowerShell-to-Python execution chain and artifacts.
author: Hermes Autonomous CTI Agent
references:
  - https://expel.com/blog/synkloader-when-you-throw-in-everything-but-the-kitchen-sink/
tags:
  - attack.initial-access
  - attack.t1566.002
  - attack.execution
  - attack.t1059.001
  - attack.persistence
  - attack.t1053.005
logsource:
  category: process_creation
  product: windows
detection:
  selection_parent:
    ParentImage|endswith:
      - \\msiexec.exe
      - \\powershell.exe
  selection_child:
    Image|endswith:
      - \\powershell.exe
      - \\pythonw.exe
      - \\schtasks.exe
  selection_artifact:
    CommandLine|contains:
      - cleaner.ps1
      - archive6.zip
      - PowershellCleaner
      - neversoftmain.net
      - rootfarmapp.net
      - tripinupdate.net
  condition: selection_parent and selection_child and selection_artifact
falsepositives:
  - Approved software deployment; require package and change-ticket correlation
level: high
```

**Splunk SPL**

```splunk
index=* (process_name IN ("powershell.exe","pythonw.exe","schtasks.exe") OR Image IN ("*\\powershell.exe","*\\pythonw.exe","*\\schtasks.exe"))
(parent_process_name IN ("msiexec.exe","powershell.exe") OR ParentImage IN ("*\\msiexec.exe","*\\powershell.exe"))
(command_line="*cleaner.ps1*" OR command_line="*archive6.zip*" OR command_line="*PowershellCleaner*" OR command_line="*neversoftmain.net*" OR command_line="*rootfarmapp.net*" OR command_line="*tripinupdate.net*")
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(command_line) as commands by process_name, parent_process_name
```

**Elastic KQL**

```kql
event.category: process and process.name: ("powershell.exe" or "pythonw.exe" or "schtasks.exe") and process.parent.name: ("msiexec.exe" or "powershell.exe") and process.command_line: ("*cleaner.ps1*" or "*archive6.zip*" or "*PowershellCleaner*" or "*neversoftmain.net*" or "*rootfarmapp.net*" or "*tripinupdate.net*")
```

### Sigma 4 — BTR.sys abuse indicators

```yaml
title: Suspicious Defender BTR Remediation Driver Loading
id: 6d77c846-7f50-4d42-a6b8-6c0113d2b12b
status: experimental
description: Detects BTR.sys weaponization indicators reported by Check Point. Legitimate Defender remediation can produce some signals; require signer, parent, timing, and Defender-event correlation.
author: Hermes Autonomous CTI Agent
references:
  - https://research.checkpoint.com/2026/btr-reforged-weaponizing-defenders-remediation-driver-as-a-kernel-operation-primitive/
tags:
  - attack.defense-evasion
  - attack.t1562.001
  - attack.persistence
  - attack.t1543.003
  - attack.t1564.004
logsource:
  category: driver_load
  product: windows
detection:
  selection_driver:
    ImageLoaded|endswith: \\.sys
  selection_artifact:
    ImageLoaded|contains:
      - BTR.sys
      - :changelist
      - MpEngine.dll
    ServiceName|contains:
      - CurrentControlSet\\Services\\
      - BTR
    FileName|contains:
      - BTR.sys
      - :changelist
  condition: selection_driver and selection_artifact
falsepositives:
  - Legitimate Microsoft Defender remediation after reboot
level: high
```

**Splunk SPL**

```splunk
index=* (ImageLoaded="*BTR.sys*" OR ImageLoaded="*:changelist*" OR ImageLoaded="*MpEngine.dll*" OR ServiceName="*CurrentControlSet\\Services\\*")
| stats count min(_time) as first_seen max(_time) as last_seen values(ImageLoaded) as drivers values(ServiceName) as services values(ParentImage) as parents by host
| sort - last_seen
```

**Elastic KQL**

```kql
event.category: driver and (file.name: "BTR.sys" or file.path: "*:changelist*" or process.command_line: "*MpEngine.dll*" or registry.path: "*CurrentControlSet\\Services\\*")
```

## YARA triage rules

No blocking signature is justified without local sample validation. The following are **triage-only** rules supported by source-published strings/artifacts; validate against known-good Node/npm, Defender, and Windows systems before deployment.

```yara
rule Hermes_RedC2_Npm_RedShell_Triage {
    meta:
        description = "Triage RedShell ELF payloads delivered through trojanized npm packages"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://www.trendaisecurity.com/en-us/resources-insights/trendai-security-blog/redc2-ai-powered-linux-implant"
        date = "2026-08-22"
        confidence = "medium; validate package and binary provenance"
    strings:
        $elf = { 7F 45 4C 46 }
        $s_redshell = "RedShell" ascii wide nocase
        $s_loader = "dist/index.mjs" ascii wide nocase
        $s_math = "math-core.bin" ascii wide nocase
        $s_pkg = "streak-metrics-math" ascii wide nocase
        $s_agent = "Red Agent" ascii wide nocase
    condition:
        $elf at 0 and 2 of ($s_*)
}

rule Hermes_SynkLoader_Windows_Triage {
    meta:
        description = "Triage SynkLoader MSI/Python/PowerShell components"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://expel.com/blog/synkloader-when-you-throw-in-everything-but-the-kitchen-sink/"
        date = "2026-08-22"
        confidence = "medium; use source hashes for exact matching"
    strings:
        $pe = { 4D 5A }
        $s_cleaner = "PowershellCleaner" ascii wide nocase
        $s_script = "cleaner.ps1" ascii wide nocase
        $s_archive = "archive6.zip" ascii wide nocase
        $s_dll1 = "msvcp150.dll" ascii wide nocase
        $s_dll2 = "msvcp160.dll" ascii wide nocase
        $s_pdb = "pwshnewdll.pdb" ascii wide nocase
        $s_phish = "PhishLocker" ascii wide nocase
        $s_c2 = "neversoftmain.net" ascii wide nocase
    condition:
        $pe at 0 and 3 of ($s_*)
}

rule Hermes_BTR_Driver_Weaponization_Triage {
    meta:
        description = "Triage BTR.sys remediation-driver abuse artifacts"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://research.checkpoint.com/2026/btr-reforged-weaponizing-defenders-remediation-driver-as-a-kernel-operation-primitive/"
        date = "2026-08-22"
        confidence = "low-medium; legitimate Defender remediation may match"
    strings:
        $pe = { 4D 5A }
        $s_btr = "BTR.sys" ascii wide nocase
        $s_ads = ":changelist" ascii wide nocase
        $s_service = "CurrentControlSet\\Services\\" ascii wide nocase
        $s_mp = "MpEngine.dll" ascii wide nocase
        $s_log = "BootClean.log" ascii wide nocase
    condition:
        $pe at 0 and 2 of ($s_*)
}
```

## Four-step cyber investigation playbook

### 1. Scope & target identification

- Inventory Internet-exposed Zimbra servers, enabled `zimbra-snmp`/SNMP notification configuration, and patch/build state; prioritize assets due before **2026-08-24**.
- Enumerate npm dependency graphs, lockfiles, caches, CI runners, and developer endpoints; identify hosts that imported any RedC2 package or ran suspicious bundled binaries.
- Inventory Windows endpoints with Teams, Defender, EDR, and privileged developer/admin access; identify SynkLoader MSI/PowerShell activity and BTR driver loads.
- Identify AWS accounts, root access keys, IAM AdministratorAccess users, organization management accounts, key age, public exposure sources, and CloudTrail retention.

### 2. SIEM/EDR hunting methodology

- Deploy the four Sigma/SPL/KQL rules and correlate host, user, parent/child process, signer, network direction, timestamps, and change-ticket context.
- Hunt Zimbra SMTP/SNMP activity followed by `zimbra`-owned shell/download processes; do not equate scanning with successful command execution.
- Hunt RedC2 package names, `dist/index.mjs`, Node-to-ELF child process creation, chmod `0755`, `217.60.77.63:8792`, the three RedC2/SynkLoader domains, and the source-published SHA-256 values.
- Hunt Teams/M365 impersonation messages, Azure Blob MSI downloads, `msiexec → powershell → pythonw`, `cleaner.ps1`, scheduled tasks, fake-lock-screen behavior, and proxy/tunnel connections.
- Hunt BTR randomized service/driver creation, ADS `:changelist`, `SeLoadDriverPrivilege`, security-tool deletion, and Defender event/reboot correlation. Hunt AWS CloudTrail for use of internal watchlisted exposed access keys, root activity, IAM changes, role assumption, data access, and unusual spend.

### 3. Triage & containment

- Zimbra: remove public exposure where possible, patch, preserve logs and volatile/process evidence, revoke suspected service credentials, and inspect for persistence or outbound connections.
- RedC2: isolate affected build/developer hosts, preserve npm caches and endpoint evidence, quarantine affected lockfiles/artifacts, rotate source-control/cloud/browser/SSH credentials, and rebuild from verified packages.
- SynkLoader: isolate endpoint, revoke/reset credentials entered into the fake lock screen, invalidate M365 sessions, block the exact C2/URL indicators after validation, and preserve MSI/archive/script evidence.
- BTR: do not delete legitimate Defender artifacts blindly; suspend suspected host activity, preserve driver/service/ADS/Defender telemetry, and validate signer and transaction provenance. AWS: revoke and rotate matching keys, review blast radius, and enforce root-key and age controls.

### 4. Forensic validation

- Preserve synchronized firewall, SMTP/proxy, Zimbra, M365/Teams, EDR/Sysmon, Windows driver/service/registry/ADS, Linux audit, npm/Cargo/CI, AWS CloudTrail/IAM, and billing telemetry.
- Confirm exploitation versus scanning or benign administration by correlating successful responses, process lineage, file writes, credential use, project/account mutations, and persistence.
- Hash and preserve suspicious MSI, scripts, archives, npm packages, ELF/PE/DLL/driver files; compare against the 12 source-published SynkLoader SHA-256 values and vendor/research artifacts. Do not infer hashes from filenames.
- Validate remediation with version/build checks, external exposure scans, clean dependency rebuilds, credential-use reviews, AWS key re-verification, Defender signer/event correlation, and owner-approved return-to-service decisions.

## Feed collection status

| Registered/supplemental source | Result |
|---|---|
| CISA KEV JSON | Reachable; Zimbra `CVE-2026-73570` added 2026-08-21 and due 2026-08-24 |
| CISA advisories | Reachable; no additional selected enterprise-grade item in window |
| TrendAI/ZDI, Unit 42, Cisco Talos, DFIR, SentinelLabs, Red Canary, Krebs | Reachable; no additional selected net-new high-severity item; Unit 42 ChainDrop treated as prior context |
| BleepingComputer | Reachable; SynkLoader and AWS exposure selected; unrelated product/news items filtered |
| The Hacker News supplemental | Reachable; RedC2 and BTR selected |
| Google TAG | Configured feed returned HTTP 404 |
| SANS ISC | HTTP 200 but returned non-XML content; parse failed |
| MSRC | Feed returned malformed XML/HTTP variability; no new item selected from this run |
| Microsoft Threat Intelligence | Reachable during collection; no additional selected item |

## Artifact and portal status

- Raw feed collection: [`collection_20260822.json`](collection_20260822.json) — 15 registered/supplemental streams, 10 qualifying feed entries before relevance filtering.
- Selected technical corpus: [`selected_corpus_20260822.txt`](selected_corpus_20260822.txt).
- Deterministic IoCs: [`iocs_20260822.json`](iocs_20260822.json).
- Direct enrichment: [`enrichment_20260822.json`](enrichment_20260822.json).
- Portal database and static index were updated for this report.

**Analytic caveats:** Exploitation and capability claims remain attributed to their cited sources. No named actor is established for SynkLoader or RedC2; RedC2 is described as a commodity/offensive framework marketed by “MarlboroMan,” not as proof of campaign attribution. AWS research is aggregate exposure intelligence and publishes no key material. BTR.sys findings are a weaponization demonstration, not confirmed enterprise exploitation. Shared services and benign route-probe indicators are explicitly dispositioned and should not be globally blocked without local validation. OTX pulse counts are context only and do not establish maliciousness or attribution.
