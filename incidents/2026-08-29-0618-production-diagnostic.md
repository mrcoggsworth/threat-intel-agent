# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 06:18 UTC (2026-08-29 01:18 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The application and private readiness surface are operational, but ingestion is
currently degraded. The latest persisted run (`4f8db05e-c29a-5c80-bfe0-464edad4a18`)
started 2026-08-29 02:00:00Z, ended 02:00:01Z, processed 14 sources, completed
12, failed 2, and persisted 110 new documents. The database contains six failed
runs and no completed run, so Google TAG and MSRC freshness are at risk. Partial
successful-source results and provenance remain available.

## Identity and change state

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD
  `a84a20340aad85bcb1777928dc2f7270468eec17`.
- Working-tree changes at capture are incident records only; no overlapping
  application, migration, Compose, or source edits were found.
- `/version` reports `hermes-cti 0.1.0`.
- Running application image is mutable tag `cti-hermes:local`, image ID
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  Compose label records image digest
  `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`.
  This remains a release-reproducibility risk.
- Application containers were replaced 2026-08-28 16:56:14Z. No formal
  approval/release record was found in the repository snapshot.
- Production env file exists at `/opt/cti-hermes/env/production.env`, mode 600,
  mtime 2026-08-25 17:20:29 -0500. Its variable-name inventory lacks the
  required `HERMES_SECRET_DIR`; consequently an independent
  `docker compose --env-file /opt/cti-hermes/env/production.env -f
  deploy/docker-compose.yml config --quiet` validation failed before rendering.
  Secret values were not read.

## Service, proxy, certificate, and resource evidence

- Private ingress `/health/ready` returned HTTP 200 with configuration and
  database `ok`; `/version` returned 200 and version `0.1.0`. `/health/live`
  on this private listener returned 404, while the application liveness probe
  is healthy and local/container health probes return 200. This is a route/
  proxy-surface distinction, not evidence of application liveness failure.
- Nginx is active, started 2026-08-26 18:20:33 CDT, `NRestarts=0`, and had no
  journal entries in the sampled 48-hour window.
- TLS certificate for `matrix-1.taild27e3c.ts.net` is Let's Encrypt YE1,
  valid 2026-08-18 through 2026-11-16. SHA-256 fingerprint:
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  Worker exited 0 as designed (`restart: no`) and is unhealthy after exit.
  Restart counts: web/scheduler/PostgreSQL/backup/worker 0; monitor 3.
  All sampled CTI containers report `OOMKilled=false`. Monitor's three
  restarts occurred during the 2026-08-28 replacement and it is now healthy.
- Scheduler heartbeat is fresh: 21 bytes, mode 644, value
  `2026-08-29T06:17:50Z`.
- Host resources are normal: root 504G total/308G available (37% used), 62GiB
  RAM/58GiB available, swap unused, `/proc/sys/fs/file-nr` reports 2592
  allocated descriptors, and system file maximum is
  `9223372036854775807`.

## Database, migration, backup, and integrity evidence

- PostgreSQL 16 accepts connections and database `hermes` is reachable.
- Alembic revision is `0013_op_retention`; this matches repository migration
  head. No pending or failed migration is evidenced and no migration was run.
- Run state is `failed=6`, `completed=0`. Latest source failures are
  `google-threat-analysis-group` with `HTTP 404/http_error` and
  `microsoft-security-response-center` with `malformed_xml`; the other 12
  source results completed with HTTP 200/304.
- Current source-document count is 1,889; the latest run added 110 documents.
  Prior integrity checks recorded zero orphan entity-evidence,
  relationship-evidence, and report-current-version references. No data
  corruption evidence was found.
- Latest encrypted backup is
  `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, completed
  2026-08-28 16:56:16Z. Recomputed SHA-256 equals metadata:
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Backup is present and readable by the backup container; no restore rehearsal
  was attempted. It predates the latest ingestion run.
- Secret metadata remains a security finding: `/opt/cti-hermes/secrets`
  includes `analyst-token` mode 644; other secret files were not enumerated or
  read in this capture. No credential was rotated.

## Cause assessment

- **High confidence, causal:** two enabled source contracts are stale/invalid.
  Repository `config/sources.json` points Google TAG at
  `https://blog.google/threat-analysis-group/rss/`, which returned HTTP 404
  HTML at capture, and MSRC at `https://msrc.microsoft.com/blog/feed`, which
  returned HTTP 301 to an HTML blog page (and then HTTP 200 HTML), not RSS/XML.
  These responses exactly match the persisted failure classifications and
  explain the two failures in every recent partially successful run.
- **High confidence, contributing:** no fully successful ingestion run is
  recorded, creating freshness risk despite successful collection from the
  other 12 sources.
- **Medium confidence, operational:** the production env omits required
  `HERMES_SECRET_DIR`, making reproducible Compose validation fail; the mutable
  image tag and absent formal release record further weaken reproducibility.
  These do not explain the upstream feed failures.
- **Low/no evidence as causes:** web, proxy, scheduler heartbeat, PostgreSQL
  connectivity, migration state, disk, memory, file descriptors, TLS,
  publication persistence, backup checksum, and data corruption.
- PostgreSQL log errors are malformed/manual diagnostic probes (including
  nonexistent columns/relations, invalid SQL, and two probes using the absent
  `postgres` role), not application failures. Application logs show normal
  operation plus repeated source-collection failures.

## Actions and approvals

- Completed read-only checks for repository/release identity, container state,
  health/restarts, logs, Docker events, Nginx/TLS, resources, database
  connectivity/revision, source results, heartbeat, Compose validation,
  backup metadata/checksum, and protected-file metadata.
- **No restart, migration, rollback, restore, proxy reload, source edit,
  disablement, credential action, Docker prune, volume operation, or data/
  publication mutation was performed.** Restart would not repair either
  upstream contract and could obscure evidence.
- This incident record is the maintenance handoff. No external issue tracker
  destination was supplied, so no external issue/PR was created.

## State, rollback, and prevention

- Service state: web/API, private readiness, scheduler, PostgreSQL, backup,
  monitor, and TLS ingress operational; ingestion degraded for two sources.
- Data-integrity state: no corruption/orphan evidence; successful partial-run
  data and provenance retained; latest encrypted backup checksum passed.
- Rollback: not performed and not indicated. No approved immutable compatible
  rollback target is documented. Destructive recovery remains unauthorized.
- Approval required for source/config or code release, env correction,
  restart, migration, restore, proxy reload, credential operations,
  deployment, or rollback.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with
  404, redirect-to-HTML, malformed-XML, and partial-run fixtures; preserve
  partial-run semantics; add `HERMES_SECRET_DIR` to the protected production
  env through approved maintenance; require immutable image digests and release
  records; correct private proxy route expectations; fix secret modes; verify
  the next backup and perform an approval-gated isolated restore rehearsal.
