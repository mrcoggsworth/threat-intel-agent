# Production ingestion incident: actionable partial-ingestion failure, recovery suppressed (23:02Z)

- **Recorded:** `2026-09-14T23:02Z`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present; this diagnosis added only this incident file.
- **Monitor evidence:** `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

## Authoritative monitor evidence

The latest read before gate evaluation was actionable:

- **State:** `actionable_failure`
- **Event ID:** `fdd6ba4d-5bcb-4b58-bbe7-29233475c486`
- **Observed at:** `2026-09-14T23:00:31.750493+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `489efb11-e5e4-482b-9e80-6790634d5da2`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** full-success freshness `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest ingestion attempt `actionable_failure`, detail `1 source(s) failed`.

## Diagnosis, impact, and confidence

The latest run is failed but usable: 38 sources attempted, 37 succeeded, 1 failed, and 12,831 new documents persisted. The failed source is `threatfox-recent-indicators-abuse-ch`:

- `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`
- persisted source configuration remains `max_response_bytes=10485760`
- checked-in `config/sources.json` contains a staged `52428800` value, but no deployment was authorized or performed

**Cause confidence: high.** This is a deterministic ThreatFox/provider response-size boundary mismatch, not evidence of a web, proxy, scheduler, database, disk, certificate, backup, or credential outage. Public CTI remains available from successful-source and partial-run data; ThreatFox coverage and complete-source freshness are degraded. No corruption or unauthorized publication mutation was observed.

## Service and operational evidence

- **Application/image:** containers use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; `/version` reports `0.1.0`.
- **Containers:** web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart count `0`, OOM `false`. Worker is intentionally reserved and exited `0`; it is reported unhealthy because it is stopped. No restart loop.
- **Health/readiness:** web `/version` succeeded; monitor's internal ops endpoint returned HTTP 200; scheduler heartbeat was current at `2026-09-14 23:02:38Z`; monitor evidence refreshed at `23:02:31Z` and remained actionable. No external ingress mutation was made.
- **Database:** `pg_isready` reports accepting connections; `current_database=hermes`, `current_user=hermes`; Alembic revision `0015_contradiction_lifecycle`. Counts: 27 ingestion runs, 800 source runs, 32,890 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. The failed source row preserves the oversized-response classification and detail. No pending/failed migration was observed from `alembic_version`.
- **Capacity:** root filesystem 43% used with 279 GiB available; host memory approximately 52 GiB available; open-file limit 4,096. No exhaustion indicated.
- **Backups:** `latest.metadata` exists, size 198 bytes, mtime `2026-09-14 12:55:23Z`; latest backup `hermes-20260914T125520Z.dump.enc` exists at 22,608,400 bytes. No backup mutation or deletion occurred. Encrypted restore verification was not run during diagnosis.
- **Certificate/proxy:** the configured host certificate path `/var/lib/cti-hermes/tls/fullchain.pem` was absent in this execution environment, so certificate expiry could not be independently verified. No proxy or certificate action was taken. Web health and internal routing were healthy.
- **Last deployment/config boundary:** CTI containers started `2026-09-12T12:55:15Z`–`12:55:20Z`. `config/sources.json` was modified `2026-09-12 19:24:50 -0500`; no deployment was performed.
- **Compose validation:** `docker compose -f deploy/docker-compose.yml ps --all` could not interpolate because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported. Existing container state was inspected read-only with Docker directly; secrets were not read or printed.
- **Logs/events:** monitor repeatedly recorded stale full success plus failed latest attempt; web health/readiness and ops checks returned 200; no application restart/OOM events were observed. PostgreSQL logs include several operator diagnostic queries using incorrect table/column names; these did not mutate data and do not explain the ingestion failure.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable evidence with the configured 1,800-second cooldown and shared lock:

- **Gate event:** `fdd6ba4d-5bcb-4b58-bbe7-29233475c486`
- **Gate correlation:** `489efb11-e5e4-482b-9e80-6790634d5da2`
- **Gate decision:** suppressed; reason `recovery cooldown is active`
- **Outcome:** no recovery attempt permitted; lock read-back `absent`

Diagnosis was authorized but destructive recovery was not. Therefore no ingestion retry, service restart, `./scripts/update-app.sh`, migration, response-limit change, credential change, volume/data/backup deletion, or publication mutation was performed. Monitor evidence, failed source row, partial-run data, and recovery audit remain preserved.

## Prevention, rollback, and follow-up

- Under explicit recovery/deployment authorization, validate ThreatFox provider-side filtering or pagination against an offline fixture, retain an oversized-response regression test, reconcile the staged `config/sources.json` value with the running image, then run focused tests and `./scripts/update-app.sh`.
- Verify the next source status, full-success/usable run semantics, monitor evidence, and publication/data integrity after any authorized change.
- Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback.
- Repair the operational diagnostic query/schema drift before the next incident review.
- Independently verify certificate state and perform encrypted backup restore verification in a maintenance window.
- **Rollback:** not applicable; no application, data, service, migration, or configuration mutation was made. The only writes were recovery-gate audit bookkeeping and this incident record.
