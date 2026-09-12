#!/usr/bin/env bash
# Clean stale Hermes cron execution locks and orphan fire claims.
set -Eeuo pipefail

HERMES_ROOT="${HERMES_HOME:-$HOME/.hermes}"
CRON_DIR="${HERMES_CRON_DIR:-$HERMES_ROOT/profiles/cti-analyst/cron}"
MAX_AGE_SECONDS="${HERMES_LOCK_MAX_AGE_SECONDS:-900}" # 15 minutes default
DRY_RUN=false
VERBOSE=false

usage() {
    cat <<EOFU
Usage: $(basename "$0") [options]

Inspect and clean stale Hermes cron execution locks and orphaned fire claims.

Options:
  --cron-dir PATH        Target profile cron directory (default: \$HERMES_CRON_DIR or ~/.hermes/profiles/cti-analyst/cron)
  --max-age-seconds SEC  Maximum allowable age before a lock is deemed stale (default: 900)
  --dry-run              Report stale locks and claims without deleting or modifying
  -v, --verbose          Show detailed inspection messages
  -h, --help             Show this help message
EOFU
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --cron-dir)
            [ "$#" -ge 2 ] || { echo "error: --cron-dir requires a path" >&2; exit 2; }
            CRON_DIR="$2"
            shift
            ;;
        --max-age-seconds)
            [ "$#" -ge 2 ] || { echo "error: --max-age-seconds requires seconds" >&2; exit 2; }
            MAX_AGE_SECONDS="$2"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            ;;
        -v|--verbose)
            VERBOSE=true
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            usage
            exit 2
            ;;
    esac
    shift
done

if [ ! -d "$CRON_DIR" ]; then
    [ "$VERBOSE" = true ] && echo "Cron directory does not exist: $CRON_DIR (skipping)"
    exit 0
fi

now=$(date +%s)

get_file_age() {
    local filepath="$1"
    local mtime=0
    if stat -f %m "$filepath" >/dev/null 2>&1; then
        # BSD / macOS stat
        mtime=$(stat -f %m "$filepath")
    elif stat -c %Y "$filepath" >/dev/null 2>&1; then
        # GNU / Linux stat
        mtime=$(stat -c %Y "$filepath")
    else
        mtime=0
    fi
    if [ "$mtime" -gt 0 ]; then
        echo $((now - mtime))
    else
        echo 0
    fi
}

cleaned_locks=0

# Inspect all .*.lock and *.lock files
for lockfile in "$CRON_DIR"/.*.lock "$CRON_DIR"/*.lock; do
    [ -e "$lockfile" ] || continue
    filename=$(basename "$lockfile")

    age=$(get_file_age "$lockfile")
    is_stale=false
    reason=""

    # Check if lockfile contains a PID
    if [ -s "$lockfile" ]; then
        pid=$(head -n 1 "$lockfile" | grep -oE '[0-9]+' | head -n 1 || true)
        if [ -n "$pid" ]; then
            if ! kill -0 "$pid" 2>/dev/null; then
                is_stale=true
                reason="holding PID $pid is not running (age ${age}s)"
            fi
        fi
    fi

    # Check age threshold if not already marked stale
    if [ "$is_stale" = false ] && [ "$age" -ge "$MAX_AGE_SECONDS" ]; then
        is_stale=true
        reason="exceeded max age threshold (${age}s >= ${MAX_AGE_SECONDS}s)"
    fi

    if [ "$is_stale" = true ]; then
        if [ "$DRY_RUN" = true ]; then
            echo "[DRY-RUN] Would remove stale lock: $filename ($reason)"
        else
            echo "[CLEAN] Removing stale lock: $filename ($reason)"
            rm -f "$lockfile"
            cleaned_locks=$((cleaned_locks + 1))
        fi
    elif [ "$VERBOSE" = true ]; then
        echo "[ACTIVE] Preserving lock: $filename (age ${age}s < ${MAX_AGE_SECONDS}s)"
    fi
done

# Inspect jobs.json for stale fire_claim
jobs_file="$CRON_DIR/jobs.json"
if [ -f "$jobs_file" ] && command -v python3 >/dev/null 2>&1; then
    python3 - <<PY
import json
import os
import sys

jobs_path = "$jobs_file"
dry_run = "$DRY_RUN" == "true"
verbose = "$VERBOSE" == "true"

try:
    with open(jobs_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    sys.exit(0)

modified = False
claims_cleared = 0

jobs = data if isinstance(data, list) else data.get("jobs", [])
for job in jobs:
    claim = job.get("fire_claim")
    if claim is not None:
        cron_dir = "$CRON_DIR"
        has_active_lock = any([
            os.path.exists(os.path.join(cron_dir, f".fire-{claim}.lock")),
            os.path.exists(os.path.join(cron_dir, f"fire-{claim}.lock")),
        ]) if isinstance(claim, str) else False

        if not has_active_lock:
            if dry_run:
                print(f"[DRY-RUN] Would clear orphan fire_claim '{claim}' on job '{job.get('id')}'")
            else:
                print(f"[CLEAN] Clearing orphan fire_claim '{claim}' on job '{job.get('id')}'")
                job["fire_claim"] = None
                modified = True
                claims_cleared += 1

if modified and not dry_run:
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
PY
fi

echo "Lock cleanup completed. Stale locks removed: $cleaned_locks"
exit 0
