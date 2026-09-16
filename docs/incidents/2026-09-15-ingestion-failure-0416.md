# Production ingestion incident: ThreatFox bounded-response failure (04:16Z)

## Classification

- **Recorded:** 2026-09-15T04:16:35Z
- **Impact:** ingestion remains partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. Successful source data remains usable, but no new full-success run exists and analyst/publication freshness remains stale.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream ThreatFox payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

Read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`:

- `state=actionable_failure`
- `event_id=f7c3bb79-2fa6-4b32-baaf-e9034cf0d1a7`
- `observed_at=2026-09-15T04:15:54.415409+00:00`
- `correlation_id=71ee9da3-450b-431f-82b1-ec7f06486841`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The recovery gate was evaluated against the authoritative evidence using the container-mounted state directory. It returned `allowed=false`, reason `recovery cooldown is active`, for event `f7c3bb79-2fa6-4b32-baaf-e9034cf0d1a7` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. The gate recorded a suppressed event at `2026-09-15T04:16:35.000351+00`; `/runtime/recovery.lock` is absent. No recovery action was attempted.

## Evidence collected

- **Time/release:** current UTC observation `2026-09-15T04:16:01Z`; repository branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; running image `cti-hermes:local`, application version `0.1.0`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12. The working tree has substantial pre-existing changes; no deployment or config update was run.
- **Ingestion:** latest run started `2026-09-15T02:00:00.049118+00`, completed `2026-09-15T02:00:54.439155+00`, status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Configuration hash remains `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- **Database/migrations:** PostgreSQL `pg_isready` returned accepting connections. Alembic revision is `0015_contradiction_lifecycle`; authoritative tables are singular (`ingestion_run`, `source_run`). No migration execution or pending/failed migration evidence was observed. An attempted diagnostic query using obsolete `run_id` and `summary` column names failed, confirming operational schema drift only, not an application transaction failure.
- **Pipeline freshness:** `source_document` total 33,797, latest 2026-09-15T02:00:54Z; `report` 186, `report_version` 201, `publication` 201, `detection` 378, `hunt` 201, `remediation` 201, all latest 2026-09-11T22:24:37Z; `relationship` 11, latest 2026-09-01T08:03:29Z. This is a stage-separated ingestion/publication freshness gap, not a web-rendering-only issue.
- **Services/restarts:** monitor, web, scheduler, backup, and PostgreSQL containers are running and healthy with restart count 0. Worker is exited code 0 by design (`restart: no`); runtime-init is also exited code 0. Scheduler heartbeat was fresh at 2026-09-15T04:16:41Z. Web logs show health/readiness HTTP 200; an unauthenticated local `/api/v1/ops/run-status` probe returned 404 and is not evidence of service failure because the monitor's authenticated internal endpoint returned 200.
- **Logs/events:** scheduler reports `source collection failed`; monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`. Docker events show only routine health-check/diagnostic execs during the observation window; no service restart or crash event was observed.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total, 52GiB available; file-descriptor limit 4096. No resource exhaustion indication.
- **Backup:** `/backups/latest.metadata` exists, 198 bytes, timestamp 2026-09-14T12:55:23Z. The metadata contents were permission-protected from the monitor container; artifact identity/hash and restore verification were not re-read in this check. No backup mutation was performed.
- **Certificate/proxy:** Caddy logs show successful local certificate renewals and cache reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy or certificate failure observed.

## Diagnosis and follow-up

The failure is source/provider-specific: the running implementation rejects a ThreatFox response larger than 10 MiB. The checked-out but undeployed `config/sources.json` contains the bounded 50 MiB adjustment. Web, proxy, worker, scheduler, database, disk, certificate, and backup are not indicated as causes.

Recovery is blocked by the cooldown and was not authorized by this diagnosis-only request. Under explicit maintenance/deployment authorization, review the ThreatFox limit change and memory/decompression implications, run focused regression tests, then deploy only with `./scripts/update-app.sh`. Verify the next run's failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE`, provide protected Compose variables to maintenance jobs, and use singular schema names in diagnostics.

**Rollback:** not applicable; no application or data mutation was performed. Gate suppression and lock absence were verified.
