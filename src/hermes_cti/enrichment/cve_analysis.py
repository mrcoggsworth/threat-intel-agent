"""Explainable CTI analyst assessment synthesis for enriched CVEs.

Provides dual-perspective analysis:
1. Tech Lead Manager (TLM) strategic briefing for engineering leaders.
2. Deep technical mechanics and root-cause breakdown for security engineers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hermes_cti.models.contracts import EnrichmentRunResult
from hermes_cti.reporting.contracts import ReportVulnerability


class CVERiskLevel(StrEnum):
    """Controlled risk levels for CVE triage and prioritization."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CVEVerdict(StrEnum):
    """Clear threat verdict for operational decision making."""

    CRITICAL_EXPLOITED = "critical_exploited"
    HIGH_EXPLOIT_RISK = "high_exploit_risk"
    ELEVATED_EXPOSURE = "elevated_exposure"
    MODERATE_RISK = "moderate_risk"
    LOW_RISK = "low_risk"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class CVEAnalystAssessment:
    """Synthesized CTI analyst evaluation with dual TLM and technical breakdowns."""

    cve_id: str
    verdict: CVEVerdict
    risk_level: CVERiskLevel
    confidence: str
    badge_label: str
    badge_style: str
    executive_summary: str
    tlm_briefing: str
    technical_analysis: str
    key_findings: tuple[str, ...]
    recommendations: tuple[str, ...]
    cvss_score: float | None
    cvss_version: str | None
    cvss_vector: str | None
    epss_score: float | None
    epss_percentile: float | None
    cwe_ids: tuple[str, ...]
    cwe_descriptions: tuple[str, ...]
    known_exploited: bool
    kev_date_added: str | None
    kev_due_date: str | None
    kev_required_action: str | None
    affected_products: tuple[str, ...]


CWE_TITLES: dict[str, str] = {
    "CWE-20": "Improper Input Validation",
    "CWE-22": "Improper Limitation of a Pathname ('Path Traversal')",
    "CWE-78": "Improper Neutralization of Special Elements ('OS Command Injection')",
    "CWE-79": "Improper Neutralization of Input ('Cross-site Scripting')",
    "CWE-89": "Improper Neutralization of Special Elements ('SQL Injection')",
    "CWE-94": "Improper Control of Generation of Code ('Code Injection')",
    "CWE-119": "Improper Restriction of Memory Operations",
    "CWE-120": "Buffer Copy without Checking Size of Input ('Classic Buffer Overflow')",
    "CWE-125": "Out-of-bounds Read",
    "CWE-190": "Integer Overflow or Wraparound",
    "CWE-200": "Exposure of Sensitive Information to an Unauthorized Actor",
    "CWE-269": "Improper Privilege Management",
    "CWE-287": "Improper Authentication",
    "CWE-295": "Improper Certificate Validation",
    "CWE-352": "Cross-Site Request Forgery (CSRF)",
    "CWE-362": "Concurrent Execution with Improper Synchronization ('Race Condition')",
    "CWE-416": "Use After Free",
    "CWE-434": "Unrestricted Upload of File with Dangerous Type",
    "CWE-502": "Deserialization of Untrusted Data",
    "CWE-611": "Improper Restriction of XML External Entity Reference ('XXE')",
    "CWE-787": "Out-of-bounds Write",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-862": "Missing Authorization",
    "CWE-863": "Incorrect Authorization",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
}


def _cwe_label(cwe_id: str) -> str:
    title = CWE_TITLES.get(cwe_id.strip().upper())
    if title:
        return f"{cwe_id}: {title}"
    return cwe_id


def synthesize_cve_analyst_assessment(
    cve_id: str,
    *,
    report_headline: str | None = None,
    run_result: EnrichmentRunResult | None = None,
    report_vulnerability: ReportVulnerability | None = None,
    kev_data: dict[str, Any] | None = None,
    epss_data: dict[str, Any] | None = None,
    nvd_data: dict[str, Any] | None = None,
) -> CVEAnalystAssessment:
    """Synthesize a dual-perspective CTI analyst evaluation for a CVE."""
    clean_cve = cve_id.strip().upper()

    # Extract provider records if available from run_result
    if run_result:
        for pr in run_result.provider_results:
            if pr.provider == "cisa_kev" and pr.normalized_result and not kev_data:
                kev_data = pr.normalized_result
            elif pr.provider == "epss" and pr.normalized_result and not epss_data:
                epss_data = pr.normalized_result
            elif pr.provider == "nvd" and pr.normalized_result and not nvd_data:
                nvd_data = pr.normalized_result

    # Merge metrics across providers and report data
    cvss_score: float | None = None
    cvss_version: str | None = None
    cvss_vector: str | None = None
    epss_score: float | None = None
    epss_percentile: float | None = None
    cwe_ids_list: list[str] = []
    known_exploited = False
    kev_date_added: str | None = None
    kev_due_date: str | None = None
    kev_required_action: str | None = None
    description = ""
    affected_products_list: list[str] = []

    if report_vulnerability:
        cvss_score = report_vulnerability.cvss_score
        cvss_version = report_vulnerability.cvss_version
        cvss_vector = report_vulnerability.cvss_vector
        epss_score = report_vulnerability.epss_score
        epss_percentile = report_vulnerability.epss_percentile
        cwe_ids_list.extend(report_vulnerability.cwe_ids)
        if report_vulnerability.known_exploited:
            known_exploited = True
        if report_vulnerability.kev_date_added:
            kev_date_added = str(report_vulnerability.kev_date_added)
        if report_vulnerability.kev_due_date:
            kev_due_date = str(report_vulnerability.kev_due_date)
        if report_vulnerability.kev_required_action:
            kev_required_action = report_vulnerability.kev_required_action
        if report_vulnerability.summary:
            description = report_vulnerability.summary
        for ap in report_vulnerability.affected_products:
            prod_str = f"{ap.product.vendor} {ap.product.product}"
            if ap.version_range:
                prod_str += f" ({ap.version_range})"
            affected_products_list.append(prod_str)

    if nvd_data:
        if cvss_score is None and nvd_data.get("cvss_score") is not None:
            cvss_score = float(nvd_data["cvss_score"])
        if cvss_version is None and nvd_data.get("cvss_version"):
            cvss_version = str(nvd_data["cvss_version"])
        if cvss_vector is None and nvd_data.get("cvss_vector"):
            cvss_vector = str(nvd_data["cvss_vector"])
        if not description and nvd_data.get("description"):
            description = str(nvd_data["description"])
        for cid in nvd_data.get("cwe_ids", []):
            if cid not in cwe_ids_list:
                cwe_ids_list.append(cid)
        if nvd_data.get("has_cisa_kev_flag"):
            known_exploited = True

    if epss_data:
        if epss_score is None and epss_data.get("epss") is not None:
            epss_score = float(epss_data["epss"])
        if epss_percentile is None and epss_data.get("percentile") is not None:
            epss_percentile = float(epss_data["percentile"])

    if kev_data and kev_data.get("found"):
        known_exploited = True
        if not kev_date_added and kev_data.get("date_added"):
            kev_date_added = str(kev_data["date_added"])
        if not kev_due_date and kev_data.get("due_date"):
            kev_due_date = str(kev_data["due_date"])
        if not kev_required_action and kev_data.get("required_action"):
            kev_required_action = str(kev_data["required_action"])
        if not description and kev_data.get("notes"):
            description = str(kev_data["notes"])

    if not description:
        description = (
            f"Vulnerability intelligence record for {clean_cve}. "
            "Telemetry indexed across public authoritative feeds."
        )

    # Determine Verdict, Risk Level, and Badges
    if known_exploited:
        verdict = CVEVerdict.CRITICAL_EXPLOITED
        risk_level = CVERiskLevel.CRITICAL
        badge_label = "Active In-The-Wild Exploitation"
        badge_style = "danger"
    elif (cvss_score is not None and cvss_score >= 9.0) or (
        epss_score is not None and epss_score >= 0.50
    ):
        verdict = CVEVerdict.HIGH_EXPLOIT_RISK
        risk_level = CVERiskLevel.CRITICAL
        badge_label = "Critical / High Exploit Probability"
        badge_style = "danger"
    elif (cvss_score is not None and cvss_score >= 7.0) or (
        epss_score is not None and epss_score >= 0.20
    ):
        verdict = CVEVerdict.ELEVATED_EXPOSURE
        risk_level = CVERiskLevel.HIGH
        badge_label = "High Severity Exposure"
        badge_style = "warning"
    elif cvss_score is not None and cvss_score >= 4.0:
        verdict = CVEVerdict.MODERATE_RISK
        risk_level = CVERiskLevel.MEDIUM
        badge_label = "Moderate Severity"
        badge_style = "warning"
    elif cvss_score is not None:
        verdict = CVEVerdict.LOW_RISK
        risk_level = CVERiskLevel.LOW
        badge_label = "Low Severity"
        badge_style = "success"
    else:
        verdict = CVEVerdict.INCONCLUSIVE
        risk_level = CVERiskLevel.UNKNOWN
        badge_label = "Telemetry Pending"
        badge_style = "slate"

    # Confidence calculation
    sources_count = sum(
        1 for d in (nvd_data, epss_data, kev_data, report_vulnerability) if d
    )
    if sources_count >= 3:
        confidence = "High (Multi-Source Verified)"
    elif sources_count >= 2:
        confidence = "Medium (Corroborated)"
    else:
        confidence = "Moderate (Single Provider)"

    cwe_descriptions = tuple(_cwe_label(cid) for cid in cwe_ids_list)

    # 1. Tech Lead Manager (TLM) Strategic Briefing Narrative
    tlm_parts: list[str] = []
    if known_exploited:
        tlm_parts.append(
            f"URGENT OPERATIONAL PRIORITY: {clean_cve} is listed in the CISA "
            "Known Exploited Vulnerabilities (KEV) catalog. Active weaponization "
            "has been observed in real-world adversary campaigns. Engineering "
            "leads must prioritize immediate out-of-band patching or enforce "
            "compensating architectural mitigations across all affected systems."
        )
    elif cvss_score and cvss_score >= 9.0:
        tlm_parts.append(
            f"HIGH OPERATIONAL RISK: {clean_cve} carries a Critical CVSS base "
            f"score of {cvss_score:.1f}. While in-the-wild exploitation may not "
            "yet be confirmed in KEV, the architectural impact allows "
            "unauthenticated execution or total privilege compromise. Teams "
            "should schedule expedited remediation in the current sprint cycle."
        )
    elif cvss_score and cvss_score >= 7.0:
        tlm_parts.append(
            f"ELEVATED EXPOSURE: {clean_cve} represents a High severity "
            f"vulnerability (CVSS {cvss_score:.1f}). Engineering managers should "
            "evaluate perimeter exposure, verify whether affected components "
            "are exposed to untrusted ingress, and schedule remediation during "
            "the next standard maintenance release."
        )
    else:
        tlm_parts.append(
            f"CONTROLLED RISK: {clean_cve} has moderate to low direct "
            "exploitability. Ensure regular dependency updates and monitor "
            "perimeter telemetry."
        )

    # TLM blast radius & engineering guidance
    if epss_percentile is not None:
        pct_rank = epss_percentile * 100
        prob_pct = (epss_score or 0) * 100
        tlm_parts.append(
            f"Statistical Exploit Likelihood (EPSS): Ranked in "
            f"the {pct_rank:.1f}th percentile globally (30-day "
            f"weaponization probability: {prob_pct:.1f}%)."
        )
    if kev_due_date:
        tlm_parts.append(f"Federal Compliance Due Date: {kev_due_date}.")
    if kev_required_action:
        tlm_parts.append(f"Mandated Action: {kev_required_action}.")

    tlm_briefing = " ".join(tlm_parts)

    # 2. Deep Technical Breakdown Narrative
    tech_parts: list[str] = []
    tech_parts.append(f"Vulnerability Analysis for {clean_cve}: {description}")
    if cwe_ids_list:
        cwe_joined = ", ".join(cwe_descriptions)
        tech_parts.append(
            f"Root-Cause Flaw Classification: Identified under {cwe_joined}. "
            "This flaw typically manifests when software fails to properly "
            "constrain inputs, validate boundaries, or manage memory lifetimes."
        )
    if cvss_vector:
        tech_parts.append(f"CVSS Metric Vector: {cvss_vector}.")
    if affected_products_list:
        tech_parts.append(
            f"Identified Attack Surface: {', '.join(affected_products_list)}."
        )

    technical_analysis = " ".join(tech_parts)

    # Executive Summary Narrative
    exec_summary = (
        f"{clean_cve} is a {risk_level.value.upper()} risk security flaw. "
        + (
            f"With a CVSS score of {cvss_score:.1f}, "
            if cvss_score
            else "With active threat monitoring, "
        )
        + (
            "it is actively exploited in the wild."
            if known_exploited
            else "it presents potential exposure requiring defensive validation."
        )
    )

    # Key Analytical Findings
    findings: list[str] = []
    if known_exploited:
        findings.append(
            "CISA KEV Catalog: Actively exploited by threat actors in "
            "observed intrusions."
        )
    else:
        findings.append("CISA KEV Catalog: No active in-the-wild exploitation entry.")

    if cvss_score is not None:
        findings.append(
            f"CVSS Base Severity: {cvss_score:.1f} ({cvss_version or 'v3.1'}) "
            f"— Vector: {cvss_vector or 'N/A'}"
        )
    if epss_score is not None:
        findings.append(
            f"EPSS Threat Probability: {epss_score * 100:.2f}% "
            f"({(epss_percentile or 0) * 100:.1f}th percentile globally)"
        )
    if cwe_descriptions:
        findings.append(f"CWE Root Cause: {'; '.join(cwe_descriptions)}")
    if affected_products_list:
        findings.append(f"Affected Inventory: {', '.join(affected_products_list[:4])}")

    # Recommendations
    recs: list[str] = []
    if known_exploited or (cvss_score and cvss_score >= 9.0):
        recs.append(
            "Emergency Remediation: Apply vendor security updates immediately "
            "across all public-facing and internal assets."
        )
        recs.append(
            "Telemetry & Threat Sweep: Execute detection queries (KQL/SPL/Sigma) "
            "across EDR and firewall logs for exploitation artifacts."
        )
        recs.append(
            "Perimeter Isolation: If patching cannot occur immediately, isolate "
            "affected services or apply WAF virtual patching rules."
        )
    elif cvss_score and cvss_score >= 7.0:
        recs.append(
            "Prioritized Patching: Schedule patch deployment during the next "
            "maintenance window or sprint release."
        )
        recs.append(
            "Exposure Assessment: Audit network segmentation to ensure "
            "vulnerable endpoints are restricted from untrusted ingress."
        )
    else:
        recs.append(
            "Standard Maintenance: Update affected libraries and software "
            "packages during standard lifecycle cycles."
        )
        recs.append(
            "Continuous Monitoring: Monitor threat intelligence feeds for "
            "proof-of-concept exploits or weaponization."
        )

    return CVEAnalystAssessment(
        cve_id=clean_cve,
        verdict=verdict,
        risk_level=risk_level,
        confidence=confidence,
        badge_label=badge_label,
        badge_style=badge_style,
        executive_summary=exec_summary,
        tlm_briefing=tlm_briefing,
        technical_analysis=technical_analysis,
        key_findings=tuple(findings),
        recommendations=tuple(recs),
        cvss_score=cvss_score,
        cvss_version=cvss_version,
        cvss_vector=cvss_vector,
        epss_score=epss_score,
        epss_percentile=epss_percentile,
        cwe_ids=tuple(cwe_ids_list),
        cwe_descriptions=cwe_descriptions,
        known_exploited=known_exploited,
        kev_date_added=kev_date_added,
        kev_due_date=kev_due_date,
        kev_required_action=kev_required_action,
        affected_products=tuple(affected_products_list),
    )
