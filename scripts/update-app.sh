#!/usr/bin/env bash
# ==============================================================================
# update-app.sh - Deterministic Hermes CTI application updater
#
# Builds CSS assets, builds container image, applies DB migrations,
# restarts Docker Compose services with unified image version, and validates health.
# ==============================================================================
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$repo_root"

# Defaults & configuration
compose_file="${HERMES_COMPOSE_FILE:-$repo_root/deploy/docker-compose.yml}"
env_file="${HERMES_ENV_FILE:-/opt/cti-hermes/env/production.env}"
image_tag="${HERMES_IMAGE:-cti-hermes:local}"
web_url="${HERMES_WEB_URL:-http://127.0.0.1:18000}"
secret_dir="${HERMES_SECRET_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/cti-hermes/secrets}"
export HERMES_SECRET_DIR="$secret_dir"
export HERMES_IMAGE="$image_tag"

run_tests=false
build_css=true
build_image=true
restart_services=true
run_migrations=true
verify_health=true

usage() {
    cat <<EOF
Usage: ./scripts/update-app.sh [OPTIONS]

Safely update the Hermes CTI application stack after code changes or git merges.

Options:
  --test          Run unit tests and linter before updating
  --no-css        Skip compiling Tailwind CSS
  --no-build      Skip building container image
  --no-restart    Skip restarting Docker Compose services
  --no-migrate    Skip database migrations
  --no-verify     Skip post-deployment health verification
  -h, --help      Show this help message

Environment variables:
  HERMES_IMAGE        Container image name (default: cti-hermes:local)
  HERMES_ENV_FILE     Compose env file (default: /opt/cti-hermes/env/production.env)
  HERMES_COMPOSE_FILE Docker Compose YAML (default: deploy/docker-compose.yml)
  HERMES_WEB_URL      Local web service URL (default: http://127.0.0.1:18000)
  HERMES_SECRET_DIR   Directory containing secrets (default: ~/.local/state/cti-hermes/secrets)
EOF
}

# Parse CLI flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test) run_tests=true; shift ;;
        --no-css) build_css=false; shift ;;
        --no-build) build_image=false; shift ;;
        --no-restart) restart_services=false; shift ;;
        --no-migrate) run_migrations=false; shift ;;
        --no-verify) verify_health=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

info() { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m[OK]\033[0m   %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR]\033[0m  %s\n" "$*" >&2; }

info "Starting Hermes CTI update pipeline..."

# Preflight checks
if [[ ! -d "$secret_dir" ]]; then
    err "Secrets directory missing: $secret_dir"
    err "Run ./scripts/setup-docker-secrets.sh first."
    exit 1
fi

compose() {
    if [[ -f "$env_file" ]]; then
        docker compose --env-file "$env_file" --file "$compose_file" "$@"
    else
        docker compose --file "$compose_file" "$@"
    fi
}

# Step 1: Preflight test checks (optional)
if [[ "$run_tests" == "true" ]]; then
    info "Running preflight checks (pytest & ruff)..."
    if command -v uv >/dev/null 2>&1; then
        uv run ruff check --quiet
        uv run pytest -q --disable-warnings
    else
        pytest -q --disable-warnings
    fi
    ok "Preflight tests and linting passed"
fi

# Step 2: Build CSS assets
if [[ "$build_css" == "true" ]]; then
    info "Compiling Tailwind CSS..."
    if command -v npm >/dev/null 2>&1; then
        npm run build:css >/dev/null
    else
        npx --yes @tailwindcss/cli -i src/hermes_cti/portal/static/input.css -o src/hermes_cti/portal/static/portal.css --minify >/dev/null
    fi
    ok "Tailwind CSS built successfully"
fi

# Step 3: Build container image
if [[ "$build_image" == "true" ]]; then
    info "Building container image: $image_tag..."
    docker build -t "$image_tag" -f deploy/Dockerfile . >/dev/null
    ok "Container image built: $image_tag"
fi

# Step 4: Validate Compose configuration
info "Validating Compose configuration..."
compose config --quiet
ok "Compose configuration is valid"

# Step 5: Database migrations
if [[ "$run_migrations" == "true" ]]; then
    info "Running database migrations..."
    compose up -d postgres >/dev/null
    compose run --rm --quiet-pull runtime-init >/dev/null
    compose run --rm --quiet-pull migrate >/dev/null
    ok "Database migrations applied to head"
fi

# Step 6: Restart services
if [[ "$restart_services" == "true" ]]; then
    info "Recreating application services..."
    compose up -d --force-recreate --pull never web scheduler worker backup monitor >/dev/null
    ok "Services recreated with image $image_tag"
fi

# Step 7: Verification & Health checks
if [[ "$verify_health" == "true" ]]; then
    info "Verifying service health..."
    attempts=30
    attempt=1
    live_ok=false
    while [[ $attempt -le $attempts ]]; do
        if curl --fail --silent --show-error --max-time 3 "$web_url/health/live" >/dev/null 2>&1; then
            live_ok=true
            break
        fi
        sleep 1
        ((attempt++))
    done

    if [[ "$live_ok" != "true" ]]; then
        err "Liveness check timed out at $web_url/health/live"
        exit 1
    fi

    # Check readiness
    if ! curl --fail --silent --show-error --max-time 5 "$web_url/health/ready" >/dev/null 2>&1; then
        err "Readiness check failed at $web_url/health/ready"
        exit 1
    fi

    # Check sample portal routes
    if ! curl --fail --silent --show-error --max-time 5 "$web_url/reports" >/dev/null 2>&1; then
        err "Portal reports route failed at $web_url/reports"
        exit 1
    fi

    ok "All health checks passed (liveness, readiness, portal)"
fi

info "Hermes CTI stack updated successfully!"
