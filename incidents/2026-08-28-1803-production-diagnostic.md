# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 18:02:40 CDT (2026-08-28 23:02:40Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API, private proxy ingress, scheduler, PostgreSQL, monitor, and backup
services are available and healthy. Ingestion remains degraded: the newest
persisted collection run is failed, with 12/14 sources successful and 1,840
new documents. Google Threat Analysis Group and Microsoft Security Response
Center continue to fail. Existing partial evidence is persisted. There is no
fully successful run in the database, so source-freshness and last-success
alerting are not trustworthy. No public portal outage was observed.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`, matching `main` and
  `origin/main`; merge of PR #41. Existing working-tree changes are staged
  incident records only; no application/deployment source changes overlap this
  diagnosis.
- Application version: `hermes-cti 0.1.0`.
- Web, scheduler, and monitor image ID:
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  The local `cti-hermes:local` tag resolves to repo digest
  `cti-hermes@sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL and backup are PostgreSQL 16 images.
- Compose SHA-256:
  `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`.
  Source registry SHA-256:
  `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.
  HEAD commit time is 2026-08-28 11:54:51 CDT; containers started at about
  2026-08-28 11:56 CDT. Current production compose validation from the available
  env file failed because required `HERMES_SECRET_DIR` was not supplied; this
  is a maintenance preflight/configuration gap, not evidence that the running
  stack is down.

## Runtime and host evidence

- `cti-hermes-web-1`, `cti-hermes-scheduler-1`, `cti-hermes-postgres-1`,
  `cti-hermes-backup-1`, and `cti-hermes-monitor-1` are running and healthy.
  `cti-hermes-worker-1` exited 0 by design (`restart=no`) after reporting that
  it is reserved for a later analysis phase.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0,
  monitor 3. Monitor restarts were startup-check churn; no continuing crash
  loop or OOM kill was observed. Recent Docker events were healthcheck/exec
  activity only; no container restart events were observed.
- Scheduler process is alive for about six hours and its heartbeat was
  `2026-08-28T23:01:47Z`; scheduler healthcheck is passing. The last collection
  remains the 16:56 UTC run, consistent with the configured daily schedule,
  whose next nominal UTC hour is 02:00.
- Host capacity is normal: root 504G total / 175G used / 308G free (37%),
  62GiB RAM with about 58GiB available, swap unused, kernel file table 2,688.
  Application FD counts were low; no disk, memory, or file-descriptor pressure
  is indicated.

## Health, proxy, and certificate

- Loopback `/health/live`, `/health/ready`, and `/version` returned HTTP 200.
  External `/health/ready` and `/version` also returned HTTP 200 with
  configuration and database checks OK.
- Host Nginx is active since 2026-08-26 18:20:33 CDT with `NRestarts=0`.
  The external `/health/live` path returns Nginx 404 because it is not in the
  configured proxy allowlist; this is expected and does not match the internal
  liveness route.
- TLS verification succeeded for `CN=matrix-1.taild27e3c.ts.net`, Let's
  Encrypt issuer `YE1`, valid 2026-08-18 14:30:37Z through 2026-11-16
  14:30:36Z, SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migrations, backup, and integrity

- PostgreSQL 16 is accepting connections. Current Alembic revision is
  `0013_op_retention`; `uv run alembic heads` reports the same single head.
  No migration was run and no pending/failed migration was evidenced.
- Runs remain: latest ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7`, started
  `2026-08-28T16:56:16.219818Z`, completed
  `2026-08-28T16:56:18.054359Z`, status `failed`, 14 total / 12 successful /
  2 failed / 1,840 new documents. Failed sources are Google TAG (`http_error`,
  HTTP 404) and MSRC (`malformed_xml`). Historical runs are also failed; query
  of `status='completed'` returns zero rows.
- Current counts are 1,885 source documents, 61 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks
  for entity evidence, relationship evidence, and current report versions all
  returned zero. No empty database or corruption evidence was found.
- Latest encrypted backup is
  `hermes-20260828T165615Z.dump.enc`, completed 2026-08-28T16:56:16Z, 3,507,536
  bytes, mode 600, SHA-256
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  `latest.metadata` is present, mode 600, and matches the artifact metadata.
  Backup container is healthy. No restore was attempted.

## Cause assessment

- **High confidence, causal:** configured Google TAG RSS URL currently returns
  HTTP 404 HTML; configured MSRC feed redirects to an HTML blog page. Direct
  probes reproduced both failures. These violate the RSS/XML adapter contract
  and explain the repeatable two-source failure and failed partial runs.
- **High confidence, contributing:** the application freshness path treats a
  failed partial run with successful sources as `last_success`; the database
  has no fully successful run. This can mask the outage in operations checks.
- **Low/no evidence as causes:** web/API, proxy, scheduler liveness,
  PostgreSQL, migrations, disk, memory, file descriptors, certificate,
  backup, publication persistence, and container crash state.
- **Medium operational risk:** the running deployment uses a mutable local tag,
  and current compose validation lacks `HERMES_SECRET_DIR`; release
  provenance/defensibility is weaker than the repository policy requires.

## Actions and approvals

- **Action taken:** read-only preflight, live and readiness probes, TLS
  inspection, Nginx/service checks, container/restart/event/log review, host
  resource checks, source endpoint probes, PostgreSQL/migration/integrity
  queries, image/config identity checks, and backup metadata verification.
- **No operational mutation:** no restart, migration, rollback, restore,
  credential operation, source disablement, config edit, Nginx reload, Docker
  prune, volume deletion, or publication/data mutation.
- **Smallest reversible action:** no action is safe/useful without an approved
  source replacement or code fix. Restart would not repair deterministic
  upstream endpoint contract failures and could obscure evidence.
- **Service/data-integrity state:** service is available but degraded for
  ingestion freshness and alert correctness; persisted partial output and
  provenance remain intact.
- **Rollback:** not attempted. No approved immutable compatible rollback target
  or approval reference is documented; rollback is not indicated by evidence.
- **Approvals required:** approve replacement source URLs/adapters and any
  code/image change. Separately approve restart, migration, restore,
  credential, proxy, or deployment operations. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Approve replacement URLs/adapters for Google TAG and MSRC; add mocked 404,
   redirect-to-HTML, and malformed-feed fixtures.
2. Make `last_successful()` require `status='completed'`; add regression tests
   and alerting for partial versus fully successful runs.
3. Require immutable image digests and a release record containing commit,
   Compose/config hashes, migration revision, approval, and rollback target.
4. Repair the deployment env/preflight so `HERMES_SECRET_DIR` is explicitly
   supplied, without exposing secret contents, and validate Compose in CI.
5. Run an approved isolated encrypted-backup restore rehearsal; do not target
   production.
6. Add a privileged Nginx config-test check to maintenance automation so
   root-only TLS-key permissions are tested without weakening key access.

**Incident record:** this file. No external issue/PR was created because no
issue target or approval reference was supplied; this local record is the
maintenance handoff for review.
