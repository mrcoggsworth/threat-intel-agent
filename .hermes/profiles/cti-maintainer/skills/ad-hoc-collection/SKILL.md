---
name: ad-hoc-collection
description: Start and monitor one authenticated CTI-Hermes collection on demand.
version: 1.0.0
metadata:
  hermes:
    tags: [CTI-Hermes, ingestion, operations, collection]
    related_skills: [docker-compose-operations, test-ci-diagnosis]
---

# Ad-hoc CTI collection

Use this skill only when the operator explicitly asks for an immediate CTI-Hermes
collection. The `/ad-hoc-collection` slash command is the approval to start one normal,
lock-protected collection. This skill does not deploy code, change
`config/sources.json`, modify PostgreSQL directly, or create scheduled jobs.

## Profile and authorization

This skill belongs to `cti-maintainer`, not `cti-analyst`, because the collection
trigger is an authenticated private operations endpoint using `X-Admin-Token`.
Never read the analyst token for this operation and never place either token in
chat output, logs, a Git commit, or a URL.

The deployed application is behind Caddy. Use the materialized private service
URL below, or override it with `HERMES_CTI_PRIVATE_SERVICE_URL` when the home
lab uses a different private DNS name or port:

```text
Private service URL: https://hermes.cti.scogin.dev
Manual trigger: POST /api/v1/ops/collection
Trigger status: GET /api/v1/ops/collection/{trigger_id}
Authentication: X-Admin-Token
Authoritative registry: config/sources.json (currently 38 active sources)
```

The default admin-token locations are the protected host secret path and the
profile-materialized path. Prefer `HERMES_CTI_ADMIN_TOKEN_FILE` if the host
layout differs:

```text
/home/<operator>/.local/state/cti-hermes/secrets/admin-token
/etc/hermes/cti-maintainer/admin-token
```

## Bash procedure

Run the following as one terminal command block. It keeps the token in a shell
variable, never prints it, waits for the asynchronous collection to finish, and
prints only the API response fields needed for operator follow-up.

```bash
set -Eeuo pipefail

private_service_url="${HERMES_CTI_PRIVATE_SERVICE_URL:-https://hermes.cti.scogin.dev}"
token_file="${HERMES_CTI_ADMIN_TOKEN_FILE:-/home/$(id -un)/.local/state/cti-hermes/secrets/admin-token}"
if [[ ! -r "$token_file" && -r /etc/hermes/cti-maintainer/admin-token ]]; then
    token_file="/etc/hermes/cti-maintainer/admin-token"
fi
[[ -r "$token_file" ]] || {
    printf 'Admin token file is not readable: %s\n' "$token_file" >&2
    exit 2
}
admin_token="$(<"$token_file")"
[[ -n "$admin_token" ]] || {
    printf 'Admin token file is empty: %s\n' "$token_file" >&2
    exit 2
}

curl_json() {
    local method="$1"
    local endpoint="$2"
    if [[ "$method" == "POST" ]]; then
        curl --fail --silent --show-error --max-time 30 \
            -X POST -H "X-Admin-Token: $admin_token" "$endpoint"
    else
        curl --fail --silent --show-error --max-time 30 \
            -H "X-Admin-Token: $admin_token" "$endpoint"
    fi
}

ready="$(curl_json GET "$private_service_url/health/ready")"
printf 'readiness=%s\n' "$ready"

trigger="$(curl_json POST "$private_service_url/api/v1/ops/collection")"
trigger_id="$(printf '%s' "$trigger" | python3 -c \
    'import json, sys; print(json.load(sys.stdin)["trigger_id"])')"
run_id="$(printf '%s' "$trigger" | python3 -c \
    'import json, sys; print(json.load(sys.stdin)["run_id"])')"
status_url="$private_service_url/api/v1/ops/collection/$trigger_id"
printf 'trigger_id=%s\nrun_id=%s\n' "$trigger_id" "$run_id"

deadline=$((SECONDS + 1800))
while (( SECONDS < deadline )); do
    status_payload="$(curl_json GET "$status_url")"
    state="$(printf '%s' "$status_payload" | python3 -c \
        'import json, sys; print(json.load(sys.stdin)["status"])')"
    printf 'collection_status=%s\n' "$state"
    case "$state" in
        completed)
            printf '%s\n' "$status_payload"
            exit 0
            ;;
        failed|lock_busy)
            printf '%s\n' "$status_payload" >&2
            exit 1
            ;;
        queued|running)
            sleep 10
            ;;
        *)
            printf 'Unexpected collection status: %s\n' "$state" >&2
            printf '%s\n' "$status_payload" >&2
            exit 1
            ;;
    esac
done

printf 'Collection did not reach a terminal state within 30 minutes.\n' >&2
printf 'Resume polling with trigger_id=%s and run_id=%s.\n' "$trigger_id" "$run_id" >&2
exit 1
```

## Required interpretation

- A `202` response means the request was accepted, not that ingestion has
  completed. Preserve the `trigger_id` and `run_id`.
- `completed` means the persisted run reached its terminal completed state;
  inspect the returned source counts and error summary before reporting success.
- `failed` means the run completed with source or pipeline failures. Preserve
  the run ID and report the failed-source summary.
- `lock_busy` means the scheduler or another manual request owns the daily
  advisory lock. Do not retry repeatedly and do not run `uv run hermes-cti db
  run-daily` from the host; wait for the existing run and inspect
  `/api/v1/ops/run-status`.
- A missing database or source registry returns an operational error. Report
  it as a service/configuration problem; do not attempt direct database setup.
- After completion, hand the `run_id` to `cti-analyst` for evidence review and
  analysis. Do not perform analyst publication work from this maintainer skill.

Return the readiness result, trigger ID, run ID, terminal state, source counts,
error summary, and the next action. Never claim that analysis or publication ran
unless the analyst profile reports that separately.
