#!/bin/sh
set -eu

repo="${HERMES_REPOSITORY:?HERMES_REPOSITORY is required}"
cron_bin="${HERMES_CRON_BIN:-hermes}"
interval="${HERMES_HEALTH_INTERVAL:-*/5 * * * *}"

add_job() {
    name="$1"
    schedule="$2"
    prompt="$3"
    profile="$4"
    wake_agent="$5"
    "$cron_bin" --profile "$profile" cron add \
        --name "$name" --schedule "$schedule" \
        --prompt-file "$repo/.hermes/prompts/$prompt" \
        --workdir "$repo" --wake-agent "$wake_agent"
}

add_job "cti-daily-analyst" "0 3 * * *" daily-analyst.md cti-analyst true
add_job "cti-feed-quality" "30 3 * * *" feed-quality.md cti-analyst true
add_job "cti-historical-resurfacing" "0 4 * * 1" historical-resurfacing.md cti-analyst true
add_job "cti-monthly-retrospective" "0 5 1 * *" monthly-retrospective.md cti-analyst true
add_job "cti-weekly-maintenance" "0 6 * * 1" weekly-maintenance.md cti-maintainer true
add_job "cti-approved-release" "0 7 * * 1" approved-release.md cti-maintainer true
add_job "cti-recovery" "*/15 * * * *" recovery.md cti-maintainer true
"$cron_bin" --profile cti-maintainer cron add --name cti-health-watchdog \
    --schedule "$interval" --command "$repo/scripts/health-watchdog.sh" \
    --workdir "$repo" --wake-agent false

echo "Hermes cron definitions installed through the profile CLI"
