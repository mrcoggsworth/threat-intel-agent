from __future__ import annotations

import re

CVE_PATTERN = r"\bCVE-\d{4}-\d{4,7}\b"


class CVEAnalyzer:
    """Deterministic CVE extraction and exploitability scoring helpers."""

    @staticmethod
    def extract_cves(text: str) -> list[str]:
        return extract_cves(text)

    @staticmethod
    def categorize_cvss_score(score: float) -> str:
        return categorize_cvss_score(score)

    @staticmethod
    def evaluate_epss_priority(epss_score: float, is_kev: bool = False) -> str:
        return evaluate_epss_priority(epss_score, is_kev)

    @staticmethod
    def compute_composite_risk_score(
        cvss: float | None, epss: float | None, is_kev: bool
    ) -> float:
        return compute_composite_risk_score(cvss, epss, is_kev)


def extract_cves(text: str) -> list[str]:
    cves = re.findall(CVE_PATTERN, text, re.IGNORECASE)
    # Canonicalize to uppercase
    return sorted({cve.upper() for cve in cves})


def categorize_cvss_score(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    elif score >= 7.0:
        return "HIGH"
    elif score >= 4.0:
        return "MEDIUM"
    elif score >= 0.1:
        return "LOW"
    return "NONE"


def evaluate_epss_priority(epss_score: float, is_kev: bool = False) -> str:
    if is_kev or epss_score >= 0.50:
        return "URGENT"
    elif epss_score >= 0.15:
        return "HIGH"
    elif epss_score >= 0.05:
        return "ELEVATED"
    return "STANDARD"


def compute_composite_risk_score(
    cvss: float | None, epss: float | None, is_kev: bool
) -> float:
    if is_kev:
        return 10.0

    score = min(10.0, max(0.0, cvss or 0.0))
    if epss is not None:
        score = min(10.0, max(0.0, score + min(1.0, max(0.0, epss)) * 2.0))

    return round(score, 1)
