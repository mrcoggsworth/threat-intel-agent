#!/bin/sh

# Bootstrap the protected file-backed secrets required by deploy/docker-compose.yml.
# Secret values are generated or read from protected files and are never
# printed. This standalone Compose path does not require Docker Swarm.

set -eu
umask 077

usage() {
    cat >&2 <<'EOF'
Usage: [HERMES_BOOTSTRAP_ADMIN_TOKEN_FILE=/path/to/admin-token] \
    scripts/setup-docker-secrets.sh

If HERMES_BOOTSTRAP_ADMIN_TOKEN_FILE is omitted, a random admin token is
generated in the current user protected state directory:
  ~/.local/state/cti-hermes/admin-token
An analyst service token is generated separately for the Hermes analyst profile.

When a token file is supplied, it must be readable by the user running this
script and protected outside the repository. The other required values are
generated locally and written to the protected Compose secret directory.

Optional environment variable:
  HERMES_SECRET_DIR  Secret directory used by standalone Docker Compose
EOF
    exit 2
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
    usage
fi

user_home=${HOME:-}
if [ -z "$user_home" ] || [ ! -d "$user_home" ]; then
    echo "HOME must name the current user home directory" >&2
    exit 1
fi

state_root=${XDG_STATE_HOME:-$user_home/.local/state}
default_admin_input="$state_root/cti-hermes/admin-token"
admin_input=${HERMES_BOOTSTRAP_ADMIN_TOKEN_FILE:-$default_admin_input}
admin_generated=0
secret_dir=${HERMES_SECRET_DIR:-$state_root/cti-hermes/secrets}

if [ -z "${HERMES_BOOTSTRAP_ADMIN_TOKEN_FILE:-}" ] && [ ! -e "$admin_input" ]; then
    mkdir -p "$(dirname "$admin_input")"
    openssl rand -hex 32 >"$admin_input"
    chmod 600 "$admin_input"
    admin_generated=1
fi

if [ ! -f "$admin_input" ] || [ ! -r "$admin_input" ]; then
    echo "Admin token file must be a readable regular file: $admin_input" >&2
    echo "Run this script as the file owner or provide a user-readable path" >&2
    usage
fi

mkdir -p "$secret_dir"
chmod 700 "$secret_dir"
for secret_file in \
    "$secret_dir/postgres-password" \
    "$secret_dir/database-url" \
    "$secret_dir/admin-token" \
    "$secret_dir/analyst-token" \
    "$secret_dir/application-secret" \
    "$secret_dir/backup-key"
do
    if [ -e "$secret_file" ]; then
        echo "Refusing to overwrite existing secret file: $secret_file" >&2
        exit 1
    fi
done

temp_dir=$(mktemp -d /tmp/cti-hermes-secrets.XXXXXX)
cleanup() {
    rm -rf "$temp_dir"
}
trap cleanup EXIT HUP INT TERM

# Generate URL-safe hexadecimal values so the database password can be used
# in a URL without additional escaping.
openssl rand -hex 32 >"$temp_dir/postgres-password"
openssl rand -hex 32 >"$temp_dir/application-secret"
openssl rand -hex 32 >"$temp_dir/backup-key"

# Strip line endings from the selected token without displaying it.
tr -d '\r\n' <"$admin_input" >"$temp_dir/admin-token"
openssl rand -hex 32 >"$temp_dir/analyst-token"
if [ ! -s "$temp_dir/admin-token" ]; then
    echo "The admin token file is empty" >&2
    exit 1
fi

IFS= read -r postgres_password <"$temp_dir/postgres-password"
printf 'postgresql+asyncpg://hermes:%s@postgres:5432/hermes' "$postgres_password" \
    >"$temp_dir/database-url"

install_secret_file() {
    source_file=$1
    target_file=$2
    cp "$source_file" "$target_file"
    # The parent directory is mode 700; Compose preserves source permissions
    # when mounting file-backed secrets for containers with different UIDs.
    chmod 644 "$target_file"
}

install_secret_file "$temp_dir/postgres-password" "$secret_dir/postgres-password"
install_secret_file "$temp_dir/database-url" "$secret_dir/database-url"
install_secret_file "$temp_dir/admin-token" "$secret_dir/admin-token"
install_secret_file "$temp_dir/analyst-token" "$secret_dir/analyst-token"
install_secret_file "$temp_dir/application-secret" "$secret_dir/application-secret"
install_secret_file "$temp_dir/backup-key" "$secret_dir/backup-key"

echo "Compose secret files created in: $secret_dir"

if [ "$admin_generated" -eq 1 ]; then
    echo "A random admin token was saved to: $admin_input"
    echo "Keep that file protected; use its value in the X-Admin-Token header."
fi
