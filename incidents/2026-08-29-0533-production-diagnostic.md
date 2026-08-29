# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 05:32 UTC (2026-08-29 00:32 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The public portal, web/API liveness, private readiness, scheduler, PostgreSQL,
and backup containers are operational. Ingestion is degraded: all six recorded
runs are `failed`; no run has status `completed`. The latest run,
`4f8db05e-c29a-5c80-bfe0-464edad4a18`, started 2026-08-29 02:00:00.091Z and
completed 02:00:01.945Z with 12/14 sources successful, 2 failed, and 110 new
documents. Successful-source documents and partial-run provenance remain
persisted. The affected feeds have freshness risk; unaffected sources continue
to ingest.

## Identity and release

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD
  `a84a20340aad85bcb1777928dc2f7270468eec17`.
- Working-tree changes are incident records only; no overlapping application,
  migration, Compose, or source edits were found before this record.
- Running image: `cti-hermes:local`; image ID/content digest
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`;
  created 2026-08-28T11:55:53-05:00. Compose image label digest is
  `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`.
  The mutable tag remains a reproducibility concern.
- Application `/version`: `hermes-cti 0.1.0`.
- Production env file: `/opt/cti-hermes/env/production.env`, mode 600,
  mtime 2026-08-25 17:20:29-05:00; contents were not read.
- Latest repository commits include portal date filtering at
  `bd3e3fddfb039f866ef1053001ca8ffafa2a6bd3` and merge HEAD above. No formal
  approval/release record was found in the repository snapshot.

## Service, proxy, certificate, and resources

- Verified with certificate validation: public `:9443/health/live` and
  `/reports`, private `:9444/health/ready` and `/version` all returned HTTP
  200. Direct application `127.0.0.1:18000` liveness/readiness/version/portal
  checks also returned 200.
- TLS certificate is Let's Encrypt `YE1`, CN
  `matrix-1.taild27e3c.ts.net`, valid 2026-08-18T14:30:37Z through
  2026-11-16T14:30:36Z; SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  Worker exited 0 as designed (`restart: no`) and is unhealthy after exit.
  Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0,
  monitor 3. All sampled CTI containers report `OOMKilled=false`.
- Scheduler heartbeat is fresh: 21 bytes, mode 644, value
  `2026-08-29T05:32:50Z`.
- Host capacity is normal: root 504G/175G/308G available (37% used), 62GiB
  RAM with 58GiB available, swap unused, and `/proc/sys/fs/file-nr` reports
  2464 allocated descriptors with an effectively unlimited system ceiling.
- Nginx is active, `NRestarts=0`, `ExecMainStatus=0`, with no journal entries
  in the sampled 48-hour window. Docker lifecycle sampling found no CTI
  restart/crash events; healthcheck/exec activity is present.

## Database, migrations, backup, and integrity

- PostgreSQL 16.14 accepts connections; database size is 36,199,447 bytes.
  Observed migration revision is `0013_op_retention`, matching repository
  migration head `0013_op_retention`; no pending or failed migration is
  evidenced and no migration was run.
- Run counts: 6 failed, 0 completed, 0 running, 0 scheduled. Latest source
  failures are Google TAG `http_error` with HTTP 404 and MSRC
  `malformed_xml` (`XML payload could not be parsed`). The other 12 sources
  completed with HTTP 200 or 304.
- Current counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks
  for entity evidence, relationship evidence, and report current-version
  references each returned 0.
- Latest encrypted backup is
  `/backups/hermes-20260828T165615Z.dump.enc`, metadata/artifact completion
  2026-08-28 16:56:16Z, 3,507,536 bytes, mode 600. Recomputed SHA-256 matched
  metadata: `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Backup healthcheck is healthy. No restore was attempted; the latest backup
  is older than the current ingestion run and no isolated restore rehearsal
  was performed.

## Cause assessment

- **High confidence, causal:** the two enabled source contracts are stale or
  invalid. Direct probes returned Google TAG HTTP 404 with HTML and MSRC HTTP
  301 to `https://www.microsoft.com/en-us/msrc/blog` with HTML rather than an
  RSS/XML feed. This exactly matches the repeated source-run classifications
  and explains the partial failed runs.
- **High confidence, contributing:** no fully successful run is recorded,
  creating freshness and downstream publication risk for the two feeds.
- **Medium confidence, operational:** mutable `cti-hermes:local` deployment
  tag and absent formal approval record weaken release reproducibility but do
  not explain the upstream failures.
- **Low/no evidence:** web, proxy, scheduler, database, migration, disk,
  memory, file descriptor exhaustion, TLS, backup integrity, publication
  persistence, or data corruption failure.
- **Security finding:** secret files were not read. Prior inspection indicates
  secret-file mode hardening remains a maintenance item; no credential was
  printed or rotated.

## Actions and approvals

- Completed read-only probes for release identity, container state and
  restart history, logs, Docker events, ingress/application health, TLS,
  resources, database/revision/integrity, source contracts, Compose
  validation, and backup metadata/hash. Compose validation passed with
  explicit `HERMES_IMAGE=cti-hermes:local` and the protected secret directory.
- Executed the monitor check once; it exited 0. No restart, migration,
  rollback, restore, proxy reload, source edit/disablement, credential action,
  Docker prune, volume operation, or data/publication mutation was performed.
- Smallest reversible action: **no restart**. Restart cannot repair the two
  upstream contracts and could obscure evidence.
- Incident record created at this path. No external issue/PR destination was
  supplied.

## State, rollback, and prevention

- Service state: operational web/API, portal, readiness, scheduler heartbeat,
  PostgreSQL, backup, and monitor; ingestion degraded for two sources.
- Data-integrity state: no corruption or orphan references found; partial
  successful results and provenance retained; encrypted backup exists and
  checksum verification passed.
- Rollback/recovery: not performed and not required. No approved immutable
  compatible rollback target was documented. Destructive recovery remains
  unauthorized.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with
  404, redirect-to-HTML, malformed-XML, and partial-run fixtures; retain
  explicit partial-run semantics; reconcile monitor route checks with Nginx
  policy; require immutable image digests and approval/release records; fix
  secret file modes through approved maintenance; verify the next backup and
  conduct an approval-gated isolated restore rehearsal.

Approvals are required for source/config or code release, restart, migration,
restore, proxy reload, credential operations, deployment, or rollback.
