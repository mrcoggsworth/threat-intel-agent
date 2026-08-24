# CTI-Hermes production deployment

This package prepares, but does not perform, a Docker Compose deployment. It
expects Docker Engine and the Compose plugin on the existing Linux home-lab
server. The application image is the same immutable HERMES_IMAGE for web,
worker, scheduler, monitor, and the controlled migration service.

## Prerequisites

Use an absolute checkout such as /opt/cti-hermes/app, a root-readable
environment file outside the repository, a restricted backup destination, DNS
for the public and private hostnames, synchronized UTC time, and TLS files in
the hermes-proxy-tls named volume. Do not commit an environment file or secret.

Create external Docker secrets out of band:

    printf '%s' '...' | docker secret create cti-hermes-postgres-password -
    printf '%s' 'postgresql+asyncpg://hermes:PASSWORD@postgres:5432/hermes' | docker secret create cti-hermes-database-url -
    printf '%s' '...' | docker secret create cti-hermes-admin-token -
    printf '%s' '...' | docker secret create cti-hermes-secret-key -
    printf '%s' '...' | docker secret create cti-hermes-backup-key -

The values above are examples of categories only. Use a protected secret
manager or operator-controlled input and never paste values into this file,
logs, prompts, or chat. The database URL secret is read through
HERMES_DATABASE_URL_FILE; the application does not require a secret in its
Compose YAML.

Populate the named TLS volume with fullchain.pem and privkey.pem using the
approved certificate process. Confirm the private hostname resolves only from
the management/VPN network.

## First bootstrap

    cp deploy/.env.example /opt/cti-hermes/env/production.env
    # edit only non-secret values and set HERMES_IMAGE to the approved digest
    docker compose --env-file /opt/cti-hermes/env/production.env -f deploy/docker-compose.yml config
    docker compose --env-file /opt/cti-hermes/env/production.env -f deploy/docker-compose.yml up -d postgres
    docker compose --env-file /opt/cti-hermes/env/production.env -f deploy/docker-compose.yml run --rm migrate
    docker compose --env-file /opt/cti-hermes/env/production.env -f deploy/docker-compose.yml up -d web worker scheduler backup monitor proxy
    scripts/smoke-test.sh PUBLIC_URL PRIVATE_URL ADMIN_TOKEN_FILE

Do not start production until the image, secrets, TLS, backup destination,
firewall, and approval gates are verified. The first bootstrap must be
performed by an authorized operator.

## Approved deployment

Only after an approved release and explicit authorization in the current
request:

    HERMES_DEPLOY_APPROVED=true HERMES_APPROVAL_REFERENCE=APPROVAL-ID \
    HERMES_ENV_FILE=/opt/cti-hermes/env/production.env \
    HERMES_IMAGE=ghcr.io/mrcoggsworth/threat-intel-agent@sha256:DIGEST \
    scripts/deploy-approved.sh

The script validates the image reference, validates Compose, runs a fresh
encrypted backup, applies the one-shot migration, starts the stack, and runs
the smoke test. A failed smoke test restores the prior recorded image and
re-runs the smoke test. It does not reverse an irreversible migration.
Automatic rollback is allowed only within this approved deployment workflow.

## Backup and recovery

The backup service writes encrypted PostgreSQL custom-format dumps to the
hermes-backups named volume and retains the configured generations. A backup
is accepted only after pg_restore listing and SHA-256 metadata succeed.

For an isolated restore rehearsal, copy a selected artifact to a restricted
operator path and run:

    scripts/restore-verify.sh /restricted/path/hermes-YYYYmmddTHHMMSSZ.dump.enc /path/key /path/password

The script starts a disposable PostgreSQL container, restores into it,
checks alembic_version and table sanity, then removes only that disposable
container. It never targets the production volume.

## Operations

The web container has no host port, Docker socket, repository write mount, or
migration side effect. PostgreSQL is private and has no host port. Public
requests reach only the proxy; public requests for admin and operations paths
return 404. The private proxy hostname is restricted to RFC1918 management
ranges and still requires the application admin token.

Use scripts/health-watchdog.sh from a script-only Hermes cron job. It checks
liveness, readiness, scheduler heartbeat, last-success endpoint, backup age,
disk threshold, PostgreSQL container health, and certificate expiry. It prints
nothing when healthy and exits nonzero on failure.

The worker is present as a separate same-image service, but the current
application scheduler owns the Phase 4 daily pipeline and the worker CLI
remains an idle reserved entrypoint. Queue-backed worker execution is not
claimed by this phase and no Redis/Celery dependency is introduced.
