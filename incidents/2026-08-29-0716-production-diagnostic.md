# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 07:16:50 UTC (2026-08-29 02:16:50 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The private web/API, readiness, scheduler, PostgreSQL, backup, monitor, and TLS ingress are operational. Ingestion remains degraded: the latest run failed on 2 of 14 sources, and there is no recorded fully completed run. Google TAG and MSRC freshness are at risk; 12 source results, partial documents, and provenance remain available. This is not a total service outage and no data-corruption signal was found.

## Identity and change state

- Repository remote: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17` (`2026-08-28T11:54:51-05:00`, merge of PR #41).
- Working-tree additions are incident records only; no overlapping application, migration, Compose, or source edits were found.
- `/version`: HTTP 200, `{"name":"hermes-cti","version":"0.1.0"}`.
- Running application image is mutable `cti-hermes:local`, image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; Compose label records image digest `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`. Reproducibility risk remains.
- Application containers started/replaced `2026-08-28T16:56:14Z`; monitor restarted three times during that replacement and is now healthy. No formal approval/release record was found in the repository snapshot.
- `/opt/cti-hermes/env/production.env` mode 600, mtime `2026-08-25 17:20:29 -0500`; its variable inventory omits required `HERMES_SECRET_DIR`. Independent Compose validation fails without explicitly supplying that variable. Secret values were not read. One secret file remains mode 644 (identity intentionally not recorded).
- Compose validation succeeds when supplied with the existing protected secret directory and current local image tag; this validates syntax only and does not make the image immutable.

## Service, proxy, certificate, and resource evidence

- `/health/live` on the supplied port returns Nginx HTTP 404; `/health/ready` returns HTTP 200 with configuration/database `ok`; `/version` returns HTTP 200. Container-local liveness checks return HTTP 200. This is a proxy route-surface mismatch, not application liveness failure.
- Containers: web, scheduler, PostgreSQL, backup, and monitor `running/healthy`; worker `exited` with code 0 as designed (`restart: no`) but health is `unhealthy` after exit. Restart counts: web/scheduler/PostgreSQL/backup/worker 0; monitor 3. All sampled CTI containers report `OOMKilled=false`.
- Scheduler heartbeat is being updated and healthcheck is passing. Host uptime is 2 days 7:56; load averages `0.04, 0.08, 0.08`.
- Host resources are normal: root filesystem 504G total/308G available (37% used); memory 62GiB total/58GiB available; swap unused; `/proc/sys/fs/file-nr` `2656 0 9223372036854775807`; shell descriptor limit 4096.
- Host Nginx is active, `NRestarts=0`, active since `2026-08-26 18:20:33 CDT`; no sampled journal entries in the last 48 hours.
- TLS certificate is for `matrix-1.taild27e3c.ts.net`, Let's Encrypt YE1, valid `2026-08-18` through `2026-11-16`; SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity evidence

- PostgreSQL 16 is accepting connections; readiness reports database `ok`.
- Alembic revision is `0013_op_retention`, matching repository migration head. No pending or failed migration is evidenced; no migration was run.
- Ingestion state is `failed=6`, `completed=0`. Latest run `4f8db05e-c29a-5c80-bfe0-464edad4a18e` started `2026-08-29 02:00:00Z`, completed `02:00:01Z`, processed 14 sources, succeeded 12, failed 2, and added 110 documents. Last successful run: `NONE`.
- Latest source failures: `google-threat-analysis-group` (`HTTP 404`, `http_error`) and `microsoft-security-response-center` (`malformed_xml`). Other 12 source results completed with HTTP 200/304.
- Current counts: source documents 1,889; raw artifacts 65; evidence claims 1,908; indicators 3,494; reports 453; publications 454. Existing integrity checks recorded no orphan entity-evidence, relationship-evidence, or report-current-version references.
- Latest encrypted backup is `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, completed `2026-08-28T16:56:16Z`. Read-only SHA-256 recomputation matched metadata: `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`. No restore rehearsal was attempted; backup predates the latest ingestion run.
- PostgreSQL log errors in the sampled period are malformed/manual diagnostic probes (wrong table/column names and SQL), not application failures. Application logs show normal operation plus source-collection failures.

## Cause assessment

- **High confidence, causal:** two enabled source contracts are stale/invalid. `config/sources.json` specifies Google TAG `https://blog.google/threat-analysis-group/rss/`, which returns HTTP 404 HTML, and MSRC `https://msrc.microsoft.com/blog/feed`, which redirects to an HTML blog page rather than RSS/XML. These responses exactly match persisted failure classifications in every recent partial run.
- **High confidence, contributing:** six failed runs and zero completed runs create freshness risk even though 12 sources succeed.
- **Medium confidence, operational:** missing `HERMES_SECRET_DIR` in the protected production env breaks reproducible Compose validation; mutable image tag and absent formal release record weaken release traceability. These do not explain upstream feed failures.
- **Low/no evidence as causes:** web process, scheduler heartbeat, proxy process, PostgreSQL connectivity, migrations, disk, memory, file descriptors, TLS, backup checksum, and data corruption.

## Actions and approvals

- Completed read-only checks for release identity, repository state, container health/restarts, logs, Docker events, Nginx/TLS, resources, database connectivity/revision, ingestion/source results, heartbeat, Compose validation, backup metadata/checksum, and protected-file metadata.
- **No restart, migration, rollback, restore, proxy reload, source edit, disablement, credential action, Docker prune, volume operation, or data/publication mutation was performed.** The smallest reversible action is no runtime action: a restart cannot repair either upstream contract and could obscure evidence.
- Incident record created in this repository; no external issue tracker destination was supplied, so no external issue/PR was created.

## State, rollback, and prevention

- Service state: operational core/private readiness and TLS; ingestion degraded for two sources; worker exit is expected reserved-entrypoint behavior.
- Data-integrity state: no corruption/orphan evidence; successful partial-run data and provenance retained; latest encrypted backup checksum passed, but backup is not current to the latest run and restore rehearsal is outstanding.
- Rollback: not performed and not indicated. No approved immutable compatible rollback target is documented. Destructive recovery remains unauthorized.
- Approval required for source/config or code release, protected env correction, restart, migration, restore, proxy reload, credential operation, deployment, or rollback.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; add `HERMES_SECRET_DIR` through approved maintenance; require immutable image digests and release records; align proxy health-route expectations; correct secret file modes; verify the next backup and perform an approval-gated isolated restore rehearsal.
