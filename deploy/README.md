# CTI-Hermes internal deployment

This deployment is internal-only. The sanitized portal is not exposed to the public Internet.

This package prepares, but does not perform, an internal-only Docker Compose
deployment behind the existing host-level Nginx. It expects Docker Engine and
the Compose plugin on the existing Linux home-lab server. Host Nginx remains
the only TLS and ingress proxy for Hermes and llama.cpp; the Hermes web
container is published only on a loopback port for that host proxy. The
application image is the same immutable HERMES_IMAGE for web, worker,
scheduler, monitor, and the controlled migration service.

Read [INTERNAL_ACCESS_MATRIX.md](INTERNAL_ACCESS_MATRIX.md) before exposing
host Nginx to the LAN or Tailscale interface, and complete
[OPERATIONS_ACCEPTANCE.md](OPERATIONS_ACCEPTANCE.md) before deployment.

## Prerequisites

Use an absolute checkout such as /opt/cti-hermes/app, a protected
environment file outside the repository, a protected Compose secret directory,
a restricted backup destination, internal DNS for the private hostnames,
synchronized UTC time, and TLS files managed by the host Nginx installation.
Do not commit an environment file or secret.

Create protected file-backed Compose secrets with the normal user:

    scripts/setup-docker-secrets.sh

This creates separate admin and analyst tokens. The analyst token is mounted
only into the web service and must be installed at the Hermes profile path
configured by `HERMES_ANALYST_SERVICE_TOKEN_FILE`.

By default the helper stores them under
`~/.local/state/cti-hermes/secrets/`. Set `HERMES_SECRET_DIR` if you want a
different protected directory. The files are mounted into containers under
`/run/secrets/`; their values are never written to the repository, logs,
prompts, or chat.

Configure the existing host Nginx with an upstream to
127.0.0.1:${HERMES_WEB_PORT:-18000}. The analyst API is served on
`https://matrix-1.taild27e3c.ts.net:9443` and the web container remains
loopback-only. Confirm the dashboard and API hostname resolve only from the
LAN/Tailscale network.
The configured private hostname is `ops.cti-hermes.home.arpa`; provide local
DNS or `/etc/hosts` resolution for it.
Keep HERMES_WEB_BIND_ADDRESS set to 127.0.0.1 so the application is never directly
reachable from the network.

## First bootstrap

    cp deploy/.env.example /opt/cti-hermes/env/production.env
    # edit only non-secret values and set HERMES_IMAGE to the approved digest
    scripts/setup-docker-secrets.sh
    scripts/start-cti-hermes-local.sh
    # Then validate the host-Nginx public and private URLs from the deployment host.

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
encrypted backup, applies the one-shot migration, starts the Compose stack,
and runs the smoke test. A failed smoke test restores the prior recorded image and
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

The web container has only a loopback host port, no Docker socket, repository
write mount, or migration side effect. PostgreSQL is private and has no host
port. All external requests reach the existing host Nginx; requests for admin
and operations paths.
require the private hostname and application admin token. Host Nginx must be restricted to RFC1918 and Tailscale ranges, while the host
firewall remains a required second control.

Use scripts/health-watchdog.sh from a script-only Hermes cron job. It checks
liveness, readiness, scheduler heartbeat, last-success endpoint, backup age,
disk threshold, PostgreSQL container health, and certificate expiry. It prints
nothing when healthy and exits nonzero on failure.

The worker is present as a separate same-image service, but the current
application scheduler owns the Phase 4 daily pipeline and the worker CLI
remains an idle reserved entrypoint. Queue-backed worker execution is not
claimed by this phase and no Redis/Celery dependency is introduced.
