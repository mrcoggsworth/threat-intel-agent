# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 10:47:51 UTC (2026-08-29 05:47 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

Partial service incident, not a total outage. Web liveness/readiness, private API, PostgreSQL, scheduler heartbeat, backup container, monitor, proxy listeners, and TLS are operational. Ingestion remains degraded for 2 of 14 enabled sources. The latest run failed overall but retained 12 successful source results and 110 new documents. Six recorded runs are failed and none is fully completed, so freshness for Google TAG and MSRC is at risk. Existing report reads remain available; report writes for an existing colliding slug remain degraded. No confirmed data corruption was found.

## Identity and deployment

- Repository remote: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, matching `main` and `origin/main` (PR #41 merge, 2026-08-28 16:54:51Z).
- Working tree has pre-existing staged incident records and untracked `introspect_temp.py`; no application, migration, Compose, or source files were changed by this diagnostic. This incident record is the only diagnostic artifact added in this capture.
- `/version`: HTTP 200, `hermes-cti 0.1.0`.
- Running CTI image is mutable `cti-hermes:local`, image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; Compose label digest `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`. No immutable release or approval reference was identified.
- CTI containers were replaced at approximately 2026-08-28 16:56:14Z. Protected environment `/opt/cti-hermes/env/production.env` is mode 600, mtime 2026-08-25 22:20:29Z, and omits `HERMES_SECRET_DIR`; `analyst-token` is mode 644. Secret values were not read. No last config change newer than the PR #41 merge was identified.

## Service, proxy, scheduler, and host state

- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy. Worker and runtime-init exited code 0 by design (`restart: no`); their health status is `unhealthy` because one-shot containers do not remain running. CTI containers report `OOMKilled=false`; web/scheduler/PostgreSQL/backup restart counts are 0; monitor restart count is 3 during initial stack replacement and is now healthy.
- Private endpoint checks: `/health/ready` HTTP 200 with `configuration=ok,database=ok`; `/version` HTTP 200. `/health/live` on port 9444 returns Nginx HTTP 404, while container-local liveness returns `{"status":"ok"}` and the checked-in split-port policy exposes liveness on the other listener. This is a monitoring/health-contract mismatch, not web failure.
- Scheduler heartbeat `/runtime/scheduler.heartbeat` was current at 2026-08-29 10:46:52Z; scheduler health checks remained successful. Docker events in the observation window showed healthcheck exec activity and no CTI crash/restart event after replacement.
- Nginx is active, `NRestarts=0`, since 2026-08-26 23:20:33Z. Listeners are `100.68.61.10:9443`, `100.68.61.10:9444`, and `127.0.0.1:18000`.
- Host capacity is normal: root 37% used with 308 GiB free; 62 GiB RAM with 57 GiB available; swap unused; file-nr `2720 0 9223372036854775807`; shell descriptor limit 4096; load 0.13/0.08/0.08. No disk, memory, OOM, or descriptor cause.
- TLS verification succeeded. Certificate CN `matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt YE1, valid 2026-08-18 14:30:37Z through 2026-11-16 14:30:36Z, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity

- PostgreSQL 16 is accepting connections. Live Alembic revision `0013_op_retention` matches repository head; no pending/failed migration is evidenced and no migration was run.
- Latest run `4f8db05e-c29a-5c80-bfe0-464edad4a18` ran 2026-08-29 02:00:00.091132Z–02:00:01.945429Z: `failed`, 14 total, 12 successful, 2 failed, 110 new documents. History is 6 failed / 0 completed; last fully successful run is `NONE`.
- The two failed source runs are `google-threat-analysis-group` (`http_error`, HTTP 404) and `microsoft-security-response-center` (`malformed_xml`, XML payload could not be parsed). Twelve other sources completed with HTTP 200/304.
- Direct probes reproduced the failures: Google TAG RSS returns HTTP 404 HTML; MSRC feed returns HTTP 301 to `https://www.microsoft.com/en-us/msrc/blog`, followed by HTTP 200 HTML. The authoritative source registry still contains incompatible feed URLs.
- Current checks: 454 active reports; zero orphan active `entity_evidence.source_document_id` references; zero orphan report current-version references. The unique report-slug constraint continues to reject duplicates, but the application exposes that conflict as a database error rather than a typed conflict. No confirmed corruption.
- Latest encrypted backup is `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, mode 600. Recomputed SHA-256 `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737` matches metadata and `latest.metadata`. It predates the latest ingestion run; isolated restore rehearsal was not attempted.
- Compose syntax validation passed with `HERMES_SECRET_DIR=/opt/cti-hermes/secrets`, `HERMES_IMAGE=cti-hermes:local`, and the protected environment file.

## Cause assessment

- **High confidence primary cause:** stale/incompatible Google TAG and MSRC source contracts. Live upstream responses exactly match persisted failure classifications and explain the repeated two-source partial failures.
- **High confidence separate publication defect:** report slug collision handling leaks a database uniqueness failure as an application error, degrading writes for an existing slug while preserving uniqueness/data integrity.
- **Medium confidence operational/security contributors:** split 9443/9444 health expectations, missing `HERMES_SECRET_DIR`, mutable image/release traceability, and mode 644 on `analyst-token`. These do not explain ingestion failures.
- **Low/no evidence as causes:** web, proxy, scheduler, database connectivity, migrations, host resources, TLS, backup checksum, or referential corruption.

## Actions and approvals

Completed read-only checks of repository/release identity, image/container state and restart history, Docker events/logs, health/readiness, scheduler heartbeat, proxy/listeners, TLS, host resources, database connectivity/revision/run state, source responses, backup inventory/checksum, protected-file metadata, and Compose validation.

No restart, migration, rollback, restore, proxy reload, source edit/disablement, credential operation, Docker prune, volume operation, or data/publication mutation was performed. The smallest reversible action is no runtime action: restart cannot repair upstream contracts and could obscure evidence. This repository incident record is the maintenance issue/handoff; no external tracker destination was supplied.

## State, rollback, and prevention

- **Service:** core/private service operational; ingestion degraded 2/14; report writes degraded for the colliding slug; 9444 liveness 404 is expected under current split policy but should be reconciled with monitoring.
- **Data integrity:** no confirmed corruption; partial results and provenance retained; uniqueness/reference checks pass. Backup checksum passes, but freshness and restoreability remain incomplete.
- **Rollback:** not performed and not indicated. No documented approved immutable compatible target was identified. Destructive recovery remains unauthorized.
- **Approvals required:** source/config or code release, report-conflict fix, protected-env/secret-mode correction, proxy change/reload, deployment, migration, restart, restore rehearsal, credential operation, or rollback.
- **Prevention:** approve replacement/adapted Google TAG and MSRC contracts with 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; return a typed conflict for existing report slugs; align the two-port health contract; add `HERMES_SECRET_DIR`; require immutable image digests and release records; correct secret modes; verify the next encrypted backup; perform an approval-gated isolated restore rehearsal.
