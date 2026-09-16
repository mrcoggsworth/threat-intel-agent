# Production ingestion incident: actionable failure diagnostic (17:01Z)

- **Observed at:** 2026-09-14T17:00:05.953778+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `95c708c8-3ea5-455d-9c5a-57f85e12232c`
- **Correlation ID:** `91e4e9e2-fdad-438d-b596-77fe93deeb5a`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was not exported by the cron shell, so the configured container-mounted fallback was used.
- **Checked at:** 2026-09-14T17:01:18Z
- **Repository:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree has pre-existing unrelated modifications, deletions, and scratch files.
- **Application:** version `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T12:55:03Z.

## Impact and persisted data

The latest scheduled collection is failed but usable in part: 37 of 38 sources succeeded and 1,564 new documents were persisted. The failed source remains recorded as a failed `source_run`; successful results and prior evidence remain available. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11T12:06:50.050468Z. The latest usable run is the failed-but-partial run above. Current database counts are 31,678 source documents (latest retrieval 2026-09-14T02:00:05.858334Z), 186 reports, 201 report versions, and 201 publications (latest publication 2026-09-11T22:24:37.183379Z).

## Diagnosis and evidence

Cause confidence is **high**: persistent ThreatFox/Abuse.ch provider-response-size failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, or publication outage.

- Failed source: `threatfox-recent-indicators-abuse-ch`; status `failed`; item count `0`; HTTP status absent; cache `miss`; retry count `0`.
- Classification/detail: `oversized_response`; `response exceeds 10485760 bytes`.
- Latest run: scheduled `2026-09-14T02:00:00Z`; completed `2026-09-14T02:00:06.398193Z`; 38 total / 37 successful / 1 failed.
- Source state: last successful retrieval `2026-09-11T12:06:49.272951Z`; consecutive failures remain `5`.
- Checked-in `config/sources.json` contains an uncommitted ThreatFox `max_response_bytes=52428800` change, while the running image still has the prior 10 MiB limit. No deployment was performed.
- `/health/live`, `/health/ready`, `/version`, and the authenticated run-status probe returned HTTP 200. Readiness reported database/configuration `ok`.
- PostgreSQL accepts connections; Alembic revision is `0015_contradiction_lifecycle`; 38 public tables are present. No pending or failed migration evidence was found.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running/healthy with restart count `0`. Worker is intentionally exited with code `0` and has no restart loop.
- Scheduler heartbeat was current at `2026-09-14 17:01:36Z`; monitor logs show only stale full-success and failed latest-attempt conditions.
- Host root filesystem is 43% used with 279G available; 51GiB memory available; host open-file limit 4096. No OOM evidence observed.
- Backup metadata reports `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`.
- Caddy certificate for `hermes.cti.scogin.dev` is valid from 2026-09-14T15:39:23Z through 2026-09-15T03:39:23Z; recent renewal is not the ingestion cause.
- Docker events during the window showed health-check execs only; no CTI-Hermes restart.

## Recovery gate and actions

The authoritative evidence was read before gate evaluation. The 1,800-second cooldown and shared lock were checked. The gate recorded:

- **Gate event:** `31c5ae5c-97e8-4dea-86ea-9ebb0cd9869f`
- **Gate correlation:** `f29312ba-718e-42c3-89ae-59ff358fdf58`
- **Result:** `suppressed`; reason `recovery cooldown is active`; lock verified absent.

This request authorizes diagnosis only. No ingestion retry, service restart, deployment via `./scripts/update-app.sh`, migration, source-limit change, credential change, volume/data deletion, or publication mutation was performed. The gate audit was read back successfully.

## Service, integrity, and rollback state

- **Service:** internally live and ready; ingestion freshness degraded and one source unavailable.
- **Data integrity:** preserved. Partial successful ingestion, failed-source evidence, reports/publications, and backups remain intact.
- **Rollback:** not applicable; no application or deployment change was made.

## Prevention / follow-up

1. Under explicitly authorized maintenance/deployment work, deploy the already-present bounded ThreatFox response-limit change with `./scripts/update-app.sh`, after adding/confirming an oversized-response regression fixture.
2. Verify the next scheduled run's failed-source status, monitor evidence, and publication/data integrity; preserve any failure classification.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container-mounted fallback.
4. Add a deployment check comparing persisted source configuration with checked-in configuration and investigate recurring operational query/schema drift separately.
