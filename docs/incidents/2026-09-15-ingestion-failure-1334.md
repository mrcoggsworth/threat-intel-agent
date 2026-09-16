# CTI-Hermes actionable ingestion failure diagnostic

- **Diagnosis time:** 2026-09-15T13:34:34Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `55ee3a45-fa92-4814-b35a-838f3785305a`
- **Observed at:** `2026-09-15T13:34:34.980697+00:00`
- **Correlation ID:** `ea545959-bf8b-4563-97b3-6be001e85249`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data`)
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** 59 pre-existing modified/deleted/untracked paths; no application or production-data files were changed by this diagnosis.
- **Application/image:** CTI services use image tag `cti-hermes:local`, started 2026-09-12T12:55:15Z–12:55:21Z; persisted application version `0.1.0`.

## Impact

The latest collection finished with 37/38 sources successful and status `failed`; it persisted 13,108 new documents and retained the failed-source evidence. The ThreatFox/Abuse.ch source is not fresh. Database projections currently contain 33,797 source documents (latest retrieval 2026-09-15T02:00:54.267448Z), 186 reports, and 201 publications. Reports/publications are stale at 2026-09-11T22:24:37Z. There are 2 completed full-success runs and 26 failed runs; usable partial runs are preserved. No evidence of data loss was found.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; `error_classification=oversized_response`; detail `response exceeds 10485760 bytes`; HTTP status unavailable. Persisted configuration remains `max_response_bytes=10485760`, configuration version 2, seven consecutive failures, last successful retrieval 2026-09-11T12:06:49.272951Z.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running and healthy, with restart count 0 and OOM false. No separate CTI worker container was present in the live `docker ps` inventory, so worker health is not independently verifiable; the scheduler is the component reporting source collection failure. In-container web checks: `/health/live` HTTP 200 with `{"status":"ok"}` and `/health/ready` HTTP 200 with configuration/database `ok`. The in-container `/api/v1/ops/run-status` check is HTTP 404; the monitor's configured internal endpoint is HTTP 200, so this is an API/routing-surface follow-up rather than web unavailability.
- Monitor evidence contains `full_success_freshness=stale_data` and `latest_ingestion_attempt=actionable_failure` (`1 source(s) failed`). Scheduler logs show source collection failure but no traceback or restart loop; containers have remained running.
- PostgreSQL accepts connections (`pg_isready`); database size is 195 MB; Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration was observed from the live revision evidence. Compose config validation could not run in this cron shell because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables are not exported; this did not affect the running stack.
- Host capacity is not limiting: root filesystem 43% used with 279G available, 49G memory available, swap 1.8 MiB used, host open-file limit 4096. No Docker container restart events were observed for CTI services in the sampled window.
- Backup state is healthy. `/backups/latest.metadata` is present at 2026-09-15T12:55:26Z, with current encrypted artifact `hermes-20260915T125523Z.dump.enc` (24,823,024 bytes). No restore or checksum revalidation was attempted.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; only unrelated client-disconnect warnings were observed.
- Checked-out but undeployed `config/sources.json` already contains a pre-existing ThreatFox `max_response_bytes=52428800` change. It was not deployed or modified by this diagnosis.

**Cause confidence: high.** The recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary is the blocking cause. Web/proxy, worker/scheduler liveness, PostgreSQL, disk, memory, migrations, backup, and certificate state do not explain the collection failure.

## Recovery gate and actions

The authoritative machine-readable evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The shared recovery gate was evaluated against the current event with its 1,800-second cooldown and lock. It returned `allowed=false`, reason `recovery cooldown is active`, and recorded a secret-free suppressed event. Read-back verified `/runtime/recovery.lock` is absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, integrity, rollback, and prevention

- **Service state:** web live/readiness and database connectivity healthy; scheduler/monitor containers healthy; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no production mutation was made.
- **Prevention/follow-up:** validate a bounded or paginated ThreatFox request, or deploy the existing 50 MiB response-limit change only through `./scripts/update-app.sh` when explicitly authorized; add oversized-response regression coverage; reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables; investigate the internal-versus-host ops-route mismatch; separately verify encrypted-backup restoreability.
