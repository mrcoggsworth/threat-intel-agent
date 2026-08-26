#!/bin/sh
set -eu

# The profile CLI's cron create operation is the supported equivalent of cron add.

repo="${HERMES_REPOSITORY:?HERMES_REPOSITORY is required}"
profile="${HERMES_PROFILE:?HERMES_PROFILE is required (cti-analyst or cti-maintainer)}"
cron_bin="${HERMES_CRON_BIN:-hermes}"
interval="${HERMES_HEALTH_INTERVAL:-*/5 * * * *}"

case "$profile" in
    cti-analyst|cti-maintainer) ;;
    *) echo "unsupported Hermes profile: $profile" >&2; exit 2 ;;
esac

prompt_dir="${HERMES_PROMPT_DIR:-$repo/.hermes/profiles/$profile/prompts}"
[ -d "$prompt_dir" ] || { echo "profile prompt directory is missing: $prompt_dir" >&2; exit 2; }

add_job() {
    name="$1"
    schedule="$2"
    prompt_file="$3"
    profile_name="$4"
    prompt_path="$prompt_dir/$prompt_file"
    [ -f "$prompt_path" ] || { echo "cron prompt file is missing: $prompt_path" >&2; exit 2; }
    prompt_text="$(cat "$prompt_path")"
    existing_id="$("$cron_bin" --profile "$profile_name" cron list 2>/dev/null | grep -B 1 "Name: *${name}$" | head -n 1 | awk '{print $1}' || true)"
    if [ -n "$existing_id" ]; then
        "$cron_bin" --profile "$profile_name" cron remove "$existing_id" >/dev/null 2>&1 || true
    fi
    "$cron_bin" --profile "$profile_name" cron create "$schedule" "$prompt_text" \
        --name "$name" --workdir "$repo"
}

if [ "$profile" = "cti-analyst" ]; then
    add_job "cti-analyst-daily-analysis" "0 3 * * *" daily-analysis.md "$profile"
    add_job "cti-analyst-feed-quality" "30 3 * * *" feed-quality.md "$profile"
    add_job "cti-analyst-historical-resurfacing" "0 4 * * 1" historical-resurfacing.md "$profile"
    add_job "cti-analyst-monthly-retrospective" "0 5 1 * *" monthly-retrospective.md "$profile"
else
    add_job "cti-maintainer-weekly-maintenance" "0 6 * * 1" weekly-maintenance.md "$profile"
    add_job "cti-maintainer-approved-release" "0 7 * * 1" approved-release.md "$profile"
    add_job "cti-maintainer-recovery" "*/15 * * * *" recovery.md "$profile"
    watchdog_path="$prompt_dir/../scripts/health-watchdog.sh"
    [ -f "$watchdog_path" ] || { echo "health watchdog is missing: $watchdog_path" >&2; exit 2; }
    existing_watchdog="$("$cron_bin" --profile "$profile" cron list 2>/dev/null | grep -B 1 "Name: *cti-maintainer-health-watchdog$" | head -n 1 | awk '{print $1}' || true)"
    if [ -n "$existing_watchdog" ]; then
        "$cron_bin" --profile "$profile" cron remove "$existing_watchdog" >/dev/null 2>&1 || true
    fi
    "$cron_bin" --profile "$profile" cron create "$interval" \
        --name cti-maintainer-health-watchdog --script health-watchdog.sh \
        --no-agent --workdir "$repo"
fi

echo "Hermes cron definitions installed for $profile through the profile CLI"
