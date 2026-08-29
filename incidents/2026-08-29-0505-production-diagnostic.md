# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 05:05 UTC (2026-08-29 00:05 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The public portal, web/API liveness, private readiness, scheduler heartbeat, PostgreSQL, and backup services are operational. Scheduled ingestion remains degraded: the latest run at `2026-08-29 02:00:00Z` failed after 12/14 sources succeeded and persisted 110 new documents. All six recorded ingestion runs have status `failed`; no fully successful (`status=completed`) run is recorded. The last partial run with successful sources is `4f8db05e-c29a-5c80-bfe0-464edad4a18` at `2026-08-29T02:00:01.945429Z`. Successful-source documents and partial-run provenance remain persisted.

## Identity and release

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, also `main`/`origin/main`.
- Working-tree changes are incident records only; no overlapping source, migration, Compose, or application edits were found.
- Live application version: `hermes-cti 0.1.0`.
- Running image: `cti-hermes:local`, content digest `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`, created `2026-08-28T16:56:04Z`. The mutable tag remains a release-reproducibility concern.
- Compose validation passed when `HERMES_SECRET_DIR=/home/cptcoggsworth/.local/state/cti-hermes/secrets` was supplied. The production env file exists at `/opt/cti-hermes/env/production.env` with mode 600; secret contents were not read.
- Last repository deployment/config-related change: commit `b2c3a61e727015b1109ba8e564d5cf43cd47d1de` (`2026-08-26 20:18:15 -0500`) for Compose secret/endpoint handling. Latest portal code commit is `bd3e3fddfb039f866ef1053001ca8ffafa2a6bd3` (`2026-08-28 11:50:34 -0500`). No formal approval/release record was found in the repository snapshot.

## Service, proxy, certificate, and resource evidence

- `9443/health/live`: HTTP 200; public `/reports`: HTTP 200.
- `9444/health/ready`: HTTP 200 with configuration/database `ok`; `/version`: HTTP 200 with `0.1.0`. Unauthenticated private `/health/live` returns host-Nginx HTTP 404 by policy, not an application failure.
- TLS verification succeeded for `matrix-1.taild27e3c.ts.net`: Let's Encrypt `YE1`, valid `2026-08-18T14:30:37Z` through `2026-11-16T14:30:36Z`, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Web, scheduler, PostgreSQL, backup, and monitor are running/healthy. Worker exited 0 as designed (`restart: no`) and is unhealthy after exit. Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3. All CTI containers report `OOMKilled=false`.
- Scheduler heartbeat was non-empty and fresh: size 21 bytes, mode 644, mtime `2026-08-29 05:01:49Z`. Scheduler logs show only two source collection failures at `02:00:00Z`, not a crash loop.
- Host capacity is normal: root 504G total/175G used/308G available (37%); 62GiB RAM with 58GiB available; swap unused; host open-file limit 4096 and sampled host FD count 231. Sampled PID 1 FD counts: web 14, scheduler 7, PostgreSQL 10.
- Host Nginx is active, `NRestarts=0`, `ExecMainStatus=0`, and has no journal entries in the sampled 24-hour window. Docker event sampling showed exec/healthcheck activity and no CTI lifecycle restart events.

## Database, migration, backup, and integrity

- PostgreSQL 16.14 is accepting connections; database size is 35MB; 3 sessions were observed.
- Database revision is `0013_op_retention`, matching the repository migration head. No pending or failed migration is evidenced; no migration was run.
- Latest run: `4f8db05e-c29a-5c80-bfe0-464edad4a18`, failed, 14 total / 12 successful / 2 failed / 110 new documents, error summary `2 source(s) failed`.
- Latest source results: Google TAG `failed/http_error` (no HTTP status persisted) and MSRC `failed/malformed_xml`; the other 12 sources were `completed` (HTTP 200 or 304).
- Current entity counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks for entity evidence, relationship evidence, and report current-version references returned zero.
- Direct source probes reproduced the upstream contract failures: `https://blog.google/threat-analysis-group/rss/` returned HTTP 404 with an HTML body; `https://msrc.microsoft.com/blog/feed` returned HTTP 301 to `https://www.microsoft.com/en-us/msrc/blog` with an HTML body rather than a feed.
- Latest encrypted backup metadata: `/backups/hermes-20260828T165615Z.dump.enc`, mode 600, completed `2026-08-28T16:56:16Z`, 3,507,536 bytes, SHA-256 `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`; `latest.metadata` mode 600 and backup healthcheck passed. No restore was attempted.

## Cause assessment

- **High confidence, causal:** stale/invalid Google TAG and MSRC source contracts explain the exact repeated two-source partial failures. This is a source/provider contract issue.
- **High confidence, contributing:** no fully completed ingestion run exists, creating freshness and downstream publication risk for affected feeds.
- **Medium confidence, operational:** production uses a mutable image tag despite a recorded content digest, and no formal approval record was found; this weakens reproducibility but does not explain the source failures.
- **Low/no evidence:** web process failure, proxy/TLS failure, scheduler crash, PostgreSQL failure, migration failure, resource exhaustion, backup failure, publication persistence failure, or data corruption.
- **Security hardening finding:** secret files are mode 644, although the containing directory is mode 700 and owned by the deployment user. No credentials were printed or rotated.

## Actions and approvals

- Completed read-only probes for release identity, Compose validation, container state/restarts/health, application/proxy health, logs, Docker events, host resources/FDs, database connectivity/revision/integrity, source contracts, backup metadata/hash, Nginx, and TLS.
- Smallest reversible action is **no restart**: restarting cannot repair the two upstream contracts and could obscure evidence. No restart, migration, rollback, restore, source edit/disablement, proxy reload, credential action, Docker prune, volume operation, or data/publication mutation was performed.
- Incident record created at this path. No external issue/PR destination was supplied.

## State and prevention

- Service state: operational web/API, portal, readiness, scheduler heartbeat, PostgreSQL, and backup; ingestion degraded for two sources.
- Data-integrity state: no corruption or orphan references found; partial successful results and provenance retained; encrypted backup exists and passed its healthcheck.
- Rollback/recovery: not performed and not required. No approved immutable compatible rollback target was documented. Destructive recovery remains unauthorized.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; keep partial-run semantics explicit; reconcile monitor route checks with Nginx policy; require immutable image digests and release/approval records; correct secret file modes via approved maintenance; verify the next backup and schedule an approval-gated isolated restore rehearsal.

Approvals are required for source/config or code release, restart, migration, restore, proxy reload, credential operations, deployment, or rollback.
