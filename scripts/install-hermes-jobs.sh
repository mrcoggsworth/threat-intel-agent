#!/bin/sh
set -eu

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
    prompt="$3"
    profile_name="$4"
    wake_agent="$5"
    "$cron_bin" --profile "$profile_name" cron add \
        --name "$name" --schedule "$schedule" \
        --prompt-file "$prompt_dir/$prompt" \
        --workdir "$repo" --wake-agent "$wake_agent"
}

if [ "$profile" = "cti-analyst" ]; then
    add_job "cti-analyst-daily-analysis" "0 3 * * *" daily-analysis.md "$profile" true
    add_job "cti-analyst-feed-quality" "30 3 * * *" feed-quality.md "$profile" true
    add_job "cti-analyst-historical-resurfacing" "0 4 * * 1" historical-resurfacing.md "$profile" true
    add_job "cti-analyst-monthly-retrospective" "0 5 1 * *" monthly-retrospective.md "$profile" true
else
    add_job "cti-maintainer-weekly-maintenance" "0 6 * * 1" weekly-maintenance.md "$profile" true
    add_job "cti-maintainer-approved-release" "0 7 * * 1" approved-release.md "$profile" true
    add_job "cti-maintainer-recovery" "*/15 * * * *" recovery.md "$profile" true
    "$cron_bin" --profile "$profile" cron add --name cti-maintainer-health-watchdog \
        --schedule "$interval" --command "$repo/.hermes/profiles/cti-maintainer/scripts/health-watchdog.sh" \
        --workdir "$repo" --wake-agent false
fi

echo "Hermes cron definitions installed for $profile through the profile CLI"
