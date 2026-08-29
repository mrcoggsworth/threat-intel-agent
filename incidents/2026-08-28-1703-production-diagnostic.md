# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 17:03:24 CDT (2026-08-28 22:03:24Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API, private operations surface, scheduler, PostgreSQL, monitor,
proxy, and backup service are available and healthy. Ingestion freshness is
degraded: the latest persisted run is failed, with 12/14 sources successful and
1,840 new documents. The two failed sources are Google Threat Analysis Group
and Microsoft Security Response Center. Partial successful-source output and
failed-source provenance are retained. There is no fully successful persisted
run. Monitoring freshness is also misleading because the application's
`last_successful()` query accepts a failed run when it has successful sources.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`, merge of PR #41
  (`feat: date-from filtering`). Working-tree changes are explained, staged
  incident evidence records; no application/config source changes were made.
- Application version: `hermes-cti 0.1.0`.
- Running web/scheduler/monitor image: mutable tag `cti-hermes:local`, image ID
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL image ID is `sha256:e013e867e712fec275706a6c51c966f0bb0c93fa8f51000f85a15f9865a28cb`;
  backup image ID is `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Web/scheduler started `2026-08-28T16:56:14Z`; PostgreSQL has run since
  `2026-08-26T23:20:36Z`. Latest repository commit is
  `2026-08-28T11:54:51-05:00`. Compose mtime is `2026-08-26 20:14:30 -0500`;
  source registry mtime is `2026-08-16 15:36:31 -0500`.
- Compose validation passed. Compose SHA-256 is
  `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`;
  source registry SHA-256 is
  `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.

## Service, restart, and resource state

- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  Worker and runtime-init exited 0 as designed; worker restart policy is `no`.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, monitor 3 during
  startup-check churn, worker 0. Checked services report `OOMKilled=false`.
- Scheduler heartbeat was `2026-08-28T22:02:46Z` at the final probe. Recent
  Docker events were healthcheck/exec activity; no current lifecycle churn.
- Nginx is active, `NRestarts=0`, and the application remains loopback-published
  on `127.0.0.1:18000`; no proxy outage was found.
- Host capacity is normal: root filesystem 504G total / 175G used / 308G free
  (37%), 62GiB RAM with about 57GiB available, swap unused, kernel file table
  3,104 allocated, and application containers below 150MiB. No disk, memory,
  or file-descriptor pressure is indicated.

## Health, readiness, proxy, and certificate

- Loopback and private `/health/ready` return HTTP 200 with
  `configuration=ok` and `database=ok`; `/health/live` and `/version` return
  HTTP 200. Authenticated operations endpoints return current readiness,
  scheduler heartbeat, version `0.1.0`, and last-success timestamp.
- TLS verifies for `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt `YE1`,
  valid `2026-08-18T14:30:37Z` through `2026-11-16T14:30:36Z`, fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migrations, backup, and integrity

- PostgreSQL 16.14 accepts connections. Current Alembic revision is
  `0013_op_retention`, matching repository head `0013_op_retention`; no pending
  or failed migration was evidenced and no migration was run.
- Latest run ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7` started
  `2026-08-28T16:56:16.219818Z` and completed `2026-08-28T16:56:18.054359Z`.
  It is `failed`: 14 total / 12 successful / 2 failed / 1,840 new documents.
  Failed rows are Google TAG (`http_error`, HTTP 404) and MSRC
  (`malformed_xml`, XML could not be parsed). The operations endpoint reports
  this failed run's completion time as `last_success`.
- Counts are 1,885 source documents, 61 raw artifacts, 1,908 evidence claims,
  3,494 indicators, 453 reports, and 454 publications. Existing FK/evidence
  relationship checks from the preceding diagnostic remain clean; no empty
  database or corruption evidence was found.
- Latest encrypted backup is
  `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, mode 600.
  SHA-256 is
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`, matching
  its mode-600 metadata. Backup container is healthy. No restore was attempted.

## Cause assessment

- Configured Google TAG URL
  `https://blog.google/threat-analysis-group/rss/` returns HTTP 404 HTML.
- Configured MSRC URL `https://msrc.microsoft.com/blog/feed` redirects to
  `https://www.microsoft.com/en-us/msrc/blog` and returns HTTP 200 HTML rather
  than RSS/XML.
- **High confidence, causal:** two enabled upstream endpoints no longer satisfy
  the RSS/XML adapter contract, deterministically failing each scheduled run
  while preserving partial results and source failure provenance.
- **High confidence, contributing:** `RunRepository.last_successful()` includes
  `status=failed` when `successful_sources > 0`, falsely signaling freshness.
- **Low/not causal:** web, proxy, scheduler process/heartbeat, PostgreSQL,
  migrations, disk, memory, file descriptors, certificate, backup creation,
  publication persistence, and current container crash-loop state.
- **Medium operational risk, not proven causal:** mutable image tag and absent
  release approval/rollback metadata weaken release defensibility.

## Actions and approvals

- **Action taken:** read-only preflight, fresh Compose validation, live endpoint
  and TLS checks, authenticated operations checks, source probes, container/log/
  event/resource checks, migration and database checks, backup hash/metadata
  verification, and this incident record.
- **No operational mutation:** no restart, migration, rollback, restore,
  credential operation, source disablement, configuration edit, Nginx reload,
  Docker prune, volume deletion, or publication/data mutation.
- **Smallest reversible action:** no operational action. Restart cannot repair
  deterministic upstream endpoint failures and could obscure evidence.
- **Service/data state:** service available but degraded for ingestion freshness
  and alert correctness; data integrity preserved and inspected relationships
  remain clean.
- **Rollback:** not attempted. No reviewed compatible immutable target or
  current approval reference is documented.
- **Approvals required:** approval of replacement source URLs/adapters and any
  code/image change; approval for restart, migration, restore, credential,
  proxy, or deployment operations. Destructive recovery remains unauthorized
  and unnecessary.

## Prevention and follow-up

1. Review and approve replacement URLs/adapters for Google TAG and MSRC; add
   mocked 404, redirect-to-HTML, and malformed-feed fixtures.
2. Require `status=completed` for `last_successful`; add regression coverage for
   partial versus total failure and distinct partial-failure alerts.
3. Require immutable image digests and release records containing commit,
   Compose/config hash, migration revision, approval, and rollback target.
4. Run an approved isolated encrypted-backup restore rehearsal; never target
   production.

**Incident record:** this file. No external issue/PR was created because no
issue target or approval reference was supplied; the local record is the
maintenance handoff for review.
