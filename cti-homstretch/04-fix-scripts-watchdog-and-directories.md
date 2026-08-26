# Task 04: Fix Script Syntax, Watchdog Path, and Output Directories

## Role & Goal
You are a software engineer and script maintainer. Your objective is to fix the Python indentation bug in [`scripts/install-hermes-profiles.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-profiles.sh), fix the watchdog script path duplication in [`scripts/install-hermes-jobs.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-jobs.sh), update the active maintainer cron job, and create the missing `portal/analyst-output` directory.

---

## Background & Diagnosis
1. **Python Indentation Bug in [`scripts/install-hermes-profiles.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-profiles.sh#L164-L167):**
   ```python
       text = text.replace("/home/$USER/code/threat-intel-agent/", repo)
       text = text.replace("https://ops.cti-hermes.home.arpa", service_url)
   text = text.replace("https://matrix-1.taild27e3c.ts.net:9443", service_url)
       text = text.replace(sentinel, destination)
   ```
   Line 165 has 0 spaces of indentation while surrounding lines have 4 spaces. Executing this python snippet raises `IndentationError: unexpected indent`.

2. **Watchdog Script Path Duplication in [`scripts/install-hermes-jobs.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-jobs.sh#L43):**
   ```bash
   "$cron_bin" --profile "$profile" cron create "$interval" \
       --name cti-maintainer-health-watchdog --script scripts/health-watchdog.sh \
       --no-agent --workdir "$repo"
   ```
   Hermes CLI automatically looks for `--script` files inside `$HOME/.hermes/profiles/<profile>/scripts/`. Specifying `scripts/health-watchdog.sh` causes Hermes to search for `.../scripts/scripts/health-watchdog.sh`. The job has failed with:
   ```text
   error: Script not found: /home/cptcoggsworth/.hermes/profiles/cti-maintainer/scripts/scripts/health-watchdog.sh (131 failures in a row)
   ```

3. **Missing `portal/analyst-output` Directory:**
   The `cti-analyst` profile has permission to write to `portal/analyst-output/`, but the directory does not exist on disk, causing tools searching or listing this path to error out.

---

## Instructions

1. **Fix Indentation in [`scripts/install-hermes-profiles.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-profiles.sh):**
   Indent line 165 by 4 spaces so that the Python block is syntactically valid:
   ```python
       text = text.replace("/home/$USER/code/threat-intel-agent/", repo)
       text = text.replace("https://ops.cti-hermes.home.arpa", service_url)
       text = text.replace("https://matrix-1.taild27e3c.ts.net:9443", service_url)
       text = text.replace(sentinel, destination)
   ```

2. **Fix Script Path in [`scripts/install-hermes-jobs.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-jobs.sh):**
   Update line 43:
   ```bash
   "$cron_bin" --profile "$profile" cron create "$interval" \
       --name cti-maintainer-health-watchdog --script health-watchdog.sh \
       --no-agent --workdir "$repo"
   ```

3. **Update the Active Cron Job in `~/.hermes/profiles/cti-maintainer/cron/jobs.json`:**
   In [`~/.hermes/profiles/cti-maintainer/cron/jobs.json`](file:///home/cptcoggsworth/.hermes/profiles/cti-maintainer/cron/jobs.json), locate the job named `cti-maintainer-health-watchdog` (ID `389981d9073a`) and update `"script"` from `"scripts/health-watchdog.sh"` to `"health-watchdog.sh"`. Reset `failure_streak` to 0.

4. **Create the Analyst Output Directory:**
   ```bash
   mkdir -p /home/cptcoggsworth/code/threat-intel-agent/portal/analyst-output
   touch /home/cptcoggsworth/code/threat-intel-agent/portal/analyst-output/.gitkeep
   ```

---

## Verification Steps & Expected Outputs

1. Validate `install-hermes-profiles.sh` dry run:
   ```bash
   scripts/install-hermes-profiles.sh --dry-run
   ```
   **Expected Output:** Exits with code 0 and outputs `Dry run complete; no files or Hermes state changed.` without `IndentationError`.

2. Test the watchdog script execution via Hermes:
   ```bash
   hermes --profile cti-maintainer cron tick
   ```
   Or verify the watchdog script exists at the expected resolved path:
   ```bash
   ls -la /home/cptcoggsworth/.hermes/profiles/cti-maintainer/scripts/health-watchdog.sh
   ```
   **Expected Output:** File exists and is executable.

3. Verify `portal/analyst-output` directory:
   ```bash
   ls -la /home/cptcoggsworth/code/threat-intel-agent/portal/analyst-output
   ```
   **Expected Output:** Directory exists.

---

## Acceptance Criteria
- [ ] [`scripts/install-hermes-profiles.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/install-hermes-profiles.sh) executes without syntax or indentation errors.
- [ ] `cti-maintainer-health-watchdog` references `health-watchdog.sh` and resolves the script file correctly.
- [ ] `portal/analyst-output/` exists.
