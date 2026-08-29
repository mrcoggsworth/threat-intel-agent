# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 05:49 UTC (2026-08-29 00:49 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The web/API, portal, private readiness, scheduler, PostgreSQL, backup, and
monitor surfaces are operational. Ingestion is degraded: six recorded
ingestion runs are `failed`, with no fully `completed` run. The latest run
(`4f8db05e-c29a-5c80-bfe0-464edad4a18`) ran at 2026-08-29 02:00:00Z,
finished at 02:00:01Z, processed 14 sources, succeeded for 12, failed for 2,
and persisted 110 new documents. Partial successful-source provenance remains
available; Google TAG and MSRC freshness are at risk.

## Identity and change state

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD
  `a84a20340aad85bcb1777928dc2f7270468eec17`, also `main`/`origin/main`.
- Working-tree changes are incident records only; no overlapping application,
  migration, Compose, or source edits were found.
- Application `/version`: `hermes-cti 0.1.0`.
- Running image: `cti-hermes:local`, image ID
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`,
  created 2026-08-28 11:55:53 -0500. Compose image label is
  `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`.
  The mutable tag is a release-reproducibility risk.
- Last observed deployment/container replacement: 2026-08-28 16:56:14Z.
  Production env mtime is 2026-08-25 17:20:29 -0500 (mode 600); contents were
  not read. Repository Compose/Dockerfile mtimes are 2026-08-26.
- No formal approval/release record was found in the repository snapshot.

## Service, proxy, certificate, and resource evidence

- Validated TLS ingress: public `:9443/health/live` and `/reports`, private
  `:9444/health/ready` and `/version` all returned HTTP 200. Bodies included
  `{"status":"ok"}`, readiness database/configuration `ok`, and version
  `0.1.0`. Direct `127.0.0.1:18000` health/readiness/version also returned 200.
- Nginx is active, started 2026-08-26 18:20:33 CDT, `NRestarts=0`, and had no
  journal entries in the sampled 48-hour window.
- Certificate validates for `matrix-1.taild27e3c.ts.net`: Let's Encrypt YE1,
  valid 2026-08-18 through 2026-11-16; SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- CTI containers: web, scheduler, PostgreSQL, backup, and monitor running and
  healthy; worker exited 0 as designed (`restart: no`) and is unhealthy after
  exit. Restart counts: web/scheduler/PostgreSQL/backup/worker 0, monitor 3.
  All sampled CTI containers have `OOMKilled=false`. Monitor startup checks
  briefly failed during replacement, then recovered; current monitor health is
  healthy.
- Scheduler heartbeat was fresh at capture: 21 bytes, mode 644, value
  `2026-08-29T05:48:50Z`.
- Host resources normal: root 504G total/308G available (37% used), 62GiB RAM
  with 58GiB available, swap unused; file descriptors 2624 allocated with
  system maximum `9223372036854775807`.

## Database, migration, backup, and integrity evidence

- PostgreSQL 16.14 accepts local connections; database `hermes` is reachable.
  Alembic revision is `0013_op_retention`, matching repository migration head;
  no pending or failed migration is evidenced, and no migration was run.
- Run status: 6 `failed`, 0 `completed`, 0 running/scheduled. Fully successful
  ingestion timestamp: `NONE`. Latest failed source results were Google TAG
  HTTP 404 (`http_error`) and MSRC `malformed_xml`; the other 12 sources
  returned completed 200/304 results.
- Current counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks
  for entity evidence, relationship evidence, and report current-version
  references each returned 0.
- Latest encrypted backup is
  `/backups/hermes-20260828T165615Z.dump.enc`, completed 2026-08-28 16:56:16Z,
  3,507,536 bytes. Metadata SHA-256 and recomputed SHA-256 both equal
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Backup health is healthy; no restore was attempted. The backup predates the
  latest ingestion run and no isolated restore rehearsal was performed.
- Secret files were not read. File metadata shows all ten protected secret
  files are mode 644, including tokens/keys/database credentials; this is a
  security maintenance finding and no credential was rotated.

## Cause assessment

- **High confidence, causal:** enabled source contracts are stale/invalid.
  `config/sources.json` specifies Google TAG
  `https://blog.google/threat-analysis-group/rss/`, which currently returns
  HTTP 404 HTML, and MSRC `https://msrc.microsoft.com/blog/feed`, which returns
  HTTP 301 to an HTML blog page (and is not RSS/XML). These responses match the
  repeated persisted classifications and explain every failed run's two source
  failures.
- **High confidence, contributing:** no fully successful run is recorded,
  leaving freshness risk for the two feeds while unaffected sources continue.
- **Medium confidence, operational:** mutable image tag and absent formal
  approval/release record reduce reproducibility but do not explain upstream
  responses.
- **Low/no evidence:** web, proxy, scheduler, database connectivity,
  migration state, disk, memory, file descriptors, TLS, backup integrity,
  publication persistence, or data corruption are not failure causes.
- PostgreSQL logs contain several malformed/manual diagnostic SQL probes and two
  `role "postgres" does not exist` probes; these were operator diagnostics, not
  application failures. The application and scheduler logs show normal service
  operation and repeated source-collection failure only.

## Actions and approvals

- Completed read-only checks for release identity, Compose validation, service
  state/health/restarts, logs, Docker events, proxy/TLS, resources, database
  revision/connectivity, ingestion/source results, provenance integrity, and
  backup metadata/checksum.
- **No restart, migration, rollback, restore, proxy reload, source edit or
  disablement, credential action, Docker prune, volume operation, or data/
  publication mutation was performed.** The smallest reversible action is no
  action: restarting cannot repair either upstream contract and could obscure
  evidence.
- Incident record created at this path. No external issue/PR destination was
  supplied.

## State, rollback, and prevention

- Service state: operational web/API, portal, readiness, scheduler heartbeat,
  PostgreSQL, backup, and monitor; ingestion degraded for two sources.
- Data-integrity state: no corruption or orphan references found; partial-run
  successful results and provenance retained; encrypted backup checksum passed.
- Rollback/recovery: not performed and not required. No approved immutable
  compatible rollback target is documented. Destructive recovery remains
  unauthorized.
- Approval required for source/config or code release, restart, migration,
  restore, proxy reload, credential operations, deployment, or rollback.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with
  404, redirect-to-HTML, malformed-XML, and partial-run fixtures; preserve
  partial-run semantics; require immutable image digests and release records;
  fix secret modes through approved maintenance; correct monitor route probes;
  verify the next backup and perform an approval-gated isolated restore
  rehearsal.
