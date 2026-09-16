# Production ingestion incident: actionable failure diagnostic (16:31Z)

- **Observed at:** 2026-09-14T16:31:03.949931+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `7d8b5216-d339-4de5-8df9-ea28529eab54`
- **Correlation ID:** `aa21e891-1c70-41bb-9619-be51ea35ffdf`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured Compose path was used.
- **Checked at:** 2026-09-14T16:31:48Z
- **Repository:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree has pre-existing unrelated changes and deletions.

## Impact and persisted data

The latest scheduled collection is failed but partially usable: 37 of 38 sources succeeded, 1 failed, and 1,564 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; its freshness is stale. Current persisted totals are 31,678 source documents (latest retrieval 2026-09-14 02:00:05.858334Z), 186 reports, 201 report versions, and 201 publications (latest publication 2026-09-11 22:24:37.183379Z). Successful evidence and the failed source-run record remain preserved.

## Diagnosis and evidence

**Cause confidence: high.** This is a persistent ThreatFox/Abuse.ch provider-response-size failure at the source boundary, not a web, proxy, worker, scheduler, PostgreSQL, disk, certificate, backup, migration, or publication outage.

- Latest run: scheduled 2026-09-14 02:00:00Z; completed 2026-09-14 02:00:06.398193Z; status `failed`; 38 total / 37 successful / 1 failed; error summary `1 source(s) failed`.
- Failed source: `threatfox-recent-indicators-abuse-ch`; item count 0; HTTP status absent; cache `miss`; retry count 0; classification `oversized_response`; detail `response exceeds 10485760 bytes`.
- Source state: `max_response_bytes=10485760`; last successful retrieval 2026-09-11 12:06:49.272951Z; last failure 2026-09-14 02:00:06.395880Z; consecutive failures 5.
- Checked-in `config/sources.json` contains an uncommitted ThreatFox `max_response_bytes=52428800` change, but the running image predates it; no deployment was performed.
- PostgreSQL is accepting connections; Alembic revision is `0015_contradiction_lifecycle`; all 38 expected public tables are present. No pending or failed migration evidence was found.
- Web, scheduler, monitor, PostgreSQL, and backup are running/healthy with restart count 0. Worker is intentionally exited with code 0 and has no restart loop.
- Web probes returned `/health/live` HTTP 200 and `/health/ready` HTTP 200 with database/configuration `ok`. Scheduler heartbeat was present and current at 2026-09-14 16:32:36Z.
- Host disk is 43% used with 279G available; memory available is 51GiB; host open-file limit is 4096; web soft limit is 1024. No OOM evidence was observed.
- Backup is healthy; `latest.metadata` was updated 2026-09-14 12:55:23Z and the latest artifact is `hermes-20260914T125520Z.dump.enc` (metadata size 198 bytes).
- Caddy logs show successful local certificate renewal for `hermes.cti.scogin.dev`; certificate state is not the ingestion cause. Docker events in the observation window showed routine health-check execs and no CTI-Hermes restart.
- Scheduler/web logs showed successful health and run-status probes plus repeated monitor failure labels; no service crash evidence.

## Recovery gate and actions

The authoritative monitor evidence was read before gate evaluation. The 30-minute cooldown/lock gate allowed an evidence-backed attempt at 2026-09-14T16:32:00.159559Z and recorded attempted event `7d8b5216-d339-4de5-8df9-ea28529eab54`, correlation `aa21e891-1c70-41bb-9619-be51ea35ffdf`, for run `3848465e-e2a0-572a-b522-4c768d790284`. This diagnosis-only request does not authorize retry, restart, deployment, migration, source-limit change, credential change, or data mutation. The gate was completed with outcome `suppressed` at 2026-09-14T16:32:11.697887Z; the audit was read back and the runtime lock was verified absent.

No recovery action was taken.

## State, rollback, and prevention

- **Service:** internally live and ready; collection freshness degraded and one source unavailable.
- **Data integrity:** preserved; partial ingestion, failed-source evidence, reports/publications, and backups remain intact.
- **Rollback:** not applicable; no application or deployment change was made.
- **Operational limitation:** host-side Compose inspection was unavailable because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; direct Docker inspection was used instead.
- **Prevention:** bound or paginate the ThreatFox request while preserving `oversized_response`; retain/add an oversized-response regression fixture; under explicitly authorized maintenance, deploy the checked-in source configuration via `./scripts/update-app.sh`; verify the next run, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback. Continue separate Caddy route/TLS and operational query/schema follow-up.
