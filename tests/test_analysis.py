from hermes_cti.analysis.cve_analyzer import (
    categorize_cvss_score,
    evaluate_epss_priority,
    extract_cves,
)
from hermes_cti.analysis.ioc_extractor import IOCExtractor, extract_iocs, refang_text
from hermes_cti.analysis.mitre_mapper import (
    MitreMapper,
    extract_mitre_techniques,
    generate_navigator_layer,
)


def test_deterministic_ioc_extraction():
    text = """
    Malicious IPs observed: 8.8.8.8 and 2607:f8b0:4005:8090:0000:0000:0000:200e.
    Hashes:
    MD5: 5d41402abc4b2a76b9719d911017c592
    SHA1: aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d
    SHA256: 2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae
    C2 Domain: badguy.com
    URL: http://badguy.com/payload.exe
    """
    iocs = extract_iocs(text)
    assert "8.8.8.8" in iocs.ipv4
    assert "2607:f8b0:4005:8090:0000:0000:0000:200e" in iocs.ipv6
    assert "5d41402abc4b2a76b9719d911017c592" in iocs.md5
    assert "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d" in iocs.sha1
    assert (
        "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
        in iocs.sha256
    )
    assert "badguy.com" in iocs.domains
    assert "http://badguy.com/payload.exe" in iocs.urls


def test_defanging_and_refanging():
    text = (
        "hxxps://badguy[.]com/payload hxxps[:]//secure(.)com "
        "hxxp://test(.)com user[@]badguy{.}com http[:/][/]test.com"
    )
    refanged = refang_text(text)
    assert "https://badguy.com/payload" in refanged
    assert "https://secure.com" in refanged
    assert "http://test.com" in refanged
    assert "user@badguy.com" in refanged
    assert "http://test.com" in refanged

    # Test through extractor
    iocs = extract_iocs("hxxps://malicious[.]com/file.exe")
    assert "malicious.com" in iocs.domains
    assert "https://malicious.com/file.exe" in iocs.urls

    iocs = extract_iocs("CVE-2024-1234 and cve-2024-1234")
    assert iocs.cves == ["CVE-2024-1234"]
    assert IOCExtractor.extract_iocs("203.0.113.4/32", False).cidrs == [
        "203.0.113.4/32"
    ]


def test_private_ip_and_example_domain_filtering():
    text = (
        "Internal IP 192.168.1.1 communicated with 10.0.0.1 and "
        "loopback 127.0.0.1. See example.com for details. Also 8.8.8.8."
    )
    iocs = extract_iocs(text, filter_private_ips=True, filter_example_domains=True)
    assert "192.168.1.1" not in iocs.ipv4
    assert "10.0.0.1" not in iocs.ipv4
    assert "127.0.0.1" not in iocs.ipv4
    assert "8.8.8.8" in iocs.ipv4
    assert "example.com" not in iocs.domains

    # Test without filtering
    iocs_unfiltered = extract_iocs(
        text, filter_private_ips=False, filter_example_domains=False
    )
    assert "192.168.1.1" in iocs_unfiltered.ipv4
    assert "10.0.0.1" in iocs_unfiltered.ipv4
    assert "127.0.0.1" in iocs_unfiltered.ipv4
    assert "example.com" in iocs_unfiltered.domains


def test_cve_extraction_and_scoring():
    text = "Exploiting CVE-2021-44228 and cve-2023-12345 in the wild."
    cves = extract_cves(text)
    assert "CVE-2021-44228" in cves
    assert "CVE-2023-12345" in cves

    assert categorize_cvss_score(9.8) == "CRITICAL"
    assert categorize_cvss_score(7.5) == "HIGH"
    assert categorize_cvss_score(5.0) == "MEDIUM"
    assert categorize_cvss_score(2.0) == "LOW"
    assert categorize_cvss_score(0.0) == "NONE"

    assert evaluate_epss_priority(0.60) == "URGENT"
    assert evaluate_epss_priority(0.10, is_kev=True) == "URGENT"
    assert evaluate_epss_priority(0.20) == "HIGH"
    assert evaluate_epss_priority(0.06) == "ELEVATED"
    assert evaluate_epss_priority(0.01) == "STANDARD"


def test_composite_risk_score_is_normalized():
    from hermes_cti.analysis.cve_analyzer import compute_composite_risk_score

    assert compute_composite_risk_score(None, None, False) == 0.0
    assert compute_composite_risk_score(9.8, 0.9, False) == 10.0
    assert compute_composite_risk_score(-1.0, 2.0, False) == 2.0
    assert compute_composite_risk_score(1.0, 0.2, True) == 10.0


def test_mitre_attack_mapping():
    text = (
        "The attacker used PowerShell and Mimikatz to dump "
        "credentials before deploying ransomware."
    )
    techniques = extract_mitre_techniques(text)
    tech_ids = [t["technique_id"] for t in techniques]
    assert "T1059.001" in tech_ids  # PowerShell
    assert "T1003" in tech_ids  # OS Credential Dumping
    assert "T1486" in tech_ids  # Data Encrypted for Impact


def test_attack_navigator_layer_json_schema():
    techniques = [
        {
            "tactic": "Execution",
            "technique_id": "T1059.001",
            "technique_name": "PowerShell",
            "matched_phrases": ["powershell"],
        }
    ]
    layer = generate_navigator_layer(techniques)
    assert layer["name"] == "Hermes CTI Campaign Layer"
    assert layer["versions"]["layer"] == "4.5"
    assert layer["domain"] == "enterprise-attack"
    assert len(layer["techniques"]) == 1
    assert layer["techniques"][0]["techniqueID"] == "T1059.001"
    assert layer["techniques"][0]["tactic"] == "execution"
    assert MitreMapper.generate_navigator_layer(techniques) == layer
