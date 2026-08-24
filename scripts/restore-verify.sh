#!/bin/sh
set -eu

backup_file="${1:?usage: restore-verify.sh BACKUP_FILE [KEY_FILE] [PASSWORD_FILE]}"
key_file="${2:-${BACKUP_ENCRYPTION_KEY_FILE:-}}"
password_file="${3:-${POSTGRES_PASSWORD_FILE:-}}"
[ -r "$backup_file" ] || { echo "backup file is not readable" >&2; exit 2; }
[ -r "$key_file" ] || { echo "encryption key file is required" >&2; exit 2; }
[ -r "$password_file" ] || { echo "database password file is required" >&2; exit 2; }

target="${RESTORE_TARGET_CONTAINER:-hermes-restore-$$}"
image="${POSTGRES_IMAGE:-postgres:16-alpine}"
restore_file="/tmp/hermes-restore-$$"
password=$(cat "$password_file")
cleanup() { docker rm --force "$target" >/dev/null 2>&1 || true; }
trap 'rm -f "$restore_file"; cleanup' EXIT

docker run --detach --rm --name "$target" \
    --env POSTGRES_PASSWORD="$password" --env POSTGRES_USER=hermes \
    --env POSTGRES_DB=hermes "$image" >/dev/null
for attempt in $(seq 1 60); do
    docker exec "$target" pg_isready -U hermes -d hermes >/dev/null 2>&1 && break
    [ "$attempt" -eq 60 ] && { echo "isolated PostgreSQL did not become ready" >&2; exit 1; }
    sleep 1
done

openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -pass file:"$key_file" \
    -in "$backup_file" -out "$restore_file"
docker cp "$restore_file" "$target:/tmp/hermes-restore.dump" >/dev/null
docker exec -e PGPASSWORD="$password" "$target" \
    pg_restore --no-owner --no-acl --dbname=postgresql://hermes@127.0.0.1:5432/hermes \
    /tmp/hermes-restore.dump
docker exec -e PGPASSWORD="$password" "$target" psql \
    --username=hermes --dbname=hermes --tuples-only --no-align \
    --command="SELECT count(*) FROM alembic_version" >/tmp/hermes-restore-revision
grep -Eq '^[0-9a-f]+' /tmp/hermes-restore-revision
docker exec -e PGPASSWORD="$password" "$target" psql \
    --username=hermes --dbname=hermes --tuples-only --no-align \
    --command="SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" |
    awk '$1 >= 1 {ok=1} END {exit ok ? 0 : 1}'
rm -f /tmp/hermes-restore-revision
echo "isolated restore verification passed"
