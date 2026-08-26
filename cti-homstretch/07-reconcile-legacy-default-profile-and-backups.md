# Task 07: Reconcile Legacy Default Profile Jobs & Fix Backups

## Role & Goal
You are a system administrator and codebase custodian. Your objective is to reconcile the legacy flat-file cron workflow (`Daily Threat Intel` in the default profile) with the new database-backed `cti-analyst` profile, resolve the model lookup failure on the `Daily backups` job, and clean up dead directory artifacts.

---

## Background & Diagnosis
1. **Legacy Flat-File Ingestion Job (`0c04163e8a06`):**
   - In the `default` Hermes profile (`~/.hermes/cron/jobs.json`), job `0c04163e8a06` runs every morning at 08:00.
   - It instructs the agent to write Markdown and JSON files directly to `./portal/` (`portal/cti_daily_report_YYYYMMDD.md`, `portal/collection_*.json`, `portal/data/cti_database.json`).
   - The original Python modules in `hermes/` (`hermes.ingestion`, `hermes.analysis`, `hermes.playbooks`, `hermes.publisher`) were deleted during the refactoring to `src/hermes_cti`, leaving behind only empty `__pycache__` folders.
   - This legacy job bypasses the PostgreSQL database, resulting in split-brain data (files on disk vs empty database).

2. **Daily Backup Job Failure (`9de28d4b5752`):**
   - Job `9de28d4b5752` in `~/.hermes/cron/jobs.json` failed with:
     ```text
     RuntimeError: HTTP 400: model 'gemma-4-26B-A4B-it-MXFP4_MOE.gguf' not found (5 failures in a row)
     ```
   - The local `llamacpp` container serves `gemma-4-26b`.

---

## Instructions

1. **Decommission or Pause Legacy `Daily Threat Intel` Job:**
   Pause or remove the legacy flat-file cron job so it does not compete with or overwrite `cti-analyst`:
   ```bash
   hermes cron pause 0c04163e8a06
   ```
   *(Or remove via `hermes cron rm 0c04163e8a06` if fully replaced by `cti-analyst-daily-analysis`).*

2. **Fix the Daily Backup Job Model Configuration:**
   - In [`~/.hermes/cron/jobs.json`](file:///home/cptcoggsworth/.hermes/cron/jobs.json), update job `9de28d4b5752` to use `no_agent: true` with a script execution or configure its model to `gemma-4-26b` (matching the active `llamacpp` container).
   - Alternatively, update the job using the CLI:
     ```bash
     hermes cron edit 9de28d4b5752 --model gemma-4-26b
     ```
   - Reset the failure streak and test a manual run:
     ```bash
     hermes cron run 9de28d4b5752
     ```

3. **Clean Up Stale Residual Directories:**
   Remove the orphaned `__pycache__` residue under `hermes/`:
   ```bash
   rm -rf /home/cptcoggsworth/code/threat-intel-agent/hermes
   ```

4. **Verify Final Cron State Across All Profiles:**
   ```bash
   echo "=== Default Profile ==="
   hermes cron list
   
   echo "=== CTI Analyst Profile ==="
   hermes --profile cti-analyst cron list
   
   echo "=== CTI Maintainer Profile ==="
   hermes --profile cti-maintainer cron list
   ```

---

## Verification Steps & Expected Outputs

1. Verify default profile jobs status:
   ```bash
   hermes cron list
   ```
   **Expected Output:** `Daily Threat Intel` is `[paused]` or removed; `Daily backups` shows `[active]` with 0 failures.

2. Verify CTI Analyst Profile Jobs:
   ```bash
   hermes --profile cti-analyst cron list
   ```
   **Expected Output:** `cti-analyst-daily-analysis` and `cti-analyst-feed-quality` are active and healthy.

3. Verify CTI Maintainer Profile Jobs:
   ```bash
   hermes --profile cti-maintainer cron list
   ```
   **Expected Output:** `cti-maintainer-health-watchdog` is active without `Script not found` errors.

---

## Acceptance Criteria
- [ ] No duplicate or competing cron jobs writing flat files to disk.
- [ ] Stale `hermes/` directory residue is removed.
- [ ] `Daily backups` executes successfully.
- [ ] All active Hermes profiles (`default`, `cti-analyst`, `cti-maintainer`) report clean status.
