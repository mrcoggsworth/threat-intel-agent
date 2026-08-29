# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 07:48 UTC (2026-08-29 02:48 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

This is a partial ingestion and private-ingress contract incident, not a total application outage. The web application, database, scheduler, backup, monitor, and TLS are operational. Ingestion remains degraded for 2 of 14 enabled sources across six consecutive failed runs; no fully successful run is recorded. Twelve source results and their partial documents/provenance remain available. The supplied 9444 port serves readiness and version but returns Nginx 404 for liveness and operational paths expected by some checks. The 9443 listener has the complementary route policy.

## Identity and change state

- Repository remote: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, also `main`/`origin/main` (merge of PR #41, 2026-08-28 11:54:51 -0500).
- Working-tree changes are incident records only; no application, migration, Compose, or source edits overlap this diagnosis.
- Running application image is mutable `cti-hermes:local`; image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; Compose image label digest `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`. `/version` reports `0.1.0`. Immutable release traceability and an approval record were not found.
- Web, scheduler, PostgreSQL, backup, and monitor were started/replaced 2026-08-28 16:56:14Z (PostgreSQL started 2026-08-26 23:20:36Z). Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3. Worker exited code 0 at 16:56:16Z under its documented `restart: no` reserved-entrypoint design; this is not evidence of a crash.
- `/opt/cti-hermes/env/production.env` is mode 600, mtime 2026-08-25 17:20:29 -0500, but its variable inventory omits required `HERMES_SECRET_DIR`; independent Compose validation fails before service inspection. Secret values were not read. `/opt/cti-hermes/secrets/analyst-token` is mode 644; `admin-token` is mode 600. This is a security/configuration finding, not the ingestion cause.

## Service, proxy, certificate, and resource evidence

- `https://...:9444/health/ready` returned HTTP 200 with `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`; `/version` returned HTTP 200 and `0.1.0`; `/health/live`, `/health/last-success`, `/api/v1/ops/status`, and `/api/v1/ops/runs/latest` returned Nginx/application 404. Container-local liveness checks repeatedly returned HTTP 200.
- Nginx config confirms deliberate split: 9443 proxies the general route and explicitly returns 404 for readiness/version/admin/ops; 9444 proxies readiness/version/admin/ops and returns 404 for the general route. Thus the supplied port is not a complete application contract, and `/health/live` is absent there. Nginx is active with `NRestarts=0` since 2026-08-26 18:20:33 CDT.
- Scheduler heartbeat was current at capture (`2026-08-29T07:48:21Z`). All inspected CTI containers report `OOMKilled=false`. Host load was low (`0.11, 0.08, 0.08` at 07:45 CDT); root filesystem is 37% used with 308G available; memory has 58GiB available of 62GiB; swap is unused; file-nr was `2528 0 9223372036854775807`; shell descriptor limit 4096. No disk, memory, or file-descriptor capacity incident is indicated.
- TLS certificate subject is `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt YE1, valid 2026-08-18 through 2026-11-16; OpenSSL verification succeeded. Certificate expiry/validation is not causal.

## Database, migration, backup, and integrity evidence

- PostgreSQL 16.14 accepts connections and readiness reports database `ok`. Alembic revision is `0013_op_retention`, matching repository migration head. No migration was run; no pending or failed migration is evidenced.
- Latest run is `4f8db05e-c29a-5c80-bfe0-464edad4a18e`, started 2026-08-29 02:00:00.091Z and completed 02:00:01.945Z: status `failed`, 14 sources processed, 12 successful, 2 failed, 110 documents added. History is six `failed`, zero `completed`; last fully successful run is `NONE`.
- Latest persisted failures are `google-threat-analysis-group` with `http_error` and `microsoft-security-response-center` with `malformed_xml`. The other 12 source runs completed with HTTP 200/304.
- Latest encrypted backup is `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, completed 2026-08-28T16:56:16Z, mode 600. Read-only SHA-256 recomputation matches metadata: `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`. Backup is valid by checksum but predates the latest run; no isolated restore rehearsal was attempted.
- PostgreSQL log errors in the sampled period are failed manual diagnostic queries (wrong relation/column names and one missing role), not application failures. No corruption or destructive operation was observed; partial-run data and provenance remain retained.

## Cause assessment

- **High confidence causal:** two enabled source contracts in authoritative `config/sources.json` are stale/incompatible. A direct probe of `https://blog.google/threat-analysis-group/rss/` reproduced HTTP 404 HTML. A direct probe of `https://msrc.microsoft.com/blog/feed` followed its redirect to `https://www.microsoft.com/en-us/msrc/blog` and received HTTP 200 HTML, not an RSS/XML document. These responses match the persisted failure classifications exactly.
- **High confidence contributing:** six failed runs and zero completed runs create freshness risk for the two affected sources while retaining successful partial data.
- **Medium confidence operational/security:** 9443/9444 route policies do not match a single-port health/ops contract; missing `HERMES_SECRET_DIR` prevents reproducible Compose validation; the running image is mutable; one secret file is world-readable. These do not explain source failures.
- **Low/no evidence as causes:** web process, scheduler heartbeat, PostgreSQL connectivity, migration state, disk, memory, file descriptors, TLS, backup checksum, and data corruption.

## Actions and approvals

- Completed read-only checks for time/version/image identity, Git state, container state/restarts, health/readiness, application and database logs, Docker events, proxy/listeners/config, resources, database connectivity/revision/run state, source responses, heartbeat, backup metadata/checksum, and protected-file metadata.
- **No restart, migration, rollback, restore, proxy reload, source edit/disablement, credential operation, Docker prune, volume operation, or data/publication mutation was performed.** The smallest reversible runtime action is no action: restarting cannot repair the upstream contracts and could obscure evidence.
- Created this repository incident record. No external issue tracker destination was supplied, so no external issue or PR was created.

## State, rollback, and prevention

- **Service state:** core/private readiness, database, scheduler, backup, monitor, and TLS are operational; ingestion is degraded on 2/14 sources; worker exit is expected design; ingress route surfaces are inconsistent.
- **Data integrity:** no corruption signal; partial successful data and provenance retained; latest backup checksum passed but is stale relative to the latest run; restore rehearsal outstanding.
- **Rollback:** not performed and not indicated. No documented approved immutable compatible target exists. Destructive recovery remains unauthorized.
- **Approvals required:** source/config or code release, protected environment correction, secret mode correction, proxy configuration change/reload, deployment, migration, restore rehearsal, restart, or rollback.
- **Prevention:** approve replacement/adapted Google TAG and MSRC contracts with 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; add `HERMES_SECRET_DIR`; require immutable image digests and release records; align proxy and monitor health/ops expectations; correct secret file modes; verify the next backup and perform an approval-gated isolated restore rehearsal.
