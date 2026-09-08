#!/bin/sh
set -eu

[ "${HERMES_DEPLOY_APPROVED:-false}" = "true" ] || {
    echo "deployment blocked: explicit approval is required" >&2
    exit 2
}
[ -n "${HERMES_APPROVAL_REFERENCE:-}" ] || {
    echo "deployment blocked: HERMES_APPROVAL_REFERENCE is required" >&2
    exit 2
}
[ -n "${HERMES_APPROVAL_IDENTITY:-}" ] || {
    echo "deployment blocked: HERMES_APPROVAL_IDENTITY is required" >&2
    exit 2
}

compose_file="${HERMES_COMPOSE_FILE:-deploy/docker-compose.yml}"
env_file="${HERMES_ENV_FILE:-deploy/.env}"
image="${HERMES_IMAGE:?HERMES_IMAGE must be a digest-pinned image reference}"
source_revision="${HERMES_SOURCE_REVISION:?HERMES_SOURCE_REVISION is required}"
migration_revision="${HERMES_MIGRATION_REVISION:?HERMES_MIGRATION_REVISION is required}"
env_checksum_expected="${HERMES_ENV_CHECKSUM:?HERMES_ENV_CHECKSUM is required}"
backup_metadata="${HERMES_BACKUP_METADATA_FILE:?HERMES_BACKUP_METADATA_FILE is required}"
rollback_image="${HERMES_ROLLBACK_IMAGE:?HERMES_ROLLBACK_IMAGE is required}"
rollback_receipt="${HERMES_ROLLBACK_RECEIPT:?HERMES_ROLLBACK_RECEIPT is required}"
state_dir="${HERMES_STATE_DIR:-/var/lib/cti-hermes}"
receipt_dir="${HERMES_RECEIPT_DIR:-$state_dir/deployment-receipts}"
health_endpoint="${HERMES_HEALTH_ENDPOINT:-${HERMES_PUBLIC_BASE_URL:-http://127.0.0.1:18000}/health/live}"

case "$image" in
    *@sha256:*) ;;
    *) echo "deployment blocked: image must include an immutable sha256 digest" >&2; exit 2 ;;
esac
case "$rollback_image" in
    *@sha256:*) ;;
    *) echo "deployment blocked: rollback image must include an immutable sha256 digest" >&2; exit 2 ;;
esac
[ -f "$env_file" ] || { echo "deployment blocked: environment file is missing" >&2; exit 2; }
[ -f "$rollback_receipt" ] || {
    echo "deployment blocked: rollback receipt is missing" >&2
    exit 2
}
python3 scripts/deployment_receipt.py --verify "$rollback_receipt" >/dev/null || { echo "deployment blocked: rollback receipt is invalid" >&2; exit 2; }
[ "${HERMES_MIGRATION_COMPATIBLE:-false}" = "true" ] || {
    echo "deployment blocked: migration compatibility was not verified" >&2
    exit 2
}

env_checksum=$(sha256sum "$env_file" | awk '{print $1}')
[ "$env_checksum" = "$env_checksum_expected" ] || {
    echo "deployment blocked: environment checksum mismatch" >&2
    exit 2
}

compose() {
    docker compose --env-file "$env_file" --file "$compose_file" "$@"
}

compose config >/dev/null
docker pull "$image" >/dev/null
resolved_image=$(docker image inspect --format '{{index .RepoDigests 0}}' "$image")
[ -n "$resolved_image" ] || {
    echo "deployment blocked: image digest unavailable" >&2
    exit 2
}
requested_digest="${image##*@}"
resolved_digest="${resolved_image##*@}"
[ "$requested_digest" = "$resolved_digest" ] || {
    echo "deployment blocked: registry resolved a different image digest" >&2
    exit 2
}

mkdir -p "$state_dir" "$receipt_dir"
compose run --rm --no-deps backup /opt/hermes/backup-postgres.sh --once
[ -s "$backup_metadata" ] || {
    echo "deployment blocked: backup metadata is not ready" >&2
    exit 2
}
compose run --rm runtime-init
compose run --rm migrate
compose up --detach postgres web worker scheduler backup monitor

if ! deploy_smoke_output=$(HERMES_IMAGE="$image" compose run --rm --no-deps smoke 2>&1); then
    echo "$deploy_smoke_output" >&2
    echo "deployment failed; rollback requires the explicitly supplied immutable target" >&2
    HERMES_IMAGE="$rollback_image" compose up --detach postgres web worker scheduler backup monitor
    exit 1
fi

health_verified_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
receipt_path="$receipt_dir/$(date -u +%Y%m%dT%H%M%SZ)-$source_revision.json"
HERMES_RECEIPT_PATH="$receipt_path" \
HERMES_ARTIFACT_REFERENCE="$image" \
HERMES_ARTIFACT_DIGEST="$resolved_digest" \
HERMES_SOURCE_REVISION="$source_revision" \
HERMES_MIGRATION_REVISION="$migration_revision" \
HERMES_ENVIRONMENT_CHECKSUM="$env_checksum" \
HERMES_APPROVAL_REFERENCE="$HERMES_APPROVAL_REFERENCE" \
HERMES_APPROVAL_IDENTITY="$HERMES_APPROVAL_IDENTITY" \
HERMES_ROLLBACK_IMAGE="$rollback_image" \
HERMES_ROLLBACK_RECEIPT="$rollback_receipt" \
HERMES_BACKUP_METADATA="$backup_metadata" \
HERMES_HEALTH_ENDPOINT="$health_endpoint" \
HERMES_HEALTH_VERIFIED_AT="$health_verified_at" \
python3 scripts/deployment_receipt.py

echo "deployment succeeded: $resolved_image"
