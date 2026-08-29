# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 17:48:36 CDT (2026-08-28 22:48:36Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The API, private proxy surface, scheduler, PostgreSQL, monitor, and backup
container are available. Ingestion is degraded: the latest and all five
persisted ingestion runs are `failed`; the latest run completed with 12/14
sources successful and 1,840 new documents. Google Threat Analysis Group and
Microsoft Security Response Center failed. Existing partial output and source
failure provenance remain persisted. No fully successful run exists in the
current database. The external `/health/live` URL returns Nginx 404 by design
(the configured proxy allowlist exposes `/health/ready`, `/version`, and
private operations paths); loopback `/health/live` is 200.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17` (merge of PR #41).
  Working-tree changes are three staged incident records only; no application
  or deployment source changes overlap this diagnosis.
- Application version: `hermes-cti 0.1.0`.
- Web, scheduler, and monitor image: mutable `cti-hermes:local`, image ID
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  No registry digest is attached. PostgreSQL and backup are PostgreSQL 16
  images. Image containers were created at approximately 2026-08-28 16:56Z.
- Compose SHA-256: `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`.
  Source registry SHA-256: `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.
  Compose mtime is 2026-08-26 20:14:30 CDT; source registry mtime is
  2026-08-16 15:36:31 CDT. Production environment file mtime is
  2026-08-25 17:20:29 CDT.

## Service, restart, resource, and event state

- `cti-hermes-web-1`, `cti-hermes-scheduler-1`, `cti-hermes-postgres-1`,
  `cti-hermes-backup-1`, and `cti-hermes-monitor-1` are running and healthy.
  Worker exited 0 with restart policy `no`, consistent with the one-shot
  worker design; runtime-init also exited 0.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0,
  monitor 3. Monitor restarts were startup-check churn; no continuing
  lifecycle churn was present. OOMKilled is false for application services.
- Scheduler heartbeat at capture: `2026-08-28T22:47:17Z`. Recent Docker events
  were healthcheck/exec activity, not service crash/restart activity.
- Host capacity is normal: root filesystem 504G total / 175G used / 308G free
  (37%); 62GiB RAM with about 58GiB available; swap unused; kernel file table
  2,688 allocated; process/container FD counts were low (web 14, scheduler 7,
  PostgreSQL 10). No disk, memory, or FD pressure is indicated.

## Health, readiness, proxy, and certificate

- Loopback `/health/live`, `/health/ready`, and `/version` all returned HTTP
  200. External `/health/ready` and `/version` returned HTTP 200. External
  `/health/live` returned the expected Nginx HTTP 404 because it is not in the
  proxy location allowlist. Readiness reported configuration and database OK.
- Nginx is active since 2026-08-26 18:20:33 CDT with `NRestarts=0`. An
  unprivileged `nginx -t` could not read the root-only key and reported
  permission denied; this is not evidence of an active outage because the
  root-owned service is running and the live TLS probe succeeds. A root
  validation could not be run without sudo approval.
- TLS verifies for `CN=matrix-1.taild27e3c.ts.net`, Let's Encrypt issuer `YE1`,
  validity 2026-08-18T14:30:37Z through 2026-11-16T14:30:36Z, SHA-256
  fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity

- PostgreSQL 16 accepts connections; current Alembic revision is
  `0013_op_retention`, matching repository head. No pending or failed
  migration was evidenced; no migration was run.
- Latest run ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7` started
  `2026-08-28T16:56:16.219818Z` and completed `2026-08-28T16:56:18.054359Z`.
  It is failed: 14 total / 12 successful / 2 failed / 1,840 new documents.
  Failed source rows are Google TAG (`http_error`, HTTP 404) and MSRC
  (`malformed_xml`, XML could not be parsed). Querying only `status=completed`
  returned no rows, so there is no last fully successful run. The known
  monitoring bug remains: `last_successful()` can treat a partially successful
  failed run as freshness.
- Current counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. All foreign
  keys are validated; no unvalidated FK constraints were returned. No empty
  database or corruption evidence was found.
- Latest encrypted backup: `hermes-20260828T165615Z.dump.enc`, 3,507,536
  bytes, mode 600, SHA-256
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Metadata is mode 600 and `latest.metadata` matches the latest metadata hash.
  Backup container is healthy. No restore was attempted.

## Cause assessment

- **High confidence, causal:** Google TAG's configured RSS URL returns HTTP
  404 HTML, and MSRC's configured feed URL redirects to an HTML blog page
  rather than RSS/XML. Both violate the configured RSS/XML adapter contract,
  explaining the repeatable two-source failures and partial run status.
- **High confidence, contributing:** freshness logic accepts a failed run when
  `successful_sources > 0`, so operations can report a failed partial run as
  `last_success`.
- **Not causal / low evidence:** web, proxy availability, scheduler heartbeat,
  PostgreSQL, migrations, disk, memory, file descriptors, certificate,
  backups, publication persistence, and current container crash state.
- **Medium operational risk:** mutable local image tag and missing release
  approval/rollback metadata reduce release defensibility, but are not shown
  to cause this incident.

## Actions and approvals

- **Action taken:** read-only preflight, repository/status review, live and
  loopback health probes, TLS inspection, Nginx/service checks, container
  state/restart/event/log review, resource checks, source endpoint probes,
  database/migration/integrity checks, and backup metadata/hash verification.
- **No mutation:** no restart, migration, rollback, restore, credential
  operation, source disablement, config edit, Nginx reload, Docker prune,
  volume deletion, or publication/data mutation.
- **Smallest reversible action:** no operational action. Restart cannot repair
  deterministic upstream endpoint contract failures and could obscure evidence.
- **Service/data-integrity state:** service available but degraded for source
  freshness and alert correctness; persisted partial evidence is intact.
- **Rollback:** not attempted. No reviewed compatible immutable rollback target
  or current approval reference is documented.
- **Approvals required:** approve replacement source URLs/adapters and any
  code/image change; separately approve restart, migration, restore,
  credential, proxy, or deployment operations. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Review and approve replacement URLs/adapters for Google TAG and MSRC; add
   mocked 404, redirect-to-HTML, and malformed-feed fixtures.
2. Require `status=completed` for `last_successful()` and add regression tests
   distinguishing partial from fully successful runs and alerting accordingly.
3. Require immutable image digests and a release record containing commit,
   Compose/config hashes, migration revision, approval, and rollback target.
4. Run an approved isolated encrypted-backup restore rehearsal; never target
   production.
5. Add a privileged Nginx config-test check to maintenance automation so the
   root-only TLS-key permission caveat is tested without weakening key access.

**Incident record:** this file. No external issue/PR was created because no
issue target or approval reference was supplied; this local record is the
maintenance handoff for review.
