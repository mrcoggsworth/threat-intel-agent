# Production ingestion incident: actionable failure diagnostic (16:01Z)

- **Observed at:** 2026-09-14T16:00:01.718858Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `fde68072-8fd1-43dd-89df-790b5acf997b`
- **Correlation ID:** `41b790f2-1112-4719-807e-aa420f05057b`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured container-mounted evidence file was used.
- **Checked at:** 2026-09-14T16:01:52Z
- **Repository:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree contains pre-existing unrelated modifications/deletions.
- **Application:** version `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T12:54:53Z.

## Impact and persisted data

The latest scheduled collection is failed but usable in part: 37 of 38 sources succeeded and 1,564 documents were newly persisted. The failed source remains recorded as a failed `source_run`; successful results and prior evidence remain available. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11T12:06:50.050468Z, so full-success freshness is stale. Current persisted counts are 31,678 source documents (latest retrieval 2026-09-14T02:00:05.858334Z), 186 reports, 201 report versions, and 201 publications (latest publication 2026-09-11T22:24:37.163555Z).

## Diagnosis and evidence

Cause confidence is **high**: this is a persistent ThreatFox/Abuse.ch provider-response-size boundary failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, or publication outage.

- Failed source: `threatfox-recent-indicators-abuse-ch`; source status `failed`; item count `0`; HTTP status absent; cache `miss`; retry count `0`.
- Classification: `oversized_response`; detail: `response exceeds 10485760 bytes`.
- Latest run: scheduled 2026-09-14T02:00:00Z; completed 2026-09-14T02:00:06.398193Z; 38 total / 37 successful / 1 failed.
- Source state: `max_response_bytes=10485760`, last successful retrieval 2026-09-11T12:06:49.272951Z, last failure 2026-09-14T02:00:06.395880Z, consecutive failures `5`.
- Checked-in `config/sources.json` has an uncommitted ThreatFox `max_response_bytes=52428800` change, but the running image predates it; no deployment was performed.
- PostgreSQL accepts connections (`pg_isready`); Alembic revision is `0015_contradiction_lifecycle`; all 38 expected public tables are present. No pending or failed migration evidence was found.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running/healthy with restart count `0`. Worker is intentionally exited with code `0` and has no restart loop.
- In-container probes: `/health/live` HTTP 200, `/health/ready` HTTP 200 with database/configuration `ok`, `/version` HTTP 200 (`0.1.0`). The monitor endpoint returned HTTP 200; the direct web path used for probing did not expose that route and returned 404, which is not a service-health failure.
- Scheduler heartbeat is present and current (`/runtime/scheduler.heartbeat`, updated 2026-09-14T16:02:36Z). Monitor logs continue to report only stale full-success and failed latest attempt.
- Host root filesystem is 43% used with 279G available; host memory available is 51GiB; host open-file limit is 4096. Web soft open-file limit is 1024. No OOM evidence observed.
- Backup is healthy: `/backups/hermes-20260914T125520Z.dump.enc`, completed 2026-09-14T12:55:23Z, 22,608,400 bytes; metadata records SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`.
- Caddy is running without restart and logs show successful local certificate renewal for `hermes.cti.scogin.dev`; certificate/TLS is not the ingestion cause.
- Docker events during the observation window show routine health-check execs and no CTI-Hermes container restart.

## Recovery gate and actions

The authoritative monitor evidence was read before gate evaluation. The 30-minute cooldown/lock gate allowed an evidence-backed attempt at 2026-09-14T16:01:52.914741Z and recorded attempted event `28b3687c-4a42-4abf-b4b8-ac36e0bbf62b`, correlation `af6c88e6-1a5d-41fc-a955-349363cf7d90`, for run `3848465e-e2a0-572a-b522-4c768d790284`. Because this request authorizes diagnosis only, the gate was completed with `outcome=suppressed`; no retry, restart, deployment, migration, source-limit change, credential change, or data mutation was performed. The runtime lock was verified absent and the audit records were read back.

## Service, integrity, and rollback state

- **Service:** internally live and ready; collection freshness degraded and one source unavailable.
- **Data integrity:** preserved. Partial successful ingestion, failed-source evidence, reports/publications, and backups remain intact.
- **Rollback:** not applicable; no application or deployment change was made.
- **Compose validation note:** host-side `docker compose ... ps` could not interpolate protected variables because the cron shell lacked `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an execution-environment limitation, not evidence of a stack outage.

## Prevention / follow-up

1. Bound or paginate the ThreatFox request below the transport limit while preserving the `oversized_response` classification; add an oversized-response regression fixture/test.
2. Under explicitly authorized maintenance/deployment work, reconcile the checked-in source configuration with the running image using `./scripts/update-app.sh`; verify the next run, failed-source status, monitor evidence, and publication/data integrity.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container-mounted fallback.
4. Add a deployment check comparing persisted source configuration with checked-in configuration, and investigate the recurring operational query/schema drift separately.
