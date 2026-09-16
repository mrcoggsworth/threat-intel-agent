# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T12:00:28.248074+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `20dc998c-431b-43e3-994c-0f4cedfb5124`
- **Correlation ID:** `50c2936d-e14f-4c4d-889e-3e9b9b58b05d`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data`)
- **Diagnosis time:** 2026-09-15T12:02:44Z
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present; no application files were changed by this diagnosis except this incident record.

## Impact

The latest scheduled collection completed 37 of 38 sources and is persisted as `failed` because one source failed. The ThreatFox/Abuse.ch source is not fresh. The run persisted 13,108 new documents and retained the failed-source record. Database projections contain 33,797 source documents (latest retrieval 2026-09-15T02:00:54.267448Z), 186 reports, 201 report versions, and 201 publications. Report/version/publication freshness remains 2026-09-11T22:24:37Z. The latest five runs are all failed with one failed source; no evidence of data loss was found.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; `error_classification=oversized_response`; detail `response exceeds 10485760 bytes`; HTTP status unavailable. Persisted configuration has `max_response_bytes=10485760`, configuration version 2, seven consecutive failures, and last successful retrieval 2026-09-11T12:06:49.272951Z.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running healthy with restart count 0 and OOM false. Web `/health/live` and `/health/ready` returned HTTP 200; readiness reported configuration and database `ok`. Scheduler heartbeat was current at 2026-09-15T12:02:44Z.
- Monitor logs repeatedly report stale full-success data and a failed latest ingestion attempt. Scheduler logs contain `source collection failed` but no sampled traceback or restart loop.
- PostgreSQL accepted connections (`pg_isready`); database size is 195 MB; PostgreSQL is 16.14; Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration was observed from the available revision evidence.
- Host capacity is not limiting: root filesystem 43% used with 278G available, 51G memory available, swap 1.5 MiB used, and host open-file limit 4096. Docker events in the window showed health-check `exec_*` events, not container restarts.
- Application containers use `cti-hermes:local`, image label digest `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`, started 2026-09-12T12:55Z; persisted run application version is `0.1.0`. The checked-out `config/sources.json` contains a pre-existing ThreatFox `max_response_bytes=52428800` change, but it is not deployed or modified by this diagnosis.
- Latest backup is `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, metadata present with SHA-256 recorded, and backup container healthy. No restore was attempted; encrypted contents/checksum were not revalidated.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate renewal failure was observed. Two unrelated client-disconnect warnings were present.

**Cause confidence: high.** This is a recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary, not a web, proxy, worker/scheduler liveness, PostgreSQL availability, disk, memory, migration, backup, or certificate-renewal failure.

## Recovery gate and actions

The authoritative machine-readable evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The recovery gate was evaluated with a 1,800-second cooldown and lock. It returned `allowed=false`, reason `recovery cooldown is active`, gate event `17b1460e-cce9-4e20-b1f5-d6a86e5605b3`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. The lock was absent after evaluation. Diagnosis-only authorization did not permit a retry, restart, deployment, migration, credential change, or destructive recovery; none was performed.

## Service, integrity, rollback, and prevention

- **Service state:** web readiness and database connectivity healthy; scheduler heartbeat current; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no application or production-data mutation was made.
- **Prevention:** validate bounded/paginated ThreatFox retrieval or the existing 50 MiB response-limit change, add oversized-response regression coverage, and deploy only through `./scripts/update-app.sh` when explicitly authorized. Reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables. Investigate the internal-versus-host `/api/v1/ops/run-status` route mismatch separately. Perform encrypted-backup restore verification separately.
