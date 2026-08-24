#!/bin/sh
set -eu

heartbeat_file="${HERMES_SCHEDULER_HEARTBEAT_FILE:-/run/hermes/scheduler.heartbeat}"
heartbeat_dir=$(dirname "$heartbeat_file")
mkdir -p "$heartbeat_dir"

touch_heartbeat() {
    date -u +%Y-%m-%dT%H:%M:%SZ >"$heartbeat_file"
}

while :; do
    touch_heartbeat
    sleep "${HERMES_HEARTBEAT_INTERVAL_SECONDS:-30}"
done &
heartbeat_pid=$!
trap 'kill "$heartbeat_pid" 2>/dev/null || true' EXIT INT TERM

exec hermes-cti-scheduler
