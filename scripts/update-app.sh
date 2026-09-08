#!/usr/bin/env bash
# Deterministic updater for an already-built immutable application image.
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_root"
compose_file="${HERMES_COMPOSE_FILE:-$repo_root/deploy/docker-compose.yml}"
env_file="${HERMES_ENV_FILE:-/opt/cti-hermes/env/production.env}"
image_ref="${HERMES_IMAGE:?HERMES_IMAGE must be an immutable sha256-pinned reference}"
web_url="${HERMES_WEB_URL:-http://127.0.0.1:18000}"
secret_dir="${HERMES_SECRET_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/cti-hermes/secrets}"
export HERMES_SECRET_DIR="$secret_dir"

case "$image_ref" in
    *@sha256:*) ;;
    *) echo "HERMES_IMAGE must include an immutable sha256 digest" >&2; exit 1 ;;
esac
export HERMES_IMAGE="$image_ref"

run_tests=false
build_css=true
restart_services=true
run_migrations=true
verify_health=true

usage() {
    cat <<EOF
Usage: ./scripts/update-app.sh [OPTIONS]

Updates the stack using a pre-built, digest-pinned image. Production approval
and deployment receipts are handled by scripts/deploy-approved.sh.

Options:
  --test          Run unit tests and linter before updating
  --no-css        Skip compiling Tailwind CSS
  --no-build      Compatibility flag; images are never built here
  --no-restart    Skip restarting Docker Compose services
  --no-migrate    Skip database migrations
  --no-verify     Skip post-deployment health verification
  -h, --help      Show this help message

Environment variables:
  HERMES_IMAGE        Required immutable image reference (name@sha256:digest)
  HERMES_ENV_FILE     Compose env file (default: /opt/cti-hermes/env/production.env)
  HERMES_COMPOSE_FILE Docker Compose YAML
  HERMES_WEB_URL      Local web service URL (default: http://127.0.0.1:18000)
  HERMES_SECRET_DIR   Directory containing secrets
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --test) run_tests=true; shift ;;
        --no-css) build_css=false; shift ;;
        --no-build) shift ;;
        --no-restart) restart_services=false; shift ;;
        --no-migrate) run_migrations=false; shift ;;
        --no-verify) verify_health=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

info() { printf "[INFO] %s\n" "$*"; }
compose() {
    if [[ -f "$env_file" ]]; then
        docker compose --env-file "$env_file" --file "$compose_file" "$@"
    else
        docker compose --file "$compose_file" "$@"
    fi
}

[[ -d "$secret_dir" ]] || { echo "Secrets directory missing: $secret_dir" >&2; exit 1; }
if [[ "$run_tests" == true ]]; then
    if command -v uv >/dev/null 2>&1; then
        uv run ruff check --quiet
        uv run pytest -q --disable-warnings
    else
        pytest -q --disable-warnings
    fi
fi
if [[ "$build_css" == true ]] && command -v npm >/dev/null 2>&1; then
    npm run build:css >/dev/null
fi
compose config --quiet
if [[ "$run_migrations" == true ]]; then
    compose up -d postgres >/dev/null
    compose run --rm --quiet-pull runtime-init >/dev/null
    compose run --rm --quiet-pull migrate >/dev/null
fi
if [[ "$restart_services" == true ]]; then
    compose up -d --force-recreate --pull never web scheduler worker backup monitor >/dev/null
fi
if [[ "$verify_health" == true ]]; then
    curl --fail --silent --show-error --max-time 5 "$web_url/health/live" >/dev/null
    curl --fail --silent --show-error --max-time 5 "$web_url/health/ready" >/dev/null
    curl --fail --silent --show-error --max-time 5 "$web_url/reports" >/dev/null
fi
info "Hermes CTI stack updated successfully with $image_ref"
