"""Explainable CTI analyst assessment synthesis for enriched indicators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from hermes_cti.models.contracts import EnrichmentRunResult


class IOCRiskLevel(StrEnum):
    """Controlled risk levels for CTI analyst triage."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class IOCVerdict(StrEnum):
    """Clear threat verdict for SOC / CTI decision making."""

    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    BENIGN = "benign"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class IOCAnalystAssessment:
    """Synthesized CTI analyst evaluation and actionable guidance."""

    verdict: IOCVerdict
    risk_level: IOCRiskLevel
    confidence: str
    badge_label: str
    badge_style: str
    summary: str
    observations: tuple[str, ...]
    recommendations: tuple[str, ...]


def _format_threat_class(threat_class_raw: Any) -> tuple[str | None, str | None]:
    """Extract narrative label and observation from threat classification."""
    if not threat_class_raw:
        return None, None
    if isinstance(threat_class_raw, str):
        return (
            threat_class_raw,
            f"Threat Classification: Identified as '{threat_class_raw}'.",
        )
    if isinstance(threat_class_raw, dict):
        label = threat_class_raw.get("suggested_threat_label")
        categories = threat_class_raw.get("popular_threat_category") or []
        names = threat_class_raw.get("popular_threat_name") or []

        cats_summary: list[str] = []
        if isinstance(categories, list):
            for c in categories:
                if isinstance(c, dict) and "value" in c:
                    count = c.get("count")
                    cats_summary.append(
                        f"{c['value']} ({count})" if count else str(c["value"])
                    )
                elif isinstance(c, str):
                    cats_summary.append(c)

        names_summary: list[str] = []
        if isinstance(names, list):
            for n in names:
                if isinstance(n, dict) and "value" in n:
                    count = n.get("count")
                    names_summary.append(
                        f"{n['value']} ({count})" if count else str(n["value"])
                    )
                elif isinstance(n, str):
                    names_summary.append(n)

        narrative_label = (
            label
            or (names_summary[0] if names_summary else None)
            or (cats_summary[0] if cats_summary else None)
        )

        obs_parts: list[str] = []
        if label:
            obs_parts.append(f"Label: '{label}'")
        if cats_summary:
            obs_parts.append(f"Categories: {', '.join(cats_summary[:3])}")
        if names_summary:
            obs_parts.append(f"Names: {', '.join(names_summary[:3])}")

        formatted_obs = (
            f"Threat Classification: {'; '.join(obs_parts)}." if obs_parts else None
        )
        return narrative_label, formatted_obs
    return None, None


def _extract_vt_stats(
    vt_data: dict[str, Any] | None,
) -> tuple[int, int, int, int, list[str], str | None, str | None]:
    if not vt_data or vt_data.get("not_found"):
        return 0, 0, 0, 0, [], None, None
    stats = vt_data.get("last_analysis_stats") or {}
    malicious = int(stats.get("malicious") or 0)
    suspicious = int(stats.get("suspicious") or 0)
    harmless = int(stats.get("harmless") or 0)
    undetected = int(stats.get("undetected") or 0)
    tags = [str(t) for t in (vt_data.get("tags") or []) if isinstance(t, str)]
    threat_label, threat_obs = _format_threat_class(
        vt_data.get("popular_threat_classification")
    )
    return (
        malicious,
        suspicious,
        harmless,
        undetected,
        tags,
        threat_label,
        threat_obs,
    )


def synthesize_ioc_analyst_assessment(
    *,
    ioc_type: str,
    ioc_value: str,
    report_headline: str | None = None,
    run_result: EnrichmentRunResult | None = None,
    vt_data: dict[str, Any] | None = None,
    abuse_data: dict[str, Any] | None = None,
    otx_data: dict[str, Any] | None = None,
) -> IOCAnalystAssessment:
    """Synthesize multi-source CTI enrichment into an analyst assessment."""
    (
        malicious_vt,
        suspicious_vt,
        harmless_vt,
        _undetected_vt,
        vt_tags,
        threat_label,
        threat_obs,
    ) = _extract_vt_stats(vt_data)

    abuse_score = int((abuse_data or {}).get("abuse_confidence_score") or 0)
    abuse_reports = int((abuse_data or {}).get("total_reports") or 0)
    country = (abuse_data or {}).get("country_code")
    usage_type = (abuse_data or {}).get("usage_type")

    pulse_count = int((otx_data or {}).get("pulse_count") or 0)
    raw_pulse_names = (otx_data or {}).get("pulse_names") or []
    pulse_names = [str(p) for p in raw_pulse_names if p]

    has_vt_result = (
        vt_data is not None
        and not vt_data.get("not_found")
        and bool(vt_data.get("last_analysis_stats"))
    )
    has_abuse_result = (
        abuse_data is not None
        and "abuse_confidence_score" in abuse_data
        and abuse_data.get("abuse_confidence_score") is not None
    )
    has_otx_result = (
        otx_data is not None
        and not otx_data.get("not_found")
        and "pulse_count" in otx_data
        and otx_data.get("pulse_count") is not None
    )

    observations: list[str] = []
    recommendations: list[str] = []

    # 1. Determine Verdict and Risk Level
    is_critical_malicious = (
        malicious_vt >= 10
        or (malicious_vt >= 5 and pulse_count >= 2)
        or (abuse_score >= 80 and abuse_reports >= 10)
    )
    is_high_malicious = (
        malicious_vt >= 3 or abuse_score >= 50 or pulse_count >= 3 or bool(threat_label)
    )
    is_suspicious = (
        malicious_vt in (1, 2)
        or suspicious_vt >= 2
        or (1 <= abuse_score < 50)
        or (1 <= pulse_count < 3)
        or len(vt_tags) > 0
    )

    has_active_clean_telemetry = (
        (has_vt_result and harmless_vt > 0 and malicious_vt == 0)
        or (has_abuse_result and abuse_score == 0 and ioc_type in ("ipv4", "ipv6"))
        or (has_otx_result and pulse_count == 0)
    )

    if is_critical_malicious:
        verdict = IOCVerdict.MALICIOUS
        risk_level = IOCRiskLevel.CRITICAL
        badge_label = "Malicious / Critical Risk"
        badge_style = "danger"
    elif is_high_malicious:
        verdict = IOCVerdict.MALICIOUS
        risk_level = IOCRiskLevel.HIGH
        badge_label = "Malicious / High Risk"
        badge_style = "danger"
    elif is_suspicious:
        verdict = IOCVerdict.SUSPICIOUS
        risk_level = IOCRiskLevel.MEDIUM
        badge_label = "Suspicious / Elevated Risk"
        badge_style = "warning"
    elif has_active_clean_telemetry and not is_suspicious:
        verdict = IOCVerdict.BENIGN
        risk_level = IOCRiskLevel.LOW
        badge_label = "Clean / Low Risk"
        badge_style = "success"
    else:
        verdict = IOCVerdict.INCONCLUSIVE
        risk_level = IOCRiskLevel.UNKNOWN
        badge_label = "Inconclusive / Unassessed"
        badge_style = "neutral"

    # 2. Confidence Level
    active_corroborating_sources = sum(
        1 for s in (has_vt_result, has_abuse_result, has_otx_result) if s
    )
    if active_corroborating_sources >= 2 or malicious_vt >= 10 or abuse_score >= 80:
        confidence = "High"
    elif active_corroborating_sources == 1 or suspicious_vt > 0 or harmless_vt > 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    # 3. Formulate Key Observations
    if threat_obs:
        observations.append(threat_obs)
    elif vt_tags:
        tags_str = ", ".join(vt_tags[:5])
        observations.append(
            f"Malware Taxonomy: Associated with activity tags [{tags_str}]."
        )

    if malicious_vt > 0 or suspicious_vt > 0:
        observations.append(
            f"VirusTotal Detections: {malicious_vt} vendors flagged as malicious "
            f"({suspicious_vt} suspicious, {harmless_vt} clean)."
        )

    if abuse_data and ioc_type in ("ipv4", "ipv6"):
        loc = f"in {country}" if country else "unknown origin"
        infra = f" ({usage_type})" if usage_type else ""
        observations.append(
            f"Network Reputation: Abuse confidence score of {abuse_score}% based on "
            f"{abuse_reports} abuse reports from infrastructure {loc}{infra}."
        )

    if pulse_count > 0:
        names_preview = f" ({', '.join(pulse_names[:3])})" if pulse_names else ""
        observations.append(
            f"Threat Correlation: Indexed in {pulse_count} AlienVault OTX "
            f"community pulse(s){names_preview}."
        )

    if report_headline:
        observations.append(
            f"Contextual Evidence: Correlated with advisory '{report_headline}'."
        )

    if not observations:
        if run_result and run_result.status and run_result.status.value == "disabled":
            observations.append(
                "Enrichment feeds are unconfigured. Set provider API keys "
                "for live correlation."
            )
        else:
            observations.append(
                f"No detections or abuse reports indexed for indicator {ioc_value}."
            )

    # 4. Formulate Actionable SOC & CTI Recommendations
    if verdict == IOCVerdict.MALICIOUS:
        recommendations.append(
            f"Containment: Enforce perimeter/DNS/firewall block for '{ioc_value}'."
        )
        recommendations.append(
            f"Telemetry Hunt: Query SIEM/EDR logs for connections or processes "
            f"involving '{ioc_value}' over the past 30–90 days."
        )
        recommendations.append(
            "Host Triage: If active endpoint beaconing is observed, isolate "
            "the impacted host and initiate memory forensics."
        )
        if pulse_names:
            recommendations.append(
                "Campaign Pivot: Cross-reference internal telemetry against "
                f"related campaign pulse(s): {', '.join(pulse_names[:2])}."
            )
    elif verdict == IOCVerdict.SUSPICIOUS:
        recommendations.append(
            f"Watchlist: Add '{ioc_value}' to SOC SIEM watchlist and set up "
            "alerts for internal communication."
        )
        recommendations.append(
            "Log Review: Review firewall and proxy historical logs for "
            "inbound/outbound connection attempts."
        )
        recommendations.append(
            "Dynamic Detonation: Submit payloads or artifacts to an isolated "
            "sandbox for behavioral verification."
        )
    elif verdict == IOCVerdict.BENIGN:
        recommendations.append(
            "Standard Logging: Maintain standard operational monitoring; no automated "
            "blocking action required."
        )
        recommendations.append(
            "Periodic Recheck: If observed in high-severity incidents, re-evaluate "
            "reputation periodically for newly published threat pulses."
        )
    else:
        recommendations.append(
            "Manual Pivot: Query WHOIS, passive DNS, and external threat databases "
            "to gather secondary corroborating telemetry."
        )
        recommendations.append(
            "Provider Setup: Ensure VirusTotal, AbuseIPDB, and OTX API credentials "
            "are configured in system settings for live enrichment."
        )

    # 5. Formulate Synthesized Executive CTI Narrative
    if verdict == IOCVerdict.MALICIOUS:
        summary_parts = [
            f"Indicator '{ioc_value}' is evaluated as a verified MALICIOUS threat "
            f"with {risk_level.value.upper()} operational risk."
        ]
        if malicious_vt > 0:
            summary_parts.append(
                f"VirusTotal indexes {malicious_vt} vendor detections"
                + (f" identified as {threat_label}" if threat_label else "")
                + "."
            )
        if abuse_score > 0:
            summary_parts.append(
                f"AbuseIPDB corroborates high malicious confidence ({abuse_score}%) "
                f"across {abuse_reports} reports."
            )
        if pulse_count > 0:
            summary_parts.append(
                f"AlienVault OTX tracks this in {pulse_count} threat pulse(s)."
            )
        summary_parts.append(
            "Immediate defensive blocking and enterprise-wide retroactive threat "
            "hunting are strongly advised."
        )
        summary = " ".join(summary_parts)
    elif verdict == IOCVerdict.SUSPICIOUS:
        summary_parts = [
            f"Indicator '{ioc_value}' exhibits SUSPICIOUS behavioral signals "
            "and warrants analyst review."
        ]
        if suspicious_vt > 0 or malicious_vt > 0:
            summary_parts.append(
                f"Multi-engine scanning identifies {malicious_vt + suspicious_vt} "
                "suspicious/malicious flag(s)."
            )
        if abuse_score > 0:
            summary_parts.append(
                f"Reputation scoring indicates an abuse confidence of {abuse_score}%."
            )
        if pulse_count > 0:
            summary_parts.append(
                f"Correlated with {pulse_count} community threat pulse(s)."
            )
        summary_parts.append(
            "SOC teams should apply monitoring watchlists and inspect endpoint logs "
            "for prior touchpoints."
        )
        summary = " ".join(summary_parts)
    elif verdict == IOCVerdict.BENIGN:
        summary = (
            f"Indicator '{ioc_value}' shows no malicious indicators across active "
            "CTI feeds (0 detections, 0 abuse reports, 0 threat pulses). "
            "It presents LOW operational risk to the environment."
        )
    else:
        summary = (
            f"Indicator '{ioc_value}' has inconclusive threat telemetry from active "
            "enrichment feeds. Analysts should perform manual pivots or configure "
            "API keys for deeper automated intelligence."
        )

    return IOCAnalystAssessment(
        verdict=verdict,
        risk_level=risk_level,
        confidence=confidence,
        badge_label=badge_label,
        badge_style=badge_style,
        summary=summary,
        observations=tuple(observations),
        recommendations=tuple(recommendations),
    )
