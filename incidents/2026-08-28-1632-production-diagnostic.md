# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 16:32:52 CDT (2026-08-28 21:32:52Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

CTI-Hermes web/API, private operations readiness, scheduler heartbeat,
PostgreSQL, monitor, proxy, and backup service are available. Ingestion
freshness is degraded: the latest five persisted runs are `failed`; the latest
run processed 12 of 14 sources and created 1,840 new documents. Successful
source output and failed-source provenance are retained. Public data integrity
checks performed here are clean; there is no evidence of an empty database or
corruption.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`, merge of PR #41
  (`feat: date-from filtering`). Working tree has explained staged incident
  evidence files; no application/config source changes were made.
- Application version: `hermes-cti 0.1.0`.
- Running application image: mutable tag `cti-hermes:local`; web, scheduler,
  and monitor image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL image ID is
  `sha256:e013e867e712fec275706a6c51c966f0bb0c93fa8f51000f85a15f9865a28cb`;
  backup image ID is
  `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Latest repository commit: `2026-08-28T11:54:51-05:00`. Compose file mtime:
  `2026-08-26 20:14:30 -0500`; protected production env mtime:
  `2026-08-25 17:20:29 -0500`; no later config-file change was evidenced.
- Compose validation passed using the protected secret directory and the
  currently running image tag. Config SHA-256:
  `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`.
  Source registry SHA-256:
  `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.

## Service, restart, and resource state

- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  The reserved worker and runtime-init one-shot containers exited 0 as
  designed; worker restart policy is `no`.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, monitor 3
  during startup-check churn, worker 0. Checked services have `OOMKilled=false`.
- Scheduler heartbeat was current at capture (`2026-08-28T21:31:46Z` during
  probe). Scheduler logs show source-collection failures but no crash loop.
- Nginx is active with no observed restart; loopback app port is `127.0.0.1:18000`
  and proxy listeners are `100.68.61.10:9443` and `:9444`.
- Host capacity is normal: root 504G total / 175G used / 308G available (37%),
  62GiB RAM with about 57GiB available, swap unused, host file table 3,232
  allocated, and container memory below 150MiB. No disk, memory, or FD pressure
  is indicated.
- Recent Docker events are healthcheck/exec activity only; no current
  application lifecycle churn was observed.

## Health, readiness, proxy, and certificate

- Private `:9444/health/ready`: HTTP 200 with `configuration=ok` and
  `database=ok`; `/version`: HTTP 200, version `0.1.0`.
- Private `/health/live` returns 404 due expected proxy route isolation on the
  private surface; direct container liveness probes return HTTP 200. This is
  not a service outage.
- TLS verification succeeds for `CN=matrix-1.taild27e3c.ts.net`, issuer
  Let's Encrypt `YE1`, valid `2026-08-18T14:30:37Z` through
  `2026-11-16T14:30:36Z`, SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity

- PostgreSQL 16.14 accepts connections (`pg_isready: accepting connections`).
- Current Alembic revision is `0013_op_retention`; repository head is also
  `0013_op_retention`. No pending or failed migration was evidenced; no
  migration was run.
- Latest run `43b7881e-965a-56c5-9bdd-eb0cdb207ed7`: started
  `2026-08-28T16:56:16.219818Z`, completed `2026-08-28T16:56:18.054359Z`,
  status `failed`, 14 total / 12 successful / 2 failed / 1,840 new documents.
  Last fully successful run: none. Authenticated last-success endpoint returns
  that failed run's completion time because repository code intentionally treats
  failed runs with successful sources as successful for this endpoint.
- Failed sources: Google Threat Analysis Group (`HTTP 404`) and Microsoft
  Security Response Center (`malformed_xml`, XML could not be parsed). Other
  12 sources completed HTTP 200.
- Counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence claims,
  3,494 indicators, 453 reports, 454 publications. Checked orphan counts:
  entity evidence 0, relationship evidence 0, report current-version links 0.
- Latest encrypted backup:
  `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, mode 600,
  metadata mode 600, SHA-256
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`,
  matching the metadata. Backup container is healthy. No restore was attempted.

## Failure evidence and cause assessment

- Live probe of configured Google TAG URL
  `https://blog.google/threat-analysis-group/rss/` returns HTTP 404 HTML.
- Live probe of configured MSRC URL
  `https://msrc.microsoft.com/blog/feed` redirects to
  `https://www.microsoft.com/en-us/msrc/blog` and returns HTTP 200 HTML,
  not RSS/XML.
- **High confidence, causal:** two enabled upstream endpoints no longer meet
  the RSS/XML adapter contract, deterministically failing each scheduled run
  while partial results and failure provenance are preserved.
- **High confidence, contributing:** `RunRepository.last_successful()` accepts
  `status=failed` when `successful_sources > 0` (source code lines 91-107), so
  monitoring and operations report the latest partial failed run as
  `last_success`; this can falsely signal freshness.
- **Low/not causal:** web, Nginx/proxy, scheduler process/heartbeat,
  PostgreSQL/connectivity, migrations, disk, memory, file descriptors,
  certificate, backup creation, publication persistence, and current
  container crash-loop state.
- **Medium operational risk:** mutable production image tag and absent release
  approval/rollback metadata reduce release defensibility. This is not the
  cause of the current source failures.

## Actions, integrity, rollback, and approvals

- **Action taken:** read-only preflight; fresh Compose validation; live health,
  TLS, source, database, container, log, event, resource, backup metadata/hash,
  and referential-integrity checks; incident record created.
- **No operational mutation:** no restart, migration, rollback, restore,
  credential operation, source disablement, configuration edit, Nginx reload,
  Docker prune, volume deletion, or publication/data mutation.
- **Smallest reversible action:** no operational action. Restart cannot repair
  deterministic upstream endpoint failures and could obscure evidence.
- **Service state:** available but degraded for ingestion freshness and
  freshness-alert correctness.
- **Data-integrity state:** preserved; partial successful-source results and
  failed-source provenance remain in PostgreSQL, and inspected FK checks are
  clean.
- **Rollback:** not attempted. No reviewed compatible immutable target or
  current approval reference is documented.
- **Approvals required:** review/approval of replacement source URLs or adapter
  changes, any code/image change, restart, migration, restore, credential
  operation, proxy change, or deployment. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Review and approve replacement URLs/adapters for Google TAG and MSRC; add
   mocked 404, redirect-to-HTML, and malformed-feed fixtures while retaining
   failed source-run evidence.
2. Change last-success semantics to require `status=completed` for a fully
   successful run, and add authenticated endpoint/monitor regression tests for
   partial versus total failure.
3. Alert distinctly on partial-source failures versus total pipeline failure.
4. Require immutable image digests and record commit, Compose/config hash,
   migration revision, approval, and compatible rollback target per release.
5. Run an approved isolated encrypted-backup restore rehearsal; never target
   production.

**Incident record:** this file. No external GitHub issue/PR was created because
no issue target or approval reference was supplied. The local incident record
is the maintenance handoff for human review.
