#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
key_file="${BACKUP_ENCRYPTION_KEY_FILE:?BACKUP_ENCRYPTION_KEY_FILE is required}"
pgpass_file="/tmp/hermes-pgpass"
verify_file="/tmp/hermes-backup-verify-$$"
once=0
[ "${1:-}" = "--once" ] && once=1

mkdir -p "$backup_dir"
umask 077
printf '%s:%s:*:%s:%s\n' "${PGHOST:-postgres}" "${PGPORT:-5432}" "${PGUSER:-hermes}" "$(cat "${POSTGRES_PASSWORD_FILE:?POSTGRES_PASSWORD_FILE is required}")" >"$pgpass_file"
trap 'rm -f "$pgpass_file" "$verify_file"' EXIT
export PGPASSFILE="$pgpass_file"

create_backup() {
    timestamp=$(date -u +%Y%m%dT%H%M%SZ)
    artifact="$backup_dir/hermes-$timestamp.dump.enc"
    metadata="$artifact.metadata"
    started=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    pg_dump --format=custom --no-owner --no-acl \
        --host="${PGHOST:-postgres}" --port="${PGPORT:-5432}" \
        --username="${PGUSER:-hermes}" --dbname="${PGDATABASE:-hermes}" |
        openssl enc -aes-256-cbc -salt -pbkdf2 -iter 600000 \
            -pass file:"$key_file" >"$artifact"
    test -s "$artifact"
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
        -pass file:"$key_file" -in "$artifact" -out "$verify_file"
    pg_restore --list "$verify_file" >/dev/null
    rm -f "$verify_file"
    bytes=$(wc -c <"$artifact" | tr -d ' ')
    sha256=$(sha256sum "$artifact" | awk '{print $1}')

    completed=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    {
        printf 'artifact=%s\n' "$artifact"
        printf 'started=%s\n' "$started"
        printf 'completed=%s\n' "$completed"
        printf 'bytes=%s\n' "$bytes"
        printf 'sha256=%s\n' "$sha256"
    } >"$metadata"
    cp "$metadata" "$backup_dir/latest.metadata"
    find "$backup_dir" -type f -name 'hermes-*.dump.enc*' -mtime +"$retention_days" -delete
}

while :; do
    create_backup
    [ "$once" -eq 1 ] && exit 0
    sleep "${BACKUP_INTERVAL_SECONDS:-86400}"
done
