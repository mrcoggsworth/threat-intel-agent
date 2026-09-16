#!/bin/sh
set -eu

public_base="${HERMES_PUBLIC_BASE_URL:?HERMES_PUBLIC_BASE_URL is required}"
private_base="${PRIVATE_SERVICE_URL:?PRIVATE_SERVICE_URL is required}"
token_file="${HERMES_MAINTAINER_TOKEN_FILE:?HERMES_MAINTAINER_TOKEN_FILE is required}"
backup_metadata="${HERMES_BACKUP_METADATA_FILE:-none}"
heartbeat_file="${HERMES_HEARTBEAT_FILE:-none}"
cert_file="${HERMES_CERT_FILE:-none}"
backup_max_age="${HERMES_BACKUP_MAX_AGE_SECONDS:-172800}"
heartbeat_max_age="${HERMES_HEARTBEAT_MAX_AGE_SECONDS:-120}"
disk_fraction="${HERMES_DISK_USED_FRACTION:-0.85}"
container="${HERMES_POSTGRES_CONTAINER:-cti-hermes-postgres-1}"
failures=""

add_failure() {
    if [ -n "$failures" ]; then failures="$failures, "; fi
    failures="$failures$1"
}

status() {
    curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --connect-timeout "${HERMES_CONNECT_TIMEOUT_SECONDS:-5}" \
        --max-time "${HERMES_TOTAL_TIMEOUT_SECONDS:-15}" "$@"
}

age_seconds() {
    now=$(date +%s)
    modified=$(stat -c %Y "$1" 2>/dev/null || echo 0)
    echo $((now - modified))
}

[ "$(status "$public_base/health/live")" = 200 ] || add_failure "liveness"
token=$(cat "$token_file")
[ "$(status -H "X-Admin-Token: $token" "$private_base/health/ready")" = 200 ] || add_failure "readiness"
[ "$(status -H "X-Admin-Token: $token" "$private_base/api/v1/ops/scheduler-heartbeat")" = 200 ] || add_failure "scheduler heartbeat"
[ "$(status -H "X-Admin-Token: $token" "$private_base/api/v1/ops/last-success")" = 200 ] || add_failure "last-success"

if [ "$heartbeat_file" != "none" ] && [ -n "$heartbeat_file" ]; then
    [ -s "$heartbeat_file" ] || add_failure "heartbeat file missing"
    [ -s "$heartbeat_file" ] && [ "$(age_seconds "$heartbeat_file")" -le "$heartbeat_max_age" ] || add_failure "heartbeat stale"
fi
if [ "$backup_metadata" != "none" ] && [ -n "$backup_metadata" ]; then
    if command -v docker >/dev/null 2>&1; then
        if [ ! -s "$backup_metadata" ] || [ "$(age_seconds "$backup_metadata")" -gt "$backup_max_age" ]; then
            mkdir -p "$(dirname "$backup_metadata")" 2>/dev/null || true
            docker exec cti-hermes-backup-1 cat /backups/latest.metadata > "$backup_metadata" 2>/dev/null || true
        fi
    fi
    [ -s "$backup_metadata" ] || add_failure "backup metadata missing"
    [ -s "$backup_metadata" ] && [ "$(age_seconds "$backup_metadata")" -le "$backup_max_age" ] || add_failure "backup stale"
fi

disk_percent=$(df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}')
[ "$disk_percent" -lt "$(awk -v f="$disk_fraction" 'BEGIN {print int(f * 100)}')" ] || add_failure "disk threshold"

if [ "$cert_file" != "none" ] && [ -n "$cert_file" ]; then
    openssl x509 -in "$cert_file" -noout -checkend "${HERMES_CERT_MIN_REMAINING_SECONDS:-1209600}" >/dev/null 2>&1 || add_failure "certificate expiry"
fi

if command -v docker >/dev/null 2>&1; then
    [ "$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || true)" = healthy ] || add_failure "postgres health"
fi

cron_dirs="${HERMES_CRON_DIRS:-$HOME/.hermes/profiles/cti-analyst/cron $HOME/.hermes/profiles/cti-maintainer/cron $HOME/.hermes/cron}"
stale_locks=0
now=$(date +%s)
for cron_dir in $cron_dirs; do
    [ -d "$cron_dir" ] || continue
    for lf in "$cron_dir"/.*.lock "$cron_dir"/*.lock; do
        [ -e "$lf" ] || continue
        case "$(basename "$lf")" in .tick.lock|auth.lock) continue ;; esac
        mtime=0
        if stat -f %m "$lf" >/dev/null 2>&1; then
            mtime=$(stat -f %m "$lf")
        elif stat -c %Y "$lf" >/dev/null 2>&1; then
            mtime=$(stat -c %Y "$lf")
        fi
        if [ "$mtime" -gt 0 ] && [ $((now - mtime)) -gt "${HERMES_LOCK_MAX_AGE_SECONDS:-1800}" ]; then
            stale_locks=$((stale_locks + 1))
        fi
    done
done
[ "$stale_locks" -eq 0 ] || add_failure "stale cron locks detected ($stale_locks)"

if [ -n "$failures" ]; then
    echo "hermes health watchdog failed: $failures" >&2
    exit 1
fi
