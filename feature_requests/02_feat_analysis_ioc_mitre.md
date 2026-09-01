# Worktree 2 Implementation Plan: Deterministic IOC Extraction & MITRE ATT&CK Engine

## Branch & Worktree Configuration
- **Branch Name:** `feat/analysis-ioc-mitre`
- **Worktree Directory:** `../threat-intel-agent-wt2`
- **Integration Merge Target:** `main` (Merge Phase 2, depends on Phase 1 models)
- **Authoritative Skill Context:** `.hermes/skills/ioc-parser/SKILL.md` & `.hermes/skills/cti-analysis/SKILL.md`

---

## 1. Scope & Responsibilities

Worktree 2 implements the core analytical engine for Hermes CTI:
1. **Deterministic IOC Extraction & Refanging:** Parsing raw, unstructured threat write-ups to extract and refang indicators (IPv4, IPv6, CIDR, MD5, SHA1, SHA256, domains, URLs) with zero hallucinations.
2. **RFC1918 & False Positive Filtering:** Suppressing documentation domains (`example.com`), private RFC1918 subnets, and loopback addresses unless explicitly allowed.
3. **CVE & Exploitability Analysis:** Extracting CVE IDs, assessing CVSS 2.0/3.0/3.1 severity metrics, evaluating EPSS threshold probabilities, and calculating threat priority.
4. **MITRE ATT&CK Mapping & Navigator Layer Export:** Tagging extracted TTPs with ATT&CK enterprise tactics and techniques, and generating standards-compliant ATT&CK Navigator Layer JSON files.

---

## 2. File Ownership & Structural Layout

```text
src/
├── hermes/
│   └── analysis/
│       ├── __init__.py
│       ├── ioc_extractor.py    # Regex engine, refanging, IoC deduplication & validation
│       ├── cve_analyzer.py     # CVE extraction, CVSS severity bands & EPSS thresholds
│       └── mitre_mapper.py     # Enterprise ATT&CK mapping & Navigator v4.5 Layer JSON export
tests/
└── test_analysis.py            # Unit tests for extraction, refanging, CVE analysis, and ATT&CK
```

---

## 3. Step-by-Step Implementation Details

### Step 3.1: Worktree Initialization
```bash
git worktree add ../threat-intel-agent-wt2 -b feat/analysis-ioc-mitre
cd ../threat-intel-agent-wt2
```

### Step 3.2: Module `src/hermes/analysis/ioc_extractor.py`
Implement `IOCExtractor`:
- **Defanging / Refanging Logic:**
  - Standardizes defanged patterns: `hxxp://` $\rightarrow$ `http://`, `hxxps://` $\rightarrow$ `https://`, `[.]` / `(.)` / `[\.]` / `{.} ` $\rightarrow$ `.`, `[@]` $\rightarrow$ `@`, `[:/]` $\rightarrow$ `:/`.
- **Regex Patterns:**
  - `IPV4_REGEX = r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"`
  - `IPV6_REGEX = r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"`
  - `MD5_REGEX = r"\b[a-fA-F0-9]{32}\b"`
  - `SHA1_REGEX = r"\b[a-fA-F0-9]{40}\b"`
  - `SHA256_REGEX = r"\b[a-fA-F0-9]{64}\b"`
  - `DOMAIN_REGEX = r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"`
  - `URL_REGEX = r"https?://[^\s<>\"'{}|\\^`\[\]]+"`
- **Data Models:**
  ```python
  from dataclasses import dataclass, field


  @dataclass
  class ExtractedIOCs:
      ipv4: list[str] = field(default_factory=list)
      ipv6: list[str] = field(default_factory=list)
      md5: list[str] = field(default_factory=list)
      sha1: list[str] = field(default_factory=list)
      sha256: list[str] = field(default_factory=list)
      domains: list[str] = field(default_factory=list)
      urls: list[str] = field(default_factory=list)
      cves: list[str] = field(default_factory=list)

      def to_dict(self) -> dict[str, list[str]]: ...
      def count(self) -> int: ...
  ```
- **Functionality:**
  - `def refang_text(text: str) -> str`
  - `def extract_iocs(text: str, filter_private_ips: bool = True, filter_example_domains: bool = True) -> ExtractedIOCs`
  - `def is_private_or_reserved_ip(ip_str: str) -> bool`: Checks RFC1918, loopback (`127.0.0.0/8`), APIPA (`169.254.0.0/16`), and multicast.

### Step 3.3: Module `src/hermes/analysis/cve_analyzer.py`
Implement `CVEAnalyzer`:
- **Functionality:**
  - `CVE_PATTERN = r"\bCVE-\d{4}-\d{4,7}\b"`
  - `def extract_cves(text: str) -> list[str]`: Extracts unique canonical CVE IDs.
  - `def categorize_cvss_score(score: float) -> str`: Returns `"CRITICAL"` ($\ge 9.0$), `"HIGH"` ($7.0 - 8.9$), `"MEDIUM"` ($4.0 - 6.9$), `"LOW"` ($0.1 - 3.9$), or `"NONE"`.
  - `def evaluate_epss_priority(epss_score: float, is_kev: bool = False) -> str`:
    - Returns `"URGENT"` if in CISA KEV or EPSS $\ge 0.50$.
    - Returns `"HIGH"` if EPSS $\ge 0.15$.
    - Returns `"ELEVATED"` if EPSS $\ge 0.05$.
    - Returns `"STANDARD"` otherwise.
  - `def compute_composite_risk_score(cvss: float | None, epss: float | None, is_kev: bool) -> float`: Calculates normalized $0.0 - 10.0$ risk rating.

### Step 3.4: Module `src/hermes/analysis/mitre_mapper.py`
Implement `MitreMapper`:
- **TTP Knowledge Base & Mapping:**
  - Maps keywords, tool names, and commands to MITRE ATT&CK Enterprise tactics and techniques:
    - `T1059.001` (PowerShell), `T1059.003` (Windows Command Shell), `T1059.004` (Unix Shell), `T1566.001` (Spearphishing Attachment), `T1190` (Exploit Public-Facing Application), `T1071.001` (Web Protocols), `T1003` (OS Credential Dumping), `T1486` (Data Encrypted for Impact / Ransomware).
- **Functions:**
  - `def extract_mitre_techniques(text: str) -> list[dict[str, str]]`: Returns tagged techniques with `tactic`, `technique_id`, `technique_name`, and matched phrases.
  - `def generate_navigator_layer(techniques: list[dict[str, Any]], layer_name: str = "Hermes CTI Campaign Layer") -> dict[str, Any]`:
    - Returns JSON structure conforming to MITRE ATT&CK Navigator v4.5 schema.
    - Fields: `name`, `versions: {"attack": "15", "navigator": "4.5", "layer": "4.5"}`, `domain: "enterprise-attack"`, `description`, `techniques: [{"techniqueID": ..., "tactic": ..., "score": ..., "color": ..., "comment": ..., "enabled": true}]`.

---

## 4. Test Suite Requirements

### `tests/test_analysis.py`
- `test_deterministic_ioc_extraction`: Verify extraction of IPv4, IPv6, MD5, SHA256, domains, and URLs from raw text write-ups.
- `test_defanging_and_refanging`: Verify refanging of `hxxps://`, `[.]`, `(.)`, `[@]`, and `{.} ` strings into valid indicators.
- `test_private_ip_and_example_domain_filtering`: Ensure `192.168.1.1`, `10.0.0.1`, `127.0.0.1`, and `example.com` are filtered when requested.
- `test_cve_extraction_and_scoring`: Test CVE identification, CVSS categorization, and EPSS priority assignment.
- `test_mitre_attack_mapping`: Verify keyword and pattern matching to MITRE ATT&CK technique IDs and tactics.
- `test_attack_navigator_layer_json_schema`: Verify generated Navigator JSON conforms to MITRE ATT&CK Navigator schema specifications.

---

## 5. Verification Commands

Run within `../threat-intel-agent-wt2`:
```bash
# Run analysis test suite
uv run pytest tests/test_analysis.py -v

# Code formatting and linting
uv run ruff check src/hermes/analysis tests/test_analysis.py
uv run ruff format --check src/hermes/analysis tests/test_analysis.py
```

---

## 6. Commit & Merge Instructions

1. Commit in worktree 2:
   ```bash
   git add src/hermes/analysis tests/test_analysis.py
   git commit -m "feat(analysis): implement deterministic IOC extractor, CVE analyzer, and MITRE ATT&CK navigator exporter"
   ```
2. In main repository workspace:
   ```bash
   git merge feat/analysis-ioc-mitre --no-ff -m "Merge branch 'feat/analysis-ioc-mitre' (Phase 2)"
   ```
