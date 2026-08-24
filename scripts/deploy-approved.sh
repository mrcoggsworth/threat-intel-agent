#!/bin/sh
set -eu

[ "${HERMES_DEPLOY_APPROVED:-false}" = "true" ] || {
    echo "deployment blocked: set HERMES_DEPLOY_APPROVED=true only after human approval" >&2
    exit 2
}
[ -n "${HERMES_APPROVAL_REFERENCE:-}" ] || {
    echo "deployment blocked: HERMES_APPROVAL_REFERENCE is required" >&2
    exit 2
}

compose_file="${HERMES_COMPOSE_FILE:-deploy/docker-compose.yml}"
env_file="${HERMES_ENV_FILE:-deploy/.env}"
image="${HERMES_IMAGE:?HERMES_IMAGE must identify the approved image}"
state_dir="${HERMES_STATE_DIR:-/var/lib/cti-hermes}"
state_file="$state_dir/deployment-state"
mkdir -p "$state_dir"
case "$image" in
    *@sha256:*|*:v[0-9]*) ;;
    *) echo "deployment blocked: use a digest or immutable v* release tag" >&2; exit 2 ;;
esac

compose() {
    docker compose --env-file "$env_file" --file "$compose_file" "$@"
}
compose config >/dev/null
previous_image=$(sed -n 's/^image=//p' "$state_file" 2>/dev/null || true)
if [ -n "$previous_image" ] && [ "$previous_image" = "$image" ]; then
    echo "deployment blocked: approved image is already active" >&2
    exit 2
fi
docker pull "$image" >/dev/null
resolved_image=$(docker image inspect --format '{{index .RepoDigests 0}}' "$image")
[ -n "$resolved_image" ] || { echo "deployment blocked: image digest unavailable" >&2; exit 2; }

compose run --rm --no-deps backup /opt/hermes/backup-postgres.sh --once
compose run --rm migrate
printf 'image=%s\ndigest=%s\napproval=%s\n' "$image" "$resolved_image" "${HERMES_APPROVAL_REFERENCE}" >"$state_file"
compose up --detach postgres web worker scheduler backup monitor proxy

if deploy_smoke_output=$(HERMES_IMAGE="$image" compose run --rm --no-deps smoke 2>&1); then
    echo "deployment succeeded: $resolved_image"
    exit 0
fi
echo "$deploy_smoke_output" >&2
[ -n "$previous_image" ] || {
    echo "automatic rollback unavailable: no prior compatible image recorded" >&2
    exit 1
}
sed "s#^HERMES_IMAGE=.*#HERMES_IMAGE=$previous_image#" "$env_file" >"$env_file.rollback"
mv "$env_file.rollback" "$env_file"
compose up --detach postgres web worker scheduler backup monitor proxy
if compose run --rm --no-deps smoke; then
    echo "deployment failed and rolled back to $previous_image" >&2
else
    echo "deployment failed and rollback smoke test also failed" >&2
fi
exit 1
