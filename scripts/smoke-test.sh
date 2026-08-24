#!/bin/sh
set -eu

public_base="${1:?usage: smoke-test.sh PUBLIC_BASE_URL PRIVATE_BASE_URL TOKEN_FILE [REPORT_SLUG]}"
private_base="${2:?usage: smoke-test.sh PUBLIC_BASE_URL PRIVATE_BASE_URL TOKEN_FILE [REPORT_SLUG]}"
token_file="${3:?usage: smoke-test.sh PUBLIC_BASE_URL PRIVATE_BASE_URL TOKEN_FILE [REPORT_SLUG]}"
report_slug="${4:-}"
token=$(cat "$token_file")

status() {
    curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
        --connect-timeout "${SMOKE_CONNECT_TIMEOUT_SECONDS:-5}" \
        --max-time "${SMOKE_TOTAL_TIMEOUT_SECONDS:-15}" "$@"
}

expect() {
    actual="$1"
    expected="$2"
    label="$3"
    [ "$actual" = "$expected" ] || { echo "smoke failed: $label ($actual)" >&2; exit 1; }
}

expect "$(status "$public_base/health/live")" 200 "public liveness"
expect "$(status "$public_base/api/v1/public/reports")" 200 "public reports"
expect "$(status -H "X-Admin-Token: $token" -H "Host: ${HERMES_PRIVATE_HOST:-ops.cti-hermes.local}" "$private_base/api/v1/ops/version")" 200 "private version"
expect "$(status "$public_base/api/v1/ops/version")" 404 "public/private isolation"

if [ -n "$report_slug" ]; then
    expect "$(status "$public_base/reports/$report_slug")" 200 "canonical report"
    expect "$(status "$public_base/reports/$report_slug/hunt")" 200 "hunt page"
    expect "$(status "$public_base/reports/$report_slug/remediation")" 200 "remediation page"
    expect "$(status "$public_base/reports/$report_slug/detections")" 200 "detection page"
fi
