# Production ingestion incident: ThreatFox oversized response, diagnosis-only recovery suppression (22:32Z)

- **Recorded:** `2026-09-14T22:32:51.001774Z`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present before this record; this diagnosis added only this incident file.
- **Evidence source:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell, so the configured container-mounted fallback was used.

## Authoritative monitor evidence

The evidence read before gate evaluation was actionable:

- **State:** `actionable_failure`
- **Event ID:** `5e9ecfac-dd31-49b5-b1df-d6d8d32b0d1b`
- **Observed at:** `2026-09-14T22:30:29.627448+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `dffa6bb0-0a4c-4a8d-b568-a4614561ed41`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** full-success freshness `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest ingestion attempt `actionable_failure`, detail `1 source(s) failed`.

The verification read at `2026-09-14T22:32:29.785179+00:00` remained actionable with event `99631483-ed74-4986-8593-deef1f34b335`, correlation `1556c4e1-bd22-4d67-961d-ddb4500531cd`, and the same failed run.

## Diagnosis, impact, and confidence

The latest run is failed but usable: 38 sources attempted, 37 succeeded, 1 failed, and 12,831 new documents persisted. The latest full-success run was `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`, with 38/38 sources and 23,841 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`:

- `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`
- persisted source configuration remains `max_response_bytes=10485760`
- checked-in `config/sources.json` contains a staged `52428800` value, but the running image has not been updated

**Cause confidence: high.** This is a deterministic ThreatFox/provider response-size boundary mismatch, not a web, proxy, scheduler, database, disk, certificate, backup, or credential outage. Public CTI remains available from successful-source and partial-run data; ThreatFox coverage and complete-source freshness are degraded. No corruption, unauthorized publication mutation, or database-integrity damage was observed.

## Service and operational evidence

- **Application/image:** CTI containers use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; `/version` from the web container reports `0.1.0`.
- **Containers:** web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart count `0`, OOM `false`. Worker is intentionally absent/reserved. No restart loop.
- **Health/readiness:** direct host port 8000 was not published, so host curl returned connection refused; container health state is healthy and the monitor's authenticated internal `/api/v1/ops/run-status` check returned HTTP 200. No new external ingress mutation was made.
- **Scheduler/monitor:** scheduler heartbeat read back `2026-09-14T22:32:38Z`; monitor continuously reports stale full success plus failed latest attempt. No scheduler exception was observed.
- **Database:** `pg_isready` reports accepting connections; `current_database=hermes`, `current_user=hermes`; Alembic revision `0015_contradiction_lifecycle`. Counts: 27 ingestion runs, 800 source runs, 32,890 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Failed source row preserves the oversized-response classification and detail.
- **Capacity:** root filesystem 43% used with 279 GiB available; host memory approximately 52 GiB available; open-file limit 4,096. No exhaustion indicated. Docker reports no active resource pressure.
- **Backups:** `/backups/latest.metadata` points to `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; no backup mutation or deletion occurred.
- **Certificate/proxy:** no new Caddy error evidence was present; no proxy or certificate action was taken.
- **Last deployment/config boundary:** CTI containers started `2026-09-12T12:55:15Z`–`12:55:20Z`. `config/sources.json` was modified `2026-09-12 19:24:50 -0500`; no deployment was performed.
- **Compose validation note:** `docker compose ps` could not interpolate the file in the cron shell because `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported. Existing container state was inspected read-only with Docker directly; no secrets were read or printed.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable evidence with the configured 1,800-second cooldown and shared lock:

- **Gate event:** `5e9ecfac-dd31-49b5-b1df-d6d8d32b0d1b`
- **Gate correlation:** `dffa6bb0-0a4c-4a8d-b568-a4614561ed41`
- **Gate decision:** allowed to acquire evidence-backed gate
- **Attempt recorded:** `2026-09-14T22:31:27.702288Z`
- **Completion:** `2026-09-14T22:32:51.001774Z`, outcome `suppressed`
- **Lock read-back:** absent

Diagnosis was authorized but recovery was not. Therefore no ingestion retry, service restart, `./scripts/update-app.sh`, migration, response-limit change, credential change, volume/data/backup deletion, or publication mutation was performed. The monitor evidence, failed ThreatFox source row, partial-run data, and recovery audit remain preserved.

## Prevention and rollback

Under explicit recovery/deployment authorization, validate ThreatFox provider-side filtering or pagination against an offline fixture, retain an oversized-response regression test, reconcile the staged `config/sources.json` value with the running image, then run focused tests and `./scripts/update-app.sh`. Verify the next source status, full-success/usable run semantics, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback. No rollback is required because no application or data mutation occurred.
