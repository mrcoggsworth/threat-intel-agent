"""Two-tiered (4-step modal summary + multi-phase deep dive) hunt playbook builder."""

from __future__ import annotations

from typing import Any

from hermes_cti.playbooks.rule_generator import DetectionRuleBundle


def _extract_primary_ioc_summary(iocs: dict[str, list[str]]) -> list[str]:
    """Collect flat list of key indicators for fast inspection."""
    res: list[str] = []
    for key in ("cves", "sha256", "domains", "ipv4", "urls"):
        if key in iocs and iocs[key]:
            res.extend([str(item) for item in iocs[key][:3]])
    return res[:10]


def generate_hunt_playbook(
    threat_title: str,
    summary: str,
    techniques: list[str],
    iocs: dict[str, list[str]],
    detection_bundle: DetectionRuleBundle,
) -> dict[str, Any]:
    """Generate two-tiered hunt playbook structure with modal and deep-dive."""
    tech_str = ", ".join(techniques) if techniques else "Unclassified TTPs"
    primary_iocs = _extract_primary_ioc_summary(iocs)
    ioc_context = f" (Focus: {', '.join(primary_iocs)})" if primary_iocs else ""

    summary_playbook = {
        "step_1": {
            "title": "Threat Scoping & Telemetry Check",
            "description": (
                f"Identify target host pools, critical infrastructure, "
                f"and verify ingestion of process creation and authentication "
                f"logs relevant to {threat_title}."
            ),
            "actions": [
                (
                    "Scope target hosts and verify log coverage for "
                    f"techniques: {tech_str}."
                ),
                (
                    "Confirm active endpoint telemetry (Sysmon Event ID 1 / "
                    "Windows Security 4688 / EDR agent status)."
                ),
                (
                    "Check network boundary telemetry for suspect destinations"
                    f"{ioc_context}."
                ),
            ],
            "target_telemetry": [
                "Process Creation (Event ID 4688 / Sysmon 1)",
                "PowerShell ScriptBlock Logs (Event ID 4104)",
                "Network Flow & DNS Queries",
            ],
        },
        "step_2": {
            "title": "SIEM Query Execution",
            "description": (
                "Execute primary hunting queries across available SIEM/EDR "
                "platforms to detect anomalous activity."
            ),
            "splunk_spl": detection_bundle.splunk_spl,
            "defender_kql": detection_bundle.defender_kql,
            "elastic_kql": detection_bundle.elastic_kql,
            "sigma_yaml": detection_bundle.sigma_yaml,
            "recommended_lookback": "30 days",
        },
        "step_3": {
            "title": "Triage & False-Positive Branching",
            "description": (
                "Distinguish legitimate IT administration or scheduled "
                "automation from active adversary activity."
            ),
            "guidance": [
                "Differentiate admin scripts from malicious execution",
                "Examine parent process lineage",
                "Check execution timestamps against maintenance windows",
            ],
            "triage_rules": [
                (
                    "Verify parent-child process relationships (e.g. identify "
                    "if shell was spawned by web server or Office)."
                ),
                (
                    "Filter authorized IT maintenance tools, signed SCCM "
                    "packages, and scheduled tasks."
                ),
                (
                    "Cross-reference user accounts initiating execution against "
                    "expected privileged role rosters."
                ),
            ],
            "false_positive_baselines": [
                (
                    "Standard administrative scripts running under "
                    "domain service accounts."
                ),
                "Approved internal vulnerability scanning or patch management agents.",
            ],
        },
        "step_4": {
            "title": "Immediate Containment & Isolation",
            "description": (
                "Host network isolation, credential invalidation, and "
                "ticket escalation."
            ),
            "actions": [
                "Isolate confirmed compromised endpoints",
                "Revoke active Kerberos tickets and sessions",
                "Block malicious network indicators on perimeter firewalls",
            ],
            "containment_steps": [
                (
                    "Initiate host-level network isolation for confirmed "
                    "affected endpoints."
                ),
                (
                    "Revoke active sessions and reset credentials for "
                    "compromised accounts."
                ),
                (
                    "Deploy YARA signatures and endpoint block rules to "
                    "halt lateral movement."
                ),
                (
                    "Preserve memory dumps and volatile forensic artifacts prior "
                    "to system reboot."
                ),
            ],
            "escalation_path": "Escalate to Tier 3 SOC / DFIR Incident Response Lead.",
        },
    }

    deep_dive_phases = {
        "phase_1": {
            "phase_name": "Baseline & Pre-Hunt Telemetry Audit",
            "description": (
                "Establish telemetry baseline and identify logging blind spots."
            ),
            "operational_steps": [
                (
                    "Verify log pipeline ingestion health and index coverage "
                    "across all targeted endpoint clusters."
                ),
                (
                    "Establish baseline volume for standard system utilities "
                    "to avoid alarm fatigue during sweeps."
                ),
                (
                    "Validate time synchronization across domain controllers, "
                    "SIEM collectors, and endpoint agents."
                ),
            ],
            "telemetry_sources": [
                "Windows Security Event Logs (4688, 4624, 4672)",
                "Sysmon Event Logs (Event IDs 1, 3, 7, 11)",
                "EDR Process Telemetry",
            ],
            "pivot_guidance": [
                (
                    "If telemetry gaps exist in specific subnets, prioritize "
                    "network flow and proxy logs."
                ),
            ],
        },
        "phase_2": {
            "phase_name": "Systematic Sweep & Anomaly Identification",
            "description": (
                "Execute broad hunts across historical logs to find initial indicators."
            ),
            "operational_steps": [
                (
                    "Execute the synthesized Defender KQL and Splunk SPL queries "
                    "across the fleet."
                ),
                (
                    "Aggregate hits by command-line frequency, grouping rare "
                    "parameters for manual triage."
                ),
                (
                    "Inspect child processes spawned by non-standard parent "
                    "trees (e.g., cmd.exe spawned by w3wp.exe)."
                ),
            ],
            "telemetry_sources": [
                "Microsoft Defender DeviceProcessEvents",
                "Splunk main/windows index",
                "Elastic Process Data Streams",
            ],
            "queries": [
                {
                    "platform": "Defender KQL",
                    "query": detection_bundle.defender_kql,
                },
                {
                    "platform": "Splunk SPL",
                    "query": detection_bundle.splunk_spl,
                },
                {
                    "platform": "Elastic KQL",
                    "query": detection_bundle.elastic_kql,
                },
            ],
            "pivot_guidance": [
                (
                    "Pivot from suspicious PID to inspect all network connections "
                    "established within +/- 5 minutes."
                ),
            ],
        },
        "phase_3": {
            "phase_name": "Deep Forensics & Secondary Indicator Extraction",
            "description": (
                "Perform memory, disk, and event log forensics to discover "
                "persistence and lateral movement."
            ),
            "operational_steps": [
                (
                    "Execute memory capture and triage collection (e.g. "
                    "Velociraptor / KAPE) on alerted endpoints."
                ),
                (
                    "Scan target directories and memory space using the "
                    "synthesized YARA rule."
                ),
                (
                    "Analyze ShimCache, Amcache.hve, and Prefetch files "
                    "(C:\\Windows\\Prefetch) for execution evidence."
                ),
                (
                    "Inspect scheduled tasks and Run registry keys "
                    "(HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)."
                ),
            ],
            "telemetry_sources": [
                "Endpoint Filesystem & Memory",
                "Prefetch / ShimCache Artifacts",
                "PowerShell Event Log 4104 (ScriptBlock)",
            ],
            "yara_signature": detection_bundle.yara_rule,
            "pivot_guidance": [
                (
                    "Extract newly discovered payload hashes and submit to "
                    "internal threat intelligence registry."
                ),
            ],
        },
        "phase_4": {
            "phase_name": "Eradication, Hardening & Detection Rule Deployment",
            "description": (
                "Remove malicious artifacts, harden attack surface, and "
                "deploy permanent detection rules."
            ),
            "operational_steps": [
                (
                    "Terminate malicious processes and remove persistence "
                    "registry keys, services, and scheduled tasks."
                ),
                (
                    "Promote the synthesized Sigma YAML rule into production "
                    "SIEM/EDR alert pipelines."
                ),
                (
                    "Implement firewall blocklists for identified external "
                    "C2 IPs and domains."
                ),
                (
                    "Conduct post-incident review and update threat hunt "
                    "baselines with newly observed TTP variations."
                ),
            ],
            "telemetry_sources": [
                "SIEM Alert Pipeline",
                "Firewall & Proxy Block Logs",
                "Endpoint Configuration Management",
            ],
            "production_sigma_rule": detection_bundle.sigma_yaml,
            "pivot_guidance": [
                (
                    "Monitor endpoint for 72 hours post-remediation to confirm "
                    "no secondary beaconing or reinfection occurs."
                ),
            ],
        },
    }

    return {
        "title": threat_title,
        "threat_title": threat_title,
        "summary": summary,
        "techniques": techniques,
        "iocs": iocs,
        "summary_playbook": summary_playbook,
        "deep_dive_phases": deep_dive_phases,
    }


class HuntPlaybookGenerator:
    """Two-tiered hunt playbook builder."""

    @staticmethod
    def generate_hunt_playbook(
        threat_title: str,
        summary: str,
        techniques: list[str],
        iocs: dict[str, list[str]],
        detection_bundle: DetectionRuleBundle,
    ) -> dict[str, Any]:
        return generate_hunt_playbook(
            threat_title=threat_title,
            summary=summary,
            techniques=techniques,
            iocs=iocs,
            detection_bundle=detection_bundle,
        )
