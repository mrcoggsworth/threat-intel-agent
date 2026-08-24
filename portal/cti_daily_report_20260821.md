# Hermes Daily CTI Briefing & Playbook Synthesis — 2026-08-21

**Collection time:** `2026-08-21T13:01:14Z`  
**Window:** `2026-08-20T13:01:14Z`–`2026-08-21T13:01:14Z`; 48-hour deduplication context  
**Assessment:** **CRITICAL**  
**Scope:** Enterprise communications, identity, DevSecOps, software supply chain, developer infrastructure, and sandboxed execution.

## BLUF

1. **TrueConf Server CVE-2026-72529 and CVE-2026-72530 are active-exploitation KEV additions.** Unauthenticated attackers can execute arbitrary scripts over TCP/4307 and escape the server's isolated environment to the host. CISA deadlines are **2026-08-23** and **2026-09-03**, respectively.
2. **GitLab CVE-2026-19478 is being exploited against honeypots within days of disclosure.** The unauthenticated GraphQL flaw can modify/delete public projects and data; hunt for `@gl_introduced` and patch self-hosted instances immediately.
3. **A Rust crates.io compromise executed malware at build time.** Malicious releases of `arrayref`, `internment`, and `append-only-vec` were available for 86–107 minutes. Any CI/developer host that built affected versions requires supply-chain triage, credential review, and artifact preservation.
4. **Microsoft Entra ID CVE-2026-69836 is CVSS 10.0 and was exploited in the wild, but Microsoft says the cloud service is fully mitigated and requires no customer action.** Treat as an awareness/update item; do not invent customer-side IoCs.
5. **isolated-vm GHSA-864f-rcv7-6rh4 breaks a key sandbox trust boundary.** Versions through 7.0.0 can permit guest-to-host memory corruption and potential RCE; upgrade to 6.2.0 or 7.0.1+.
6. **Cisco Crosswork/Secure Workload released hardening fixes for nine critical/high flaws**, including five CVSS 10.0 issues. Cisco says exploitation is not known; this is an urgent patch/watch item, not an exploitation claim.

## Deduplication and provenance

- `.hermes/memories/MEMORY.md` contains Microsoft July Patch Tuesday (`CVE-2026-56155`, `CVE-2026-56164`) and SharePoint `CVE-2026-55040`; none are repeated as new findings.
- The 2026-08-20 report already covered UAT-10147/SPECTRE, Zimbra `CVE-2026-73570`, FUXA, AIT-GUI, MLflow, NetScaler, and Elementor. They are suppressed here as duplicates; no material update was found in the current 24-hour collection.
- Session history was searched for CVE, zero-day, APT, ransomware, and exploit overlap. Previously reported Microsoft, SharePoint, Cisco ASA/FTD, Lazarus, Siemens S7, Windchill, SilkParasite, MLflow, Zimbra, FUXA, AIT-GUI, NetScaler, and Elementor items were treated as duplicates or prior updates.
- Source precedence: CISA KEV/NVD/FIRST for vulnerability status and scoring; TrueConf/Kaspersky, GitLab, Rust Security Response Team, Cisco, and Endor Labs for primary technical details; BleepingComputer and The Hacker News are corroborating sources.

## Priority findings

### 1. TrueConf Server active exploitation — `CVE-2026-72529` / `CVE-2026-72530`

| Field | Detail |
|---|---|
| Status | **NEW — CISA KEV / active exploitation** |
| Affected product | TrueConf Server self-hosted communications/video platform |
| CVSS / EPSS | `9.3` / `0.00284` for CVE-2026-72529; `9.5` / `0.00340` for CVE-2026-72530 |
| Exposure | Unauthenticated network access over TCP/4307 |
| Impact | Arbitrary script execution; sandbox escape to host OS and arbitrary code execution |
| CISA dates | CVE-2026-72529 due **2026-08-23**; CVE-2026-72530 due **2026-09-03** |
| Attribution | Kaspersky reports Head Mare exploitation since at least July 2026; this attribution is secondary reporting, not independently established here |
| Remediation | Apply TrueConf fixes: versions `5.3.9`, `5.4.9`, or `5.5.5` as applicable; restrict TCP/4307 exposure and validate vendor guidance |

**Action:** Inventory all self-hosted TrueConf deployments, remove Internet exposure, patch before the applicable CISA deadline, and review client-installer integrity. Hunt TCP/4307 access, undocumented-function requests, new scripts, altered installers, and post-exploitation child processes on TrueConf hosts.

**Sources:** [CISA KEV](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json) · [NVD CVE-2026-72529](https://nvd.nist.gov/vuln/detail/CVE-2026-72529) · [NVD CVE-2026-72530](https://nvd.nist.gov/vuln/detail/CVE-2026-72530) · [BleepingComputer](https://www.bleepingcomputer.com/news/security/cisa-orders-feds-to-patch-actively-exploited-trueconf-server-flaws/) · [TrueConf advisory](https://trueconf.com/blog/news/security-fixes-updates-and-advisories)

### 2. GitLab GraphQL code injection — `CVE-2026-19478`

- **Status:** **NEW — active exploitation observed by watchTowr against honeypots**.
- **Impact:** Unauthenticated attackers can modify or delete publicly accessible projects and user data; reporting also describes repository deletion, forged merge records, and maintainer lockout.
- **CVSS / EPSS:** `9.4`, vector `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:H/A:H`; EPSS `0.01506`, 72.361st percentile (2026-08-20 snapshot).
- **Affected/fixed:** GitLab CE/EE 18.2 before `18.11.11`, 19.0 before `19.0.8`, 19.1 before `19.1.6`, and 19.2 before `19.2.4`.
- **Hunt:** Web requests containing `@gl_introduced`, especially against `/api/graphql`; correlate with project deletion, permission changes, merge-record changes, and maintainer bans.
- **Mitigation:** Upgrade to the fixed release; if patching is delayed, restrict unauthenticated access to `/api/graphql` and remove public repository access where operationally acceptable.

**Sources:** [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-19478) · [The Hacker News / watchTowr](https://thehackernews.com/2026/08/gitlab-cve-2026-19478-comes-under.html) · [GitLab CVE project](https://about.gitlab.com/security/cve/)

### 3. Rust crates.io build-time supply-chain compromise

- **Status:** **NEW — confirmed malicious package releases; compromise scope requires local validation**.
- **Affected releases:** `arrayref 0.3.10`, `internment 0.8.7`, `append-only-vec 0.1.9`; all were published on 2026-08-20 and removed after 86–107 minutes.
- **Execution:** A typosquatted `proc-macro1` dependency executed a build script during `cargo build`, `cargo check`, or `cargo test`; it did not require application code to call the affected crate.
- **Observed payload:** `23.254.165.112:9089` payload host, `23.254.165.112:443` C2, `hwsrv-798836.hostwindsdns.com`, `/tmp/rust-setup`, `%TEMP%\\rust-setup.ps1`, `%TEMP%\\rust-setup-launch.vbs`, and C2 path `/49890878`.
- **Persistence/collection:** Windows Registry Run key, macOS LaunchAgent, Linux systemd user service; browser credential access from Chrome, Brave, and Edge was reported.
- **Scope:** `arrayref` had 245,385,500 all-time downloads and 403 dependent crates according to the corroborating report. No CVE or named-actor attribution is established.

**Action:** Search every CI/developer host and lockfile for affected versions and `proc-macro1`; preserve Cargo caches before cleanup; isolate hosts that built affected versions; review process/network telemetry for `rustc`, Cargo, PowerShell, `wscript`, `/tmp/rust-setup`, the listed IP/domain, and `/49890878`; rotate credentials exposed to build environments; rebuild from known-good lockfiles. Pin `arrayref` to `0.3.9` or earlier only as an interim containment measure and verify current RustSec guidance.

**Sources:** [Rust Security Response Team](https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/) · [The Hacker News](https://thehackernews.com/2026/08/rust-supply-chain-attack-puts-build.html) · [StepSecurity analysis](https://www.stepsecurity.io/blog/arrayref-rust-crate-supply-chain-attack)

### 4. Microsoft Entra ID deserialization RCE — `CVE-2026-69836`

- **Status:** **NEW — exploited in the wild; Microsoft-managed mitigation complete**.
- **Severity:** CVSS `10.0`, vector `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H`.
- **Technical detail:** Untrusted-data deserialization permits unauthorized network code execution in the cloud IAM service.
- **Provider statement:** Microsoft says the service is fully mitigated and there is no customer action. No exploit path, campaign, or customer-side IoC was published.
- **Action:** Record the service-side mitigation, monitor Microsoft service-health/security communications, and avoid treating the CVSS score as evidence that customer-hosted Entra components require emergency patching.

**Sources:** [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-69836) · [Microsoft Security Response Center advisory portal](https://msrc.microsoft.com/update-guide/advisory) · [The Hacker News](https://thehackernews.com/2026/08/microsoft-entra-id-flaw-cvss-100.html)

### 5. isolated-vm sandbox escape — `GHSA-864f-rcv7-6rh4`

- **Status:** **NEW — critical developer/AI execution-boundary issue; no CVE assigned**.
- **Impact:** A type confusion in `ExternalCopy` handling of `transferList` can corrupt host memory. Demonstrated impact ranges from reliable host-process crash to guest-to-host control-flow hijack and potential RCE.
- **Affected/fixed:** Versions through `7.0.0` are affected; fixed releases are `6.2.0` and `7.0.1`.
- **Action:** Upgrade all Node.js services that execute untrusted JavaScript, review whether sandboxes receive `ivm.Reference` capabilities, and isolate/review developer or agent workloads that ran untrusted code. Do not claim exploitation; the reporting withheld full exploit details.

**Source:** [The Hacker News / Endor Labs](https://thehackernews.com/2026/08/isolated-vm-flaw-lets-sandboxed.html)

### 6. Cisco Crosswork / Secure Workload hardening release

- **Status:** **NEW — urgent patch/watch; Cisco says not known exploited**.
- **Crosswork:** `CVE-2026-20030` SQL injection (CVSS 10.0), `CVE-2026-20357` missing authentication (10.0), `CVE-2026-20358` external control of filesystem (10.0), and `CVE-2026-20359` insufficiently protected credentials (9.9); fixed in Crosswork `7.2.1-SP`.
- **Secure Workload:** `CVE-2026-20231` (9.9), `CVE-2026-20315` (10.0), `CVE-2026-20317` (10.0), `CVE-2026-20318` (9.6), and `CVE-2026-20319` (7.5); fixed in `3.10.9.1` and `4.0.4.16` as applicable.
- **Action:** Inventory SaaS/on-prem deployments, patch, review admin/API access and credential exposure, and prioritize systems reachable from untrusted network segments.

**Sources:** [Cisco Crosswork advisory](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-hardening-crosswork-UzDTU9Vh) · [Cisco Secure Workload advisory](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-hardening-csw1-shSvndWP) · [Corroborating report](https://thehackernews.com/2026/08/cisco-patches-nine-crosswork-and-secure.html)

## Deterministic IoC and artifact extraction

Extraction ran against the normalized technical evidence corpus using the `ioc-parser` patterns, with defanging normalization and global/private-IP filtering. Source URLs were kept as provenance and not mixed into the IoC set.

```json
{
  "ipv4": ["23.254.165.112"],
  "ipv6": [],
  "md5": [],
  "sha256": [],
  "domains": ["hwsrv-798836.hostwindsdns.com"],
  "urls": [],
  "cves": ["CVE-2026-19478", "CVE-2026-69836", "CVE-2026-72529", "CVE-2026-72530"],
  "ghsas": ["GHSA-864f-rcv7-6rh4"],
  "registry_keys": ["HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"],
  "artifacts": [
    "arrayref 0.3.10", "internment 0.8.7", "append-only-vec 0.1.9", "proc-macro1",
    "/tmp/rust-setup", "%TEMP%\\rust-setup.ps1", "%TEMP%\\rust-setup-launch.vbs",
    "/api/graphql", "@gl_introduced", "/49890878", "~/.cargo/registry/cache",
    "LaunchAgent", "systemd user service"
  ]
}
```

The IP/domain are observed Rust supply-chain infrastructure indicators; no reputation verdict is claimed. Block or sinkhole only after local validation and change-control review.

## Enrichment status and risk scoring

| Item | CISA KEV | NVD CVSS | FIRST EPSS | Reputation APIs |
|---|---|---:|---:|---|
| TrueConf `CVE-2026-72529` | Yes; due 2026-08-23 | 9.3 | 0.00284 / 21.051 percentile | Not queried: no API credentials assumed |
| TrueConf `CVE-2026-72530` | Yes; due 2026-09-03 | 9.5 | 0.00340 / 27.168 percentile | Not queried: no API credentials assumed |
| GitLab `CVE-2026-19478` | No entry observed | 9.4 | 0.01506 / 72.361 percentile | Not queried: no API credentials assumed |
| Entra `CVE-2026-69836` | No entry observed | 10.0 | No EPSS record returned | Not applicable to provider-mitigated service claim |
| isolated-vm `GHSA-864f-rcv7-6rh4` | Not a CVE/KEV record | No NVD score | Not available | Not queried |
| Rust supply chain | No CVE | Not applicable | Not applicable | Not queried: no API credentials assumed |

AbuseIPDB, VirusTotal, and AlienVault OTX results are intentionally **not claimed** because no credentials were assumed or available. EPSS is a probability estimate and does not override direct exploitation evidence.

## ATT&CK mapping

| Finding | Techniques supported by evidence |
|---|---|
| TrueConf | `T1190` Exploit Public-Facing Application; `T1059.004` Unix Shell only if post-exploit process telemetry confirms shell execution; `T1105` if trojanized installer/payload transfer is observed |
| GitLab | `T1190` Exploit Public-Facing Application; `T1565.001` Stored Data Manipulation for project/data tampering |
| Rust supply chain | `T1195.002` Compromise Software Supply Chain; `T1059.001` PowerShell; `T1059.005` Visual Basic; `T1105` Ingress Tool Transfer; `T1547.001` Registry Run Keys/Startup Folder; `T1543.002` Systemd Service; `T1555.003` Credentials from Web Browsers; `T1071.001` Web Protocols |
| Entra | `T1190` is not asserted for customer environments; provider-side exploitation evidence is insufficient for a customer ATT&CK claim |
| isolated-vm | `T1611` Escape to Host is a defensible mapping for a confirmed sandbox escape capability; exploitation in enterprise environments is not claimed |
| Cisco | `T1190` only as exposure/hunt context; exploitation is explicitly not reported |

## Detection rule synthesis

### Sigma 1 — TrueConf TCP/4307 exposure

```yaml
title: TrueConf Server Exploit Surface on TCP 4307
id: 1e0d9e7a-4e06-4c1d-a9ea-7d0e9b8e2c11
status: experimental
description: Detects inbound network connections to the TrueConf Server service port associated with CVE-2026-72529 and CVE-2026-72530. Correlate with TrueConf process, script, and installer telemetry.
author: Hermes Autonomous CTI Agent
references:
  - https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
  - https://nvd.nist.gov/vuln/detail/CVE-2026-72529
  - https://nvd.nist.gov/vuln/detail/CVE-2026-72530
tags:
  - attack.initial-access
  - attack.t1190
logsource:
  category: firewall
  product: generic
detection:
  selection:
    destination.port: 4307
    network.direction: inbound
  condition: selection
falsepositives:
  - Approved internal TrueConf clients
level: critical
```

**Splunk SPL**

```splunk
index=* (dest_port=4307 OR destination_port=4307) (direction=inbound OR action=allowed)
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(dest_ip) as dest_ips values(action) as actions by dest_port
| sort - last_seen
```

**Elastic KQL**

```kql
event.category: network and network.direction: inbound and destination.port: 4307
```

### Sigma 2 — GitLab GraphQL exploitation probe

```yaml
title: GitLab CVE-2026-19478 GraphQL Exploitation Probe
id: 7f2f72e5-3da8-41a4-9cb1-89f7a0f1e6aa
status: experimental
description: Detects GitLab GraphQL requests containing the directive marker reported by watchTowr for CVE-2026-19478. Correlate with project deletion, data modification, and maintainer changes.
author: Hermes Autonomous CTI Agent
references:
  - https://nvd.nist.gov/vuln/detail/CVE-2026-19478
  - https://thehackernews.com/2026/08/gitlab-cve-2026-19478-comes-under.html
tags:
  - attack.initial-access
  - attack.t1190
  - attack.impact
  - attack.t1565.001
logsource:
  category: webserver
  product: gitlab
detection:
  selection:
    cs-uri-stem|endswith: /api/graphql
    cs-request-body|contains: '@gl_introduced'
  condition: selection
falsepositives:
  - Authorized GitLab security testing; require ticket correlation
level: critical
```

**Splunk SPL**

```spl
index=* (uri_path="*/api/graphql" OR cs_uri_stem="*/api/graphql")
("@gl_introduced" OR request_body="*@gl_introduced*")
| stats count min(_time) as first_seen max(_time) as last_seen values(src_ip) as src_ips values(http_status) as statuses values(user) as users by host, uri_path
| sort - last_seen
```

**Elastic KQL**

```kql
(event.category: web or event.dataset: web) and url.path: */api/graphql and http.request.body.content: "*@gl_introduced*"
```

### Sigma 3 — Rust malicious build chain

```yaml
title: Suspicious Rust Cargo Build Launching Script Interpreter
id: 8a6e4db1-0ee3-4c39-8b8d-3c7e4d7f4f91
status: experimental
description: Detects script interpreters launched from Rust Cargo/rustc build activity with artifacts reported for the 2026-08-20 crates.io compromise.
author: Hermes Autonomous CTI Agent
references:
  - https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/
  - https://thehackernews.com/2026/08/rust-supply-chain-attack-puts-build.html
tags:
  - attack.execution
  - attack.t1059.001
  - attack.t1059.005
  - attack.supply-chain
  - attack.t1195.002
logsource:
  category: process_creation
  product: windows
detection:
  selection_parent:
    ParentImage|endswith:
      - '\\cargo.exe'
      - '\\rustc.exe'
  selection_child:
    Image|endswith:
      - '\\powershell.exe'
      - '\\wscript.exe'
  selection_artifact:
    CommandLine|contains:
      - 'rust-setup'
      - '23.254.165.112'
      - 'hwsrv-798836.hostwindsdns.com'
      - '/49890878'
  condition: selection_parent and selection_child and selection_artifact
falsepositives:
  - Approved build scripts; validate dependency lockfile and package provenance
level: critical
```

**Splunk SPL**

```spl
index=* (process_name IN ("powershell.exe","wscript.exe") OR Image IN ("*\\powershell.exe","*\\wscript.exe"))
(parent_process_name IN ("cargo.exe","rustc.exe") OR ParentImage IN ("*\\cargo.exe","*\\rustc.exe"))
(command_line="*rust-setup*" OR command_line="*23.254.165.112*" OR command_line="*hwsrv-798836.hostwindsdns.com*" OR command_line="*/49890878*")
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(user) as users values(command_line) as command_lines by process_name, parent_process_name
| sort - last_seen
```

**Elastic KQL**

```kql
event.category: process and process.parent.name: ("cargo.exe" or "rustc.exe") and process.name: ("powershell.exe" or "wscript.exe") and process.command_line: ("*rust-setup*" or "*23.254.165.112*" or "*hwsrv-798836.hostwindsdns.com*" or "*/49890878*")
```

### Sigma 4 — Rust persistence/artifact activity

```yaml
title: Rust Supply Chain Payload Persistence Artifacts
id: 4f1cdd3b-7c9a-4e3b-a8a7-c04e6aa2c6c4
status: experimental
description: Detects file, registry, or service artifacts reported for the 2026-08-20 malicious Rust crate build chain. Requires local allowlisting and package provenance validation.
author: Hermes Autonomous CTI Agent
references:
  - https://thehackernews.com/2026/08/rust-supply-chain-attack-puts-build.html
tags:
  - attack.persistence
  - attack.t1547.001
  - attack.t1543.002
  - attack.credential-access
  - attack.t1555.003
logsource:
  category: file_event
  product: generic
detection:
  selection:
    TargetFilename|contains:
      - '/tmp/rust-setup'
      - 'rust-setup.ps1'
      - 'rust-setup-launch.vbs'
      - '/.cargo/registry/cache'
      - 'CurrentVersion\\Run'
      - 'LaunchAgent'
      - 'systemd'
  condition: selection
falsepositives:
  - Legitimate Rust build caches and approved developer tooling
level: high
```

**Splunk SPL**

```spl
index=* (file_path="*/tmp/rust-setup*" OR file_path="*rust-setup.ps1" OR file_path="*rust-setup-launch.vbs" OR file_path="*/.cargo/registry/cache/*" OR registry_path="*CurrentVersion\\Run*" OR file_path="*LaunchAgent*" OR file_path="*systemd*")
| stats count min(_time) as first_seen max(_time) as last_seen values(host) as hosts values(user) as users values(process) as processes by file_path, registry_path
| sort - last_seen
```

**Elastic KQL**

```kql
(event.category: file or event.category: registry) and (file.path: ("*/tmp/rust-setup*" or "*rust-setup.ps1" or "*rust-setup-launch.vbs" or "*/.cargo/registry/cache/*" or "*LaunchAgent*" or "*systemd*") or registry.path: "*CurrentVersion\\Run*")
```

### YARA disposition

A sample-based blocking signature is not justified for TrueConf, GitLab, Entra, isolated-vm, or Cisco because no malware sample, byte pattern, or unique binary string was published. A low-noise Rust triage rule is supported by the reported PE/ELF artifact strings, but it must be validated against known-good developer systems before deployment.

```yara
rule Hermes_Rust_Crates_SupplyChain_Triage {
    meta:
        description = "Triage artifacts for the 2026-08-20 malicious Rust crates build chain"
        author = "Hermes Autonomous CTI Agent"
        reference = "https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/"
        date = "2026-08-21"
        confidence = "medium; sample and environment validation required"
    strings:
        $pe = { 4D 5A }
        $s_ip = "23.254.165.112" ascii wide
        $s_domain = "hwsrv-798836.hostwindsdns.com" ascii wide nocase
        $s_path = "rust-setup" ascii wide nocase
        $s_c2 = "/49890878" ascii wide
        $s_proc = "proc-macro1" ascii wide nocase
    condition:
        $pe at 0 and 2 of ($s_*)
}
```

## Four-step cyber investigation playbook

### 1. Scope & target identification

- Inventory TrueConf Server, self-hosted GitLab CE/EE, Rust/Cargo CI runners and developer workstations, Node.js services using isolated-vm, and Cisco Crosswork/Secure Workload deployments.
- Identify versions, Internet exposure, authentication boundaries, build identities, package-lock/lockfile provenance, and access to source-control, cloud, browser, and signing credentials.
- For Rust, identify hosts that built `arrayref 0.3.10`, `internment 0.8.7`, or `append-only-vec 0.1.9` during the exposure window; preserve caches before deletion.

### 2. SIEM/EDR hunting methodology

- Deploy the Sigma/SPL/KQL rules above and correlate source IP, host, user, process lineage, request body/path, response status, file creation, registry/service changes, and first/last-seen timestamps.
- Hunt TrueConf TCP/4307 access and scripts; GitLab `/api/graphql` requests containing `@gl_introduced`; Rust `cargo`/`rustc` child interpreters, payload IP/domain, `/tmp/rust-setup`, Windows script launchers, browser-database reads, and persistence artifacts.
- Review GitLab audit events for public project deletion/modification, merge-record changes, maintainer bans, token creation, and permission changes.
- For isolated-vm, review service inputs and crashes/SIGSEGV around sandbox workloads; do not infer exploitation from package presence alone.

### 3. Triage & containment

- Isolate suspected TrueConf and CI/developer hosts while preserving volatile, package-cache, build, EDR, and network evidence.
- Patch TrueConf by CISA deadlines; upgrade GitLab to `18.11.11`, `19.0.8`, `19.1.6`, or `19.2.4`; upgrade isolated-vm to `6.2.0` or `7.0.1+`; apply Cisco fixed releases.
- Quarantine affected Rust caches and lockfiles, block the observed Rust infrastructure after validation, rotate secrets accessible to impacted builds, revoke sessions/tokens, and rebuild from verified sources.
- Coordinate with source-control, identity, and application owners before destructive cleanup; preserve evidence for any suspected installer replacement or repository tampering.

### 4. Forensic validation

- Preserve firewall, reverse-proxy, GitLab audit/API, TrueConf, Windows event/Sysmon, Linux audit, Cargo build logs, package caches, EDR, browser, registry, LaunchAgent, and systemd telemetry with synchronized timestamps.
- Confirm exploitation versus scanning by correlating successful responses, process lineage, file writes, project mutations, installer hashes, outbound connections, and credential use. Do not infer hashes from filenames.
- Hash and preserve suspicious crates, build scripts, payloads, scripts, and persistence files; compare against RustSec/vendor advisories and known-good builds.
- Validate remediation with version/build checks, external exposure scans, clean lockfile rebuilds, repository integrity review, credential-use review, and owner-approved return-to-service decisions.

## Feed collection status

| Registered/supplemental source | Result in 24-hour window |
|---|---|
| CISA KEV | Reachable; two TrueConf entries added 2026-08-20 |
| CISA advisories | Reachable; no parseable new material in window |
| Cisco Talos | Reachable; newsletter item, no selected new campaign |
| Unit 42, Microsoft TI, SentinelLabs, ZDI, Krebs, DFIR | Reachable; no selected enterprise-grade item in window |
| Red Canary, SANS ISC | Reachable; no selected high-severity campaign; SANS entries were operational guidance |
| BleepingComputer | Reachable; TrueConf, Entra, Rust, and Elementor items collected |
| MSRC | Feed malformed during parse; Microsoft advisory portal queried separately |
| Google TAG | Configured feed returned HTTP 404 |
| The Hacker News supplemental | Reachable; GitLab, Entra, Rust, isolated-vm, Cisco, and corroborating items collected |

## Source register

- [CISA KEV JSON](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json)
- [BleepingComputer — TrueConf exploitation](https://www.bleepingcomputer.com/news/security/cisa-orders-feds-to-patch-actively-exploited-trueconf-server-flaws/)
- [The Hacker News — GitLab CVE-2026-19478](https://thehackernews.com/2026/08/gitlab-cve-2026-19478-comes-under.html)
- [Rust Security Response Team — arrayref supply chain](https://blog.rust-lang.org/2026/08/20/supply-chain-attack-on-arrayref/)
- [The Hacker News — Rust supply chain](https://thehackernews.com/2026/08/rust-supply-chain-attack-puts-build.html)
- [The Hacker News — Entra ID CVE-2026-69836](https://thehackernews.com/2026/08/microsoft-entra-id-flaw-cvss-100.html)
- [The Hacker News — isolated-vm GHSA](https://thehackernews.com/2026/08/isolated-vm-flaw-lets-sandboxed.html)
- [Cisco Crosswork advisory](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-hardening-crosswork-UzDTU9Vh)
- [Cisco Secure Workload advisory](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-hardening-csw1-shSvndWP)
- [NVD CVE API](https://services.nvd.nist.gov/rest/json/cves/2.0)
- [FIRST EPSS API](https://api.first.org/data/v1/epss)
- Authoritative source registry: `/home/cptcoggsworth/code/threat-intel-agent/config/sources.json`

**Analytic caveats:** Exploitation claims are attributed to the cited reporters. Head Mare attribution is secondary Kaspersky reporting. The Rust IP/domain are observed indicators from reporting; current ownership/reputation was not independently scored. No customer-side action or IoC is inferred for the Microsoft-managed Entra service. YARA content is triage-only until sample validation.
