#!/bin/sh

# Start the locally built CTI-Hermes stack for home-lab testing.
# The production Compose file uses protected file-backed secrets created
# by setup-docker-secrets.sh.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file=${HERMES_COMPOSE_FILE:-$repo_root/deploy/docker-compose.yml}
env_file=${HERMES_ENV_FILE:-/opt/cti-hermes/env/production.env}
web_url=${HERMES_WEB_URL:-http://127.0.0.1:18000}
user_home=${HOME:-}
if [ -z "$user_home" ] || [ ! -d "$user_home" ]; then
    echo "HOME must name the current user home directory" >&2
    exit 1
fi
secret_dir=${HERMES_SECRET_DIR:-${XDG_STATE_HOME:-$user_home/.local/state}/cti-hermes/secrets}
export HERMES_SECRET_DIR="$secret_dir"

compose() {
    docker compose --env-file "$env_file" --file "$compose_file" "$@"
}

echo "Validating Compose configuration"
compose config --quiet

echo "Starting PostgreSQL"
compose up -d postgres

echo "Preparing runtime volume"
compose run --rm runtime-init

echo "Running database migrations"
compose run --rm migrate

echo "Starting CTI-Hermes services"
compose up -d --force-recreate --pull never web scheduler worker backup monitor

wait_for_health() {
    label=$1
    endpoint=$2
    attempts=${HERMES_HEALTH_ATTEMPTS:-30}
    attempt=1
    echo "Checking $label"
    while [ "$attempt" -le "$attempts" ]; do
        if curl --fail --silent --show-error --max-time 3 "$web_url$endpoint"; then
            printf '\n'
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    echo "Timed out waiting for $label: $web_url$endpoint" >&2
    return 1
}

wait_for_health liveness /health/live
wait_for_health readiness /health/ready

echo "Validating host Nginx"
if [ "$(id -u)" -eq 0 ]; then
    nginx -t
    systemctl reload nginx
else
    sudo nginx -t
    sudo systemctl reload nginx
fi

echo "CTI-Hermes local stack is running"
