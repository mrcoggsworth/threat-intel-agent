# Stage 5 Implementation Plan: Database Migration, Live Ingestion & Reconciliation

## Phase Context
- **Target Branch:** `main` (Post-merges of Worktrees 1, 2, 3, and 4)
- **Primary CLI Command:** `python main.py --sync-db --rebuild-all`
- **Authoritative Sources:** `config/sources.json`
- **Memory & Deduplication Target:** `.hermes/memories/MEMORY.md`

---

## 1. Scope & Responsibilities

Stage 5 unifies all 4 merged worktrees into an operational end-to-end pipeline:
1. **CLI Orchestration (`main.py`):** Extending `main.py` / `hermes_cti.cli.main` to support `--sync-db`, `--rebuild-all`, and daily orchestrator routines.
2. **Database Migration & Sync:** Applying Alembic database schema migrations and verifying table readiness.
3. **Live Source Ingestion & Historical Deduplication:** Executing collection across all active sources in `config/sources.json`, deduping against database records and `.hermes/memories/MEMORY.md`.
4. **Automated Enrichment & Playbook Generation:** Attaching CISA KEV status and FIRST EPSS metrics to extracted CVEs, tagging MITRE ATT&CK techniques, and synthesizing Sigma/YARA/SPL/KQL detection rules.
5. **Static Portal Rebuild & Export Refresh:** Generating refreshed static HTML portal pages, `portal/data/cti_database.json`, `portal/data/stix2_bundle.json`, and STIX 2.1 feeds.
6. **Worktree Cleanup & Full Suite Validation:** Removing temporary git worktrees and executing the complete automated test suite.

---

## 2. Integration & CLI Enhancements

### Step 2.1: CLI Command Extensions (`src/hermes_cti/cli/main.py` & `main.py`)
Enhance `main.py` and Typer CLI to accept top-level flags and commands:
```python
@app.command("sync-db")
def sync_db_command(...) -> None:
    """Run database migration, live ingestion from config/sources.json, and deduplication."""
    ...

@app.command("rebuild-all")
def rebuild_all_command(...) -> None:
    """Rebuild static portal pages, STIX 2.1 bundles, and JSON feeds."""
    ...
```
Also support orchestrator invocation:
```bash
python main.py --sync-db --rebuild-all
```

---

## 3. Step-by-Step Execution Workflow

### Step 3.1: Merge Verification on `main`
Ensure all 4 feature branches are cleanly merged in order:
```bash
git checkout main
git merge feat/ingestion-enrichment --no-ff -m "Merge 1: feat/ingestion-enrichment"
git merge feat/analysis-ioc-mitre --no-ff -m "Merge 2: feat/analysis-ioc-mitre"
git merge feat/playbooks-detection-rules --no-ff -m "Merge 3: feat/playbooks-detection-rules"
git merge feat/portal-ui-exports --no-ff -m "Merge 4: feat/portal-ui-exports"
```

### Step 3.2: Database Migration
```bash
uv run alembic upgrade head
```

### Step 3.3: Live Ingestion, Enrichment, and Portal Rebuild
```bash
uv run python main.py --sync-db --rebuild-all
```
This command:
1. Iterates through all 37+ sources in `config/sources.json`.
2. Normalizes articles and raw threat drops.
3. Extracts IoCs and refangs network indicators.
4. Queries CISA KEV and EPSS APIs for vulnerability enrichment.
5. Synthesizes Sigma rules, YARA signatures, and Two-Tiered Hunt Playbooks.
6. Generates `portal/index.html`, `portal/data/cti_database.json`, and `portal/data/stix2_bundle.json`.

### Step 3.4: Worktree Cleanup
Once merges and verification succeed, remove the 4 worktree directories and branches:
```bash
git worktree remove ../threat-intel-agent-wt1
git worktree remove ../threat-intel-agent-wt2
git worktree remove ../threat-intel-agent-wt3
git worktree remove ../threat-intel-agent-wt4
```

---

## 4. End-to-End Verification & Acceptance Criteria

### Automated Test Suite Run
Run the full test suite across the unified codebase:
```bash
uv run pytest -v
```
**Acceptance Criteria:**
- All 192 existing regression tests pass.
- All new tests (`test_ingestion.py`, `test_enrichment.py`, `test_analysis.py`, `test_playbooks.py`, `test_publisher.py`) pass.
- Zero test failures, zero regressions.

### Artifact Verification
Check that the following live files exist and contain valid data:
1. `portal/index.html` (Valid HTML markup with 1-click copy scripts and EPSS quadrant chart)
2. `portal/data/cti_database.json` (Valid JSON containing ingested reports and IoCs)
3. `portal/data/stix2_bundle.json` (Valid STIX 2.1 bundle with indicators and relationships)
