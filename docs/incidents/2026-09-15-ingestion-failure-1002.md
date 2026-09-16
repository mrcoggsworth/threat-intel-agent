# CTI-Hermes production ingestion failure diagnostic (10:02Z)

## Classification

- Recorded: 2026-09-15T10:02:06Z
- Impact: partial collection degradation. The latest run failed after 37/38 sources and persisted 13,108 new documents. ThreatFox coverage, full-success freshness, and downstream analyst/publication freshness remain stale.
- Cause confidence: high for the deployed ThreatFox response-size boundary; medium for upstream payload growth.
- Data integrity: preserved. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in this cron shell. Per the deployed Compose configuration, authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before any model work or gate evaluation:

- state: `actionable_failure`
- event_id: `a80cae92-53c2-448c-9965-ad0ebe31eb57`
- observed_at: `2026-09-15T10:00:19.540468+00:00`
- correlation_id: `df100208-8b6d-48bd-9005-79830b3e0f79`
- endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- signals: `latest_ingestion_attempt=actionable_failure` (`1 source(s) failed`); `full_success_freshness=stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- usable-run status: the latest terminal run with at least one successful source is the failed latest attempt `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` (37/38 sources); usable partial data is available, but it is not a full-success run

## Recovery gate

The shared `/runtime` recovery gate was evaluated after evidence validation with the 1,800-second cooldown and lock. It returned `allowed=false`, reason `recovery cooldown is active`, and recorded suppressed event `024ea406-28f0-4040-a0e2-5bef70e14c0d` at `2026-09-15T10:01:42.540424+00`. The recorded correlation was `cbbff7d4-d222-4476-a36e-b5c9066e7c7a`; run ID was `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Read-back verified `/runtime/recovery.lock` is absent. No recovery was attempted.

## Evidence collected

- Repository/release: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree modifications, deletions, and untracked files were observed and left untouched apart from this incident record.
- Application/image: version `0.1.0`; image `cti-hermes:local`, ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12. Compose services started 2026-09-12; PostgreSQL started 2026-09-05.
- Container/restart state: web, scheduler, monitor, PostgreSQL, backup, and proxy are up; Hermes containers report healthy; restart count 0 and OOM false. No relevant service restart/start/die event occurred in the two-hour window; observed Docker events were exec health/probe activity.
- Health/readiness: `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration and database `ok`; `/version` HTTP 200 with version `0.1.0`. The unauthenticated direct run-status probe returned 404 because the route requires the admin token; monitor evidence is authoritative and recorded HTTP 200.
- Scheduler: `/runtime/scheduler.heartbeat` in `cti-hermes-scheduler-1` read `2026-09-15T10:02:43Z`; scheduler logs had no matching error output. Monitor logs repeatedly reported only `last successful run stale, latest ingestion attempt failed`.
- Database/migrations: PostgreSQL 16.14 accepted `psql` connections; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration indication. The authoritative table is singular `public.ingestion_run` (plural probe correctly failed because that relation does not exist; no mutation resulted).
- Ingestion: run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, status `failed`, started 2026-09-15T02:00:00.049118Z, completed 2026-09-15T02:00:54.439155Z, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `ThreatFox Recent Indicators (Abuse.ch)` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`; persisted source configuration reports `max_response_bytes=10485760` and seven consecutive failures. Latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11T12:06:50Z, 38/38 sources.
- Downstream: report 186, report_version 201, publication 201, detection 378, hunt 201, remediation 201, relationship 11. Latest report/publication timestamp is 2026-09-11T22:24:37.163555Z.
- Resources: root filesystem 43% used with 278G available; host memory reports 51 GiB available; load `1.27 0.84 0.56`; open-file limit 4096. No disk, memory, or descriptor exhaustion indication.
- Backup: backup container is running and healthy, restart count 0. Mounted encrypted backup inventory reaches `/backups/hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) with `latest.metadata`; restore verification was not run.
- Certificate/proxy: Caddy is running with configured cert/data mounts. Recent logs show successful local certificate renewals for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy/certificate cause indicated.
- Deployment/config: checked-in `config/sources.json` declares ThreatFox `max_response_bytes=52428800`, while the running database/source configuration and failure prove the deployed boundary remains 10 MiB. Last checked-in application commit is `c925cd5` on 2026-09-12; no deployment or config mutation was made. Compose validation was not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`.

## Diagnosis, action, and recovery

This is a source/provider-specific deterministic ingestion failure: the deployed ThreatFox request exceeds the 10 MiB response limit. Web, proxy, scheduler, worker, PostgreSQL, disk, memory, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was suppressed by the cooldown gate.

- Service state: web/scheduler/monitor/database/backup/proxy healthy; one-source collection freshness degraded; full-success and downstream publication freshness stale.
- Action: diagnosis plus secret-free gate bookkeeping only. No service or data mutation.
- Rollback: not applicable; no application or data mutation occurred.

## Prevention / follow-up

1. With explicit maintenance/deployment authorization, validate provider-side filtering/pagination or the bounded 50 MiB configuration, including decompression and memory impact; retain an oversized-response regression fixture.
2. Run focused tests and deploy only with `./scripts/update-app.sh`; verify failed-source status, full-success/usable projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Reconcile operational probes with the deployed singular schema.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
