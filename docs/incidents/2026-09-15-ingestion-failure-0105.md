# Production ingestion incident: ThreatFox bounded-response failure (01:05Z)

## Classification

- **Impact:** ingestion remains partially degraded. Latest scheduled run `20c8d81a-48e4-5215-8292-63a72ddac05d` processed 37/38 sources and failed only `threatfox-recent-indicators-abuse-ch`.
- **Monitor state:** `actionable_failure`.
- **Cause confidence:** high for the immediate cause (deployed 10 MiB response-size guard rejecting the ThreatFox response); low-to-medium for the upstream payload growth cause.
- **Data integrity:** no database reset, volume deletion, migration, credential rotation, evidence deletion, restart, rerun, or deployment was performed. Failed source/run records and successful partial-run data remain preserved.

## Authoritative monitor evidence

Read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`:

- `state=actionable_failure`
- `event_id=c619db8b-47d5-4fdb-bc00-42caa60fdb30`
- `observed_at=2026-09-15T01:01:40.400406+00:00`
- `correlation_id=9698c1fd-31ab-4fea-8b65-ac92e18fd849`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`, detail `1 source(s) failed`

## Recovery gate

The 30-minute cooldown and shared lock were checked. The gate was acquired at `2026-09-15T01:05:00.587640+00` with event ID `dfad506e-4eb5-4bc5-a118-71846a2f2c1f`, correlation `f9d75524-b072-41c5-bfec-52d34d9845d9`, and run `20c8d81a-48e4-5215-8292-63a72ddac05d`. Because this scheduled request authorizes diagnosis only, recovery was suppressed. Completed outcome was recorded at `2026-09-15T01:05:00.587978+00`; read-back verified `/runtime/recovery.lock` is absent.

## Evidence collected

- **Release/deployment:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; running image `cti-hermes:local`, ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`; application version `0.1.0` from the persisted run. All CTI containers started 2026-09-12 and report restart count 0. Working tree has substantial pre-existing changes; no deployment/config update was run.
- **Database/migrations:** PostgreSQL accepting connections as `hermes` on database `hermes`; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration observed. Authoritative schema uses singular tables (`ingestion_run`, `source_run`).
- **Runs/source:** latest run started `2026-09-14T18:32:12.667740+00` and failed `2026-09-14T18:33:07.628491+00`; 38 total, 37 successful, 1 failed, 12,831 new documents. Failed source has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Last full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` at `2026-09-11T12:06:50.050468+00`.
- **Analysis/publication:** reports count 186 and publications count 201; both latest timestamps are `2026-09-11T22:24:37.163555+00`, so publication is stale alongside full-success ingestion.
- **Services/health:** monitor, web, scheduler, PostgreSQL, and backup are running and healthy with zero restarts. The worker container is exited with code 0 since `2026-09-12T12:55:16Z` by design; its log says it is reserved for a later analysis phase, so it is not the ingestion owner. Monitor evidence observed the internal run-status endpoint with HTTP 200. Scheduler heartbeat was fresh at `2026-09-15 01:03:09 UTC`. No container restart events were observed in the checked window.
- **Resources:** root filesystem 43% used (279G available), host memory 62 GiB total / 52 GiB available, container FD limits 1024; no exhaustion indication.
- **Backups:** `/backups/latest.metadata` identifies encrypted artifact `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no proxy or certificate failure observed.
- **Logs:** monitor repeatedly reports stale last success and failed latest attempt. PostgreSQL contains repeated operator diagnostic queries against nonexistent plural tables/columns; these are query/schema-drift errors, not application transaction failures. Scheduler emitted no useful log output.

## Diagnosis and follow-up

The web, proxy, worker/scheduler, database, disk, certificate, and backup services are not the cause. The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. The checked-out but undeployed `config/sources.json` raises this source's `max_response_bytes` to 50 MiB. No recovery or deployment was authorized here.

Under explicit maintenance/deployment authorization, review the bounded ThreatFox change and memory/decompression implications, run focused regression tests, then deploy only with `./scripts/update-app.sh`. Verify the next run's failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE` and correct future operational queries to the singular schema.

**Rollback:** not applicable; no application or data mutation was performed. Gate audit read-back succeeded and lock is absent.
