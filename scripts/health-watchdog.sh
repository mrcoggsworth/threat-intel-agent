#!/bin/sh
set -eu

public_base="${HERMES_PUBLIC_BASE_URL:?HERMES_PUBLIC_BASE_URL is required}"
private_base="${HERMES_PRIVATE_BASE_URL:?HERMES_PRIVATE_BASE_URL is required}"
token_file="${HERMES_ADMIN_TOKEN_FILE:?HERMES_ADMIN_TOKEN_FILE is required}"
backup_dir="${HERMES_BACKUP_DIR:?HERMES_BACKUP_DIR is required}"
cert_file="${HERMES_CERT_FILE:?HERMES_CERT_FILE is required}"
max_age="${HERMES_MAX_AGE_SECONDS:-172800}"
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

[ "$(status "$public_base/health/live")" = 200 ] || add_failure "liveness"
token=$(cat "$token_file")
[ "$(status -H "X-Admin-Token: $token" "$private_base/health/ready")" = 200 ] || add_failure "readiness"
[ "$(status -H "X-Admin-Token: $token" "$private_base/api/v1/ops/scheduler-heartbeat")" = 200 ] || add_failure "scheduler heartbeat"
[ "$(status -H "X-Admin-Token: $token" "$private_base/api/v1/ops/last-success")" = 200 ] || add_failure "last-success"
[ "$(status -H "X-Admin-Token: $token" "$private_base/api/v1/ops/version")" = 200 ] || add_failure "private version"

latest=$(find "$backup_dir" -type f -name 'hermes-*.dump.enc.metadata' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | awk '{print $2}')
[ -n "$latest" ] || add_failure "backup missing"
if [ -n "$latest" ]; then
    backup_epoch=$(stat -c %Y "$latest")
    now_epoch=$(date +%s)
    [ $((now_epoch - backup_epoch)) -le "$max_age" ] || add_failure "backup stale"
fi

disk_percent=$(df -P / | awk 'NR==2 {gsub(/%/, "", $5); print $5}')
[ "$disk_percent" -lt "$(awk -v f="$disk_fraction" 'BEGIN {print int(f * 100)}')" ] || add_failure "disk threshold"
openssl x509 -in "$cert_file" -noout -checkend "${HERMES_CERT_MIN_REMAINING_SECONDS:-1209600}" >/dev/null 2>&1 || add_failure "certificate expiry"
if command -v docker >/dev/null 2>&1; then
    [ "$(docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || true)" = healthy ] || add_failure "postgres health"
fi

if [ -n "$failures" ]; then
    echo "hermes health watchdog failed: $failures" >&2
    exit 1
fi
