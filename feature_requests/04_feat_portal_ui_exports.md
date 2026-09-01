# Worktree 4 Implementation Plan: Portal Enhancements, STIX 2.1 & SIEM Export UI

## Branch & Worktree Configuration
- **Branch Name:** `feat/portal-ui-exports`
- **Worktree Directory:** `../threat-intel-agent-wt4`
- **Integration Merge Target:** `main` (Merge Phase 4, depends on Models, Analysis, and Playbooks)
- **Primary Deliverables:** Static portal pages, STIX 2.1 export bundle, 1-click SIEM copy UI, Webhook dispatchers

---

## 1. Scope & Responsibilities

Worktree 4 is responsible for the publishing, visualization, and export surfaces of Hermes CTI:
1. **Static Site & Portal Builder:** Compiling static portal HTML/JSON assets into `portal/` (`index.html`, `reports.html`, `cves.html`, `data/cti_database.json`).
2. **STIX 2.1 JSON Exporter:** Generating OASIS STIX 2.1 JSON bundles connecting `report`, `indicator`, `attack-pattern`, `vulnerability`, and `relationship` objects.
3. **Webhook & Alert Notifiers:** Formatting and dispatching threat alerts to Slack (Block Kit), Microsoft Teams (Adaptive Cards), Discord (Embeds), and generic JSON webhooks.
4. **Rich Portal UI Controls:** Delivering 1-click clipboard copy buttons for Sigma/SPL/KQL/YARA, interactive EPSS vs CVSS exploitability quadrant matrix, and direct STIX/Navigator download buttons.

---

## 2. File Ownership & Structural Layout

```text
src/
├── hermes/
│   └── publisher/
│       ├── __init__.py
│       ├── site_builder.py     # Static portal HTML/JSON compiler and asset generator
│       ├── stix_exporter.py    # STIX 2.1 JSON bundle builder (SDOs, SCOs, SROs)
│       └── notifier.py         # Multi-platform webhook dispatchers (Slack, Teams, Discord)
portal/
├── index.html                  # Main portal landing dashboard
├── assets/
│   ├── portal.css              # Custom styling, quadrant matrix, copy tooltips
│   └── portal.js               # 1-click copy handler, EPSS matrix rendering, STIX downloader
tests/
└── test_publisher.py           # Unit tests for site builder, STIX 2.1 bundle, and notifiers
```

---

## 3. Step-by-Step Implementation Details

### Step 3.1: Worktree Initialization
```bash
git worktree add ../threat-intel-agent-wt4 -b feat/portal-ui-exports
cd ../threat-intel-agent-wt4
```

### Step 3.2: Module `src/hermes/publisher/stix_exporter.py`
Implement `STIXExporter`:
- **STIX 2.1 Object Builders:**
  - `def create_stix_bundle(report_title: str, summary: str, published_date: str, iocs: dict[str, list[str]], cves: list[str], techniques: list[str]) -> dict[str, Any]`
  - Emits:
    - `type: "bundle"`, `id: f"bundle--{uuid4()}"`
    - `identity`: Author organization (`CTI-Hermes Autonomous Agent`).
    - `report`: Main CTI report SDO with `published`, `object_refs`.
    - `indicator`: SDOs with STIX patterning (e.g. `[ipv4-addr:value = '198.51.100.45']`, `[file:hashes.'SHA-256' = '...']`).
    - `vulnerability`: SDOs with `external_references` pointing to NVD / CVE.
    - `attack-pattern`: SDOs with MITRE ATT&CK technique IDs.
    - `relationship`: SROs linking `indicator` $\xrightarrow{\text{indicates}}$ `attack-pattern` and `attack-pattern` $\xrightarrow{\text{targets}}$ `vulnerability`.

### Step 3.3: Module `src/hermes/publisher/notifier.py`
Implement `ThreatNotifier`:
- **Webhook Dispatchers:**
  - `class SlackNotifier`: Builds Slack Block Kit payload with header, markdown summary, severity status badges, and report links.
  - `class TeamsNotifier`: Builds Microsoft Teams Adaptive Card / Connector payload with facts table and action buttons.
  - `class DiscordNotifier`: Builds Discord Embed payload with color-coded severity bar and IoC field list.
  - `class WebhookDispatcher`: Dispatches async HTTP POST requests with rate limiting and response verification.

### Step 3.4: Module `src/hermes/publisher/site_builder.py` & `portal/` UI
Implement `SiteBuilder`:
- **Static Asset Generation:**
  - `def build_portal(output_dir: Path, reports_data: list[dict], cves_data: list[dict], iocs_data: list[dict]) -> None`:
    - Renders `portal/index.html` (Hero metrics, latest reports, active CVE table, recent IoCs).
    - Writes `portal/data/cti_database.json` and `portal/data/stix2_bundle.json`.
    - Copies/generates `portal/assets/portal.css` and `portal/assets/portal.js`.
- **UI Enhancements (`portal/assets/`):**
  - **1-Click Copy Tool:** Interactive JS handler copying Sigma YAML, Splunk SPL, KQL, or YARA rule text to clipboard with feedback tooltip.
  - **EPSS vs CVSS Quadrant Matrix:** SVG/Canvas/CSS scatter chart plotting CVEs across 4 quadrants:
    - *Quadrant I (High CVSS $\ge 7.0$, High EPSS $\ge 0.15$):* **Urgent Action / Active Exploitation**.
    - *Quadrant II (High CVSS $\ge 7.0$, Low EPSS $< 0.15$):* **High Impact / Low Exploitation Probability**.
    - *Quadrant III (Low CVSS $< 7.0$, Low EPSS $< 0.15$):* **Low Priority**.
    - *Quadrant IV (Low CVSS $< 7.0$, High EPSS $\ge 0.15$):* **Weaponized Fast Attack**.

---

## 4. Test Suite Requirements

### `tests/test_publisher.py`
- `test_stix_bundle_generation`: Verify STIX 2.1 bundle structure, object types, UUID formatting, and relationship references.
- `test_slack_webhook_payload_format`: Validate Slack Block Kit JSON schema and section blocks.
- `test_teams_webhook_payload_format`: Validate Teams card JSON schema and facts formatting.
- `test_site_builder_static_compilation`: Verify `SiteBuilder.build_portal` produces valid HTML files and `cti_database.json` in destination directory.
- `test_epss_quadrant_classification_logic`: Verify mathematical classification of CVEs into the 4 exploitability quadrants.

---

## 5. Verification Commands

Run within `../threat-intel-agent-wt4`:
```bash
# Run publisher test suite
uv run pytest tests/test_publisher.py -v

# Code formatting and linting
uv run ruff check src/hermes/publisher tests/test_publisher.py
uv run ruff format --check src/hermes/publisher tests/test_publisher.py
```

---

## 6. Commit & Merge Instructions

1. Commit in worktree 4:
   ```bash
   git add src/hermes/publisher portal/ tests/test_publisher.py
   git commit -m "feat(publisher): add static site builder, STIX 2.1 exporter, webhook notifiers, and portal UI"
   ```
2. In main repository workspace:
   ```bash
   git merge feat/portal-ui-exports --no-ff -m "Merge branch 'feat/portal-ui-exports' (Phase 4)"
   ```
