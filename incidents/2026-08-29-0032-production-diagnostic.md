# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 00:32:50Z (2026-08-28 19:32:50 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API, private ingress, scheduler heartbeat, PostgreSQL, monitor, and
backup container are available and reporting healthy. Ingestion is degraded:
the latest persisted collection run is failed (12/14 sources successful, 2
failed, 1,840 new documents). There are five failed runs and zero fully
completed runs. Partial successful-source output and failure provenance remain
persisted. The private last-success operation path is therefore not a valid
freshness signal if it reports the latest failed run. No database corruption,
publication orphaning, or public evidence deletion was found.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`; working-tree changes are
  incident records only and do not overlap application/deployment source.
- Application version: `hermes-cti 0.1.0`.
- Application image: mutable tag `cti-hermes:local`, image ID and resolved
  digest `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL is `postgres:16-alpine` (image ID
  `sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb`);
  backup is PostgreSQL 16 (image ID
  `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`).
- Latest repository commit is the 2026-08-28 11:54:51 CDT merge of PR #41.
  Compose mtime is 2026-08-26 20:14:30 CDT; source registry mtime is
  2026-08-16 15:36:31 CDT; deployment script mtime is 2026-08-25 19:44:41 CDT.
- Compose validation from the checkout could not run: `deploy/.env` is absent
  (`docker compose --env-file deploy/.env ... config --quiet` failed). This is
  a release-preflight/configuration gap, not evidence that the active stack is
  down.

## Runtime, health, and proxy evidence

- `cti-hermes-web-1`, `cti-hermes-scheduler-1`, `cti-hermes-monitor-1`,
  `cti-hermes-postgres-1`, and `cti-hermes-backup-1` are running and healthy.
  The reserved worker exited 0 with restart policy `no`; it is not an active
  queue worker by design.
- Web, scheduler, PostgreSQL, and backup restart counts are 0; monitor restart
  count is 3 during startup-check churn; all inspected application/container
  states report `OOMKilled=false`. No lifecycle restart/kill events were found
  in the 48-hour Docker event review; observed events were healthcheck/exec
  activity.
- Containers started 2026-08-28 16:56:14--16:56:16Z. Scheduler heartbeat
  healthcheck is passing. Scheduler logs contain two `source collection failed`
  messages and no crash-loop evidence.
- Loopback `/health/live`, `/health/ready`, and `/version` returned HTTP 200;
  readiness reported configuration and database `ok`, and version `0.1.0`.
  Supplied ingress `/health/ready` and `/version` returned HTTP 200. Ingress
  `/health/live` and unconfigured paths return Nginx 404 by allowlist design.
- Host Nginx is active since 2026-08-26 18:20:33 CDT with `NRestarts=0`.
  `nginx -t` fails for the unprivileged diagnostic process because it cannot
  read `/etc/nginx/ssl/tailscale/hermes.key` (permission denied). This does not
  invalidate the live TLS probe, but it is a privileged maintenance check that
  needs operator follow-up; permissions must not be weakened.
- TLS verification succeeded for `CN=matrix-1.taild27e3c.ts.net`, Let's Encrypt
  issuer `YE1`, valid 2026-08-18T14:30:37Z through 2026-11-16T14:30:36Z,
  SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Host capacity is normal: root filesystem 504G total/175G used/308G free
  (37%), 62GiB RAM with about 58GiB available, swap unused, kernel file table
  2,592 allocated, and process file-limit 4,096. No disk, memory, or FD pressure
  is indicated.

## Database, migrations, backup, and integrity

- PostgreSQL 16 accepts connections; database size is 35 MB. Production
  `alembic_version` is `0013_op_retention`, matching the repository's single
  Alembic head. No pending or failed migration is evidenced and no migration
  was run. The local `uv run alembic current` check was not usable because the
  checkout's default database configuration attempted password authentication
  as user `unused`; the production database revision query is authoritative.
- Latest run ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7`, started
  `2026-08-28T16:56:16.219818Z`, completed `2026-08-28T16:56:18.054359Z`,
  status `failed`, 14 total / 12 successful / 2 failed / 1,840 new documents.
  Failed sources: Google TAG (`http_error`, observed HTTP 404) and MSRC
  (`malformed_xml`). Historical status counts are 0 completed and 5 failed.
- Current counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks
  for entity evidence, relationship evidence, and current report versions all
  returned zero.
- Latest encrypted backup is `hermes-20260828T165615Z.dump.enc`, completed
  `2026-08-28T16:56:16Z`, 3,507,536 bytes, mode 600. `latest.metadata` is mode
  600 and its SHA-256 matches the artifact:
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Backup healthcheck is passing. No restore was attempted.

## Cause assessment

- **High confidence, causal:** the authoritative `config/sources.json` still
  configures Google TAG at `https://blog.google/threat-analysis-group/rss/`,
  which currently returns HTTP 404 HTML, and MSRC at
  `https://msrc.microsoft.com/blog/feed`, which returns HTTP 301 to an HTML
  blog page. Direct probes reproduced both failures. The supported Microsoft
  threat-intelligence feed returns RSS/XML, but changing the registry requires
  approval. These deterministic upstream/adapter-contract failures explain the
  repeated two-source partial failures.
- **High confidence, contributing:** freshness semantics are unsafe if the
  `last-success` path returns a failed run timestamp; the database has no fully
  successful run. This masks ingestion freshness failure in operations checks.
- **Low/no evidence as causes:** web/API, proxy routing, scheduler process and
  heartbeat, PostgreSQL, migration state, disk, memory, file descriptors,
  certificate validity, backup creation, publication persistence, and container
  crash state.
- **Medium operational risk:** mutable local image tag, missing checkout env for
  Compose validation, and non-privileged Nginx config-test failure weaken
  deployment defensibility but do not explain the ingestion failures.

## Actions and approvals

- Completed read-only preflight: repository identity/status, image/container
  state and restart history, Docker events/logs, local and external health
  probes, TLS inspection, host resource checks, PostgreSQL/migration/integrity
  queries, source endpoint probes, and backup metadata/checksum review.
- **No operational mutation:** no restart, migration, rollback, restore,
  credential operation, source disablement, config edit, Nginx reload, Docker
  prune, volume deletion, or publication/data mutation.
- Smallest reversible action is no action: restart cannot repair deterministic
  upstream URL/format failures and could obscure evidence. Rollback is not
  indicated; no approved immutable compatible target or approval reference is
  documented.
- Service/data-integrity state: available but ingestion-degraded; partial
  persisted evidence and provenance intact; no corruption evidence.
- Local incident record created at this path. No external issue/PR was created:
  no issue target or approval reference was supplied.
- Approvals required: approve replacement source URLs/adapters and any code or
  image change; separately approve restart, migration, restore, proxy,
  credential, or deployment operations. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Approve and validate replacement URLs/adapters for Google TAG and MSRC; add
   mocked 404, redirect-to-HTML, malformed XML, and partial-run fixtures.
2. Make `last_successful()` require `status='completed'` and distinguish
   partial ingestion from fully successful freshness in alerting.
3. Require immutable image digests and release records for commit, Compose/source
   hashes, migration revision, approval, and rollback target.
4. Supply the protected production env file to maintenance preflight and validate
   Compose in CI without exposing secret contents.
5. Run an approved isolated encrypted-backup restore rehearsal.
6. Run privileged Nginx config-test checks in maintenance automation while
   preserving private-key permissions.
