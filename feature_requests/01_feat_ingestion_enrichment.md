# Worktree 1 Implementation Plan: Ingestion & OSINT Enrichment Engine

## Branch & Worktree Configuration
- **Branch Name:** `feat/ingestion-enrichment`
- **Worktree Directory:** `../threat-intel-agent-wt1`
- **Integration Merge Target:** `main` (Merge Phase 1)
- **Authoritative Registry:** `config/sources.json`

---

## 1. Scope & Responsibilities

Worktree 1 is responsible for the complete data acquisition and external telemetry enrichment layer of Hermes CTI:
1. **Async RSS & Atom Feed Parsing:** Ingesting 37+ feeds across CERT advisories, vendor research, and news feeds, handling GUID deduplication, XML namespace parsing, and timestamp normalization.
2. **HTML & PDF Article Scraping:** Extracting readable article content from advisory and blog URLs while stripping navigation headers, footers, scripts, and styling.
3. **OSINT Telemetry Enrichment:** Providing high-performance async lookups against CISA KEV, FIRST EPSS API, AbuseIPDB, and VirusTotal with rate limiting, in-memory caching, and exponential backoff.
4. **Isolated Test Suite:** Mocked transport tests for all network clients verifying parser accuracy, edge cases, rate limiting, and failure modes.

---

## 2. File Ownership & Structural Layout

```text
src/
├── hermes/
│   ├── __init__.py
│   └── ingestion/
│       ├── __init__.py
│       ├── rss_parser.py       # Async RSS 2.0 / Atom feed parser & GUID deduplicator
│       ├── web_scraper.py      # HTML/PDF article extraction and boilerplate stripper
│       └── enrichment.py       # CISA KEV, FIRST EPSS, AbuseIPDB, and VirusTotal clients
tests/
├── test_ingestion.py           # Unit tests for RSS, Atom, and Web Scraper
└── test_enrichment.py          # Unit tests for KEV, EPSS, AbuseIPDB, and VirusTotal
```

---

## 3. Step-by-Step Implementation Details

### Step 3.1: Worktree Initialization
```bash
git worktree add ../threat-intel-agent-wt1 -b feat/ingestion-enrichment
cd ../threat-intel-agent-wt1
```

### Step 3.2: Module `src/hermes/ingestion/rss_parser.py`
Implement `FeedParser` and `FeedItem`:
- **Data Models:**
  ```python
  from dataclasses import dataclass, field
  from datetime import datetime
  from typing import Any


  @dataclass
  class FeedItem:
      guid: str
      title: str
      link: str
      published: datetime | None
      summary: str
      content: str = ""
      categories: list[str] = field(default_factory=list)
      author: str = ""
      raw_entry: dict[str, Any] = field(default_factory=dict)
  ```
- **Functionality:**
  - `async def fetch_and_parse_feed(url: str, timeout: float = 15.0, user_agent: str = "HermesCTI/1.0 (+https://cti.scogin.dev)") -> list[FeedItem]`
  - `def parse_feed_xml(xml_content: str | bytes) -> list[FeedItem]`: Handles `<rss><channel><item>`, `<feed><entry>` (Atom), Dublin Core (`dc:date`), Content Encoded (`content:encoded`), and HTML unescaping.
  - `def parse_published_date(date_str: str | None) -> datetime | None`: Robust parser supporting RFC 2822 (e.g. `Mon, 22 Aug 2026 08:00:00 GMT`), ISO 8601 (`2026-08-22T08:00:00Z`), and edge-case date formats, returning UTC `datetime`.
  - `class FeedDeduplicator`: Tracks seen GUIDs, content hashes, and canonical URLs to prevent re-processing across polling cycles.

### Step 3.3: Module `src/hermes/ingestion/web_scraper.py`
Implement `ArticleExtractor`:
- **Functionality:**
  - `class HTMLArticleParser(HTMLParser)`: Strips `<script>`, `<style>`, `<noscript>`, `<svg>`, `<nav>`, `<header>`, `<footer>`, `<aside>` tags; inserts newlines for block elements (`<p>`, `<h1>`-`<h6>`, `<li>`, `<div>`, `<br>`); decodes HTML entities.
  - `async def fetch_article_text(url: str, timeout: float = 20.0, user_agent: str = ...) -> str`: Fetches article HTML via `httpx.AsyncClient` with follow redirects, parses text, and normalizes excessive whitespace.
  - `def clean_html_content(raw_html: str) -> str`: Pure function for sanitizing HTML strings into normalized Markdown or plain text.
  - `def extract_pdf_text_fallback(pdf_bytes: bytes) -> str`: Safe extractor for PDF advisories (e.g. CISA PDFs) with error handling when PDF libraries are unavailable.

### Step 3.4: Module `src/hermes/ingestion/enrichment.py`
Implement external OSINT enrichment clients:
- **`class KEVEnricher`**:
  - Fetches CISA KEV JSON (`https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`).
  - Caches vulnerability catalog with configurable TTL (default 12 hours).
  - `def is_known_exploited(cve_id: str) -> bool`
  - `def get_kev_details(cve_id: str) -> dict[str, Any] | None`
- **`class EPSSEnricher`**:
  - Queries FIRST EPSS API (`https://api.first.org/data/v1/epss?cve={cve_id}`).
  - Supports bulk batch querying (`cve=CVE-1,CVE-2,...`).
  - `async def get_epss_score(cve_id: str) -> tuple[float, float] | None`: Returns `(epss_score, percentile)`.
- **`class AbuseIPDBEnricher`**:
  - Queries AbuseIPDB v2 check endpoint (`https://api.abuseipdb.com/api/v2/check`).
  - Reads `ABUSEIPDB_API_KEY` from environment. If not configured, gracefully falls back with `None` or cached mock.
  - Returns `abuse_confidence_score`, `country_code`, `isp`, `total_reports`.
- **`class VirusTotalEnricher`**:
  - Queries VirusTotal v3 IP/domain/hash endpoints (`https://www.virustotal.com/api/v3/ip_addresses/{ip}`, `/files/{hash}`).
  - Reads `VIRUSTOTAL_API_KEY` from environment.
  - Returns `malicious_count`, `suspicious_count`, `harmless_count`, `reputation`.
- **`class IngestionEnrichmentService`**:
  - In-memory async LRU cache for all lookups.
  - Semaphore-based concurrency limiting (e.g. 5 concurrent requests) and exponential backoff retry on HTTP 429/503.

---

## 4. Test Suite Requirements

### `tests/test_ingestion.py`
- `test_rss2_feed_parsing`: Parse standard RSS 2.0 XML with items, categories, and RFC 2822 dates.
- `test_atom_feed_parsing`: Parse standard Atom XML feed with entries, updated timestamps, and author fields.
- `test_feed_deduplication`: Verify `FeedDeduplicator` discards duplicate GUIDs and canonical links.
- `test_html_article_cleaning`: Verify script, style, and navigation tags are stripped while retaining readable article paragraphs.
- `test_malformed_feed_handling`: Ensure syntax errors, empty feeds, and non-XML responses raise structured errors without unhandled crashes.

### `tests/test_enrichment.py`
- `test_cisa_kev_lookup`: Mock CISA KEV JSON response and verify lookup by CVE-YYYY-NNNN.
- `test_epss_lookup_and_batching`: Mock EPSS API response and verify score and percentile parsing.
- `test_abuseipdb_enrichment_mocked`: Mock AbuseIPDB response and verify IP reputation parsing and missing API key fallback.
- `test_virustotal_enrichment_mocked`: Mock VirusTotal v3 response and verify detection ratios.
- `test_enrichment_cache_and_backoff`: Verify repeated lookups hit in-memory cache and 429 responses trigger retry backoff.

---

## 5. Verification Commands

Run within `../threat-intel-agent-wt1`:
```bash
# Verify test suite
uv run pytest tests/test_ingestion.py tests/test_enrichment.py -v

# Verify code formatting and linting
uv run ruff check src/hermes/ingestion tests/test_ingestion.py tests/test_enrichment.py
uv run ruff format --check src/hermes/ingestion tests/test_ingestion.py tests/test_enrichment.py
```

---

## 6. Commit & Merge Instructions

1. Commit changes in worktree 1:
   ```bash
   git add src/hermes/ingestion src/hermes/__init__.py tests/test_ingestion.py tests/test_enrichment.py
   git commit -m "feat(ingestion): add async feed parsers, article scraper, and OSINT enrichment clients"
   ```
2. In main repo workspace (`threat-intel-agent`):
   ```bash
   git merge feat/ingestion-enrichment --no-ff -m "Merge branch 'feat/ingestion-enrichment' (Phase 1)"
   ```
