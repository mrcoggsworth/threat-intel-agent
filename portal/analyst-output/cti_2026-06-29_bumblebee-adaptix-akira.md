# Targeted CTI Report: Bumblebee, AdaptixC2, and Akira

- **Source:** [https://thedfirreport.com/2026/06/29/from-bing-search-to-ransomware-bumblebee-and-adaptixc2-deliver-akira-3/](https://thedfirreport.com/2026/06/29/from-bing-search-to-ransomware-bumblebee-and-adaptixc2-deliver-akira-3/)
- **Published:** 2026-06-29 (source search result; exact article publication time retained by source)
- **Collected:** 2026-08-27T02:27:56Z
- **Source class:** Original incident-response research
- **Confidence:** High for directly stated IOCs and behaviors; reputation is provider-observed context only.

## Executive summary
The DFIR Report describes a Bing SEO-poisoning intrusion in which a trojanized MSI delivered Bumblebee, followed by AdaptixC2 activity and Akira ransomware deployment. The report contains network and file telemetry suitable for indicator-based hunting. This is public threat intelligence only and does not establish any organization’s exposure.

## ATT&CK mapping
- **T1189 — Drive-by Compromise:** Bing SEO poisoning delivered trojanized MSI installers.
- **T1204.002 — User Execution: Malicious File:** A user executed the downloaded MSI installer.
- **T1218.007 — System Binary Proxy Execution: Msiexec:** MSI execution used the Windows Installer path.
- **T1574.002 — Hijack Execution Flow: DLL Side-Loading:** msimg32.dll/version.dll side-loading was described.
- **T1055 — Process Injection:** AdaptixC2 shellcode was injected into a legitimate process.
- **T1059.001 — Command and Scripting Interpreter: PowerShell:** PowerShell was used during post-compromise activity.
- **T1018 — Remote System Discovery:** Network discovery activity was described.
- **T1021.001 — Remote Services: RDP:** RDP was used for lateral movement.
- **T1021.002 — Remote Services: SMB/Windows Admin Shares:** SMB and remote execution tooling were described.
- **T1021.006 — Remote Services: Windows Remote Management:** WinRM activity was described.
- **T1003.003 — OS Credential Dumping: NTDS:** ntds.dit collection was described.
- **T1486 — Data Encrypted for Impact:** Akira ransomware deployment was the reported outcome.

## Indicators

### IPv4
- `109.205.195.211`
- `170.130.55.223`
- `171.22.183.43`
- `172.96.137.160`
- `185.174.100.203`
- `188.40.187.145`
- `192.121.22.94`
- `193.242.184.150`
- `194.127.178.21`
- `4.239.95.1`
- `84.32.84.32`

### MD5
- `124a48b78060fa851e1cc077ca35713c`
- `8c113b3aa82c81eee7c6b4ed0ba9a90f`
- `ca8646dfc88423bb9fffda811160cebe`

### SHA-256
- `186b26df63df3b7334043b47659cba4185c948629d857d47452cc1936f0aa5da`
- `a6df0b49a5ef9ffd6513bfe061fb60f6d2941a440038e2de8a7aeb1914945331`
- `de730d969854c3697fd0e0803826b4222f3a14efe47e4c60ed749fff6edce19d`

### URLs
- `https://tria.ge/250530-ttmjhayzhw`
- `https://tria.ge/250812-zw4tfszpy4`

### Parser domain results
- `1.ps1`
- `10.redacted`
- `2rxyt8yrhq0bgj.org`
- `2rxyt9urhq0bgj.org`
- `5ka8rxp6t6eup2.org`
- `6cimu4mc085em8.org`
- `8doj8uvx604eck.org`
- `adgnsy.exe`
- `advanced-ip-scanner.msi`
- `asazqzdjz.avhdx`
- `atexec.py`
- `certgraveyard.org`
- `cmd.exe`
- `comsvcs.dll`
- `consent.exe`
- `d1hmxkpwby0d4s.org`
- `delete.me`
- `detection.fyi`
- `download-center.online`
- `download-server.online`
- `ev2sirbd269o5j.org`
- `ewujsfb1dp5ran.org`
- `explorer.exe`
- `g7wo.sys`
- `hlpdrv.sys`
- `hosts1.txt`
- `icardagt.exe`
- `ip-scanner.org`
- `kernelbase.dll`
- `ks501oz9nm3v05.org`
- `kwywztxoo2xdot.org`
- `ky1d1p1daahe5t.org`
- `locker.exe`
- `manageengine-opmanager.msi`
- `mmc20.application`
- `mmcexec.py`
- `msimg32.dll`
- `msimg32d.dll`
- `n.exe`
- `net.exe`
- `netml.shop`
- `nltest.exe`
- `ntdll.dll`
- `ntds.dit`
- `opmanager.pro`
- `ovh1kn1tcqw5kp.org`
- `powershell.exe`
- `psql.exe`
- `recentservers.xml`
- `redacted.lan`
- `redacted.lan.txt`
- `redacted.txt`
- `rundll32.exe`
- `rustdesk.exe`
- `rwdrv.sys`
- `shares.txt`
- `shopping5.shop`
- `sigmasearchengine.com`
- `smbexec.py`
- `soft-hub.pro`
- `soft-server.online`
- `spn.txt`
- `ssh.exe`
- `taskmgr.exe`
- `tria.ge`
- `trustanchors.txt`
- `u8vfsh.docx`
- `urlscan.io`
- `v5rjsdqogstopr.org`
- `vector`
- `version.dll`
- `wab.exe`
- `wbadmin.exe`
- `whoami.exe`
- `win.exe`
- `wmiexec.py`
- `wmiprvse.exe`
- `yj6jurm5qqkye5.org`
- `zenmap.pro`

## Provider enrichment
VirusTotal and AlienVault OTX lookups completed for all extracted IPs and hashes. VirusTotal returned malicious detections for every listed IP and all six queried file-hash values; OTX returned pulse counts for every queried value. AbuseIPDB requests returned HTTP 401, so no AbuseIPDB score is claimed. Provider results are time-sensitive and should not be treated as proof of current maliciousness.

## Limitations
The deterministic parser labels some executable names and code tokens as domain-like values; these are retained for traceability but should not be blocklisted without analyst review. The report’s indicators are historical public evidence.
