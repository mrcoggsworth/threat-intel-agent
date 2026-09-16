# Production ingestion incident: actionable partial-ingestion failure, recovery gated (23:17Z)

- **Recorded:** `2026-09-14T23:17:37Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present. This diagnosis added only this incident record; no application files were changed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before gate evaluation:

- **State:** `actionable_failure`
- **Event ID:** `afd789b9-f665-49f9-bdda-9e7896869bac`
- **Observed at:** `2026-09-14T23:15:32.790561+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `aed1f10d-1eef-49b0-8ecf-cd3b11a17abc`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** `full_success_freshness=stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.

## Diagnosis and impact

The latest run is failed but usable: 38 sources attempted, 37 succeeded, 1 failed, and 12,831 new documents persisted. The failed source is `ThreatFox Recent Indicators (Abuse.ch)`:

- `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`
- persisted source limit is `10485760` bytes; source consecutive failure count is `6`
- last successful retrieval was `2026-09-11 12:06:49.272951+00`
- checked-in `config/sources.json` contains a pre-existing staged `max_response_bytes=52428800`, but it has not been deployed

**Cause confidence: high.** Evidence indicates a deterministic ThreatFox/provider response-size boundary mismatch, not a web, proxy, scheduler, database, disk, memory, certificate, backup, credential, or publication outage. Public CTI from successful sources and the usable partial run remains available; ThreatFox coverage, full-success freshness, and downstream report/publication freshness are degraded. No corruption or unauthorized publication mutation was observed.

## Service, data, and operational evidence

- **Application/image:** `cti-hermes:local`, application `/version` `0.1.0`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- **Containers:** web, scheduler, monitor, backup, and PostgreSQL are running and healthy with restart count `0` and OOM `false`; reserved worker exited `0` and is not involved. No restart loop.
- **Health/readiness:** `/health/live` HTTP `200` (`{"status":"ok"}`); `/health/ready` HTTP `200` with configuration/database `ok`; `/version` HTTP `200`. Scheduler heartbeat was `2026-09-14T23:17:39Z`.
- **Database:** `pg_isready` accepted connections; database `hermes`, user `hermes`; migration revision `0015_contradiction_lifecycle`. Counts: 27 ingestion runs, 800 source runs, 32,890 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Latest full-success run completed `2026-09-11 12:06:50.050468+00`; latest publication is `2026-09-11 22:24:37.163555+00`. No pending/failed migration evidence was observed.
- **Capacity:** root filesystem 43% used with 279 GiB available; host memory approximately 52 GiB available; open-file limit 4,096. No resource exhaustion indicated.
- **Backups:** `/backups/latest.metadata` exists and the latest encrypted dump `hermes-20260914T125520Z.dump.enc` is present (22,608,400 bytes); no backup mutation or deletion occurred. Restore verification was not run.
- **Certificate/proxy:** certificate expiry was not independently verified because the configured host certificate path was absent in this execution environment; no proxy/certificate action was taken. Internal web routing is healthy.
- **Logs/events:** monitor repeatedly reports stale full success plus failed latest attempt; bounded web checks are successful; no CTI container restart, die, recreate, or OOM event was observed. PostgreSQL contains prior operator diagnostic query errors (wrong relation/columns), which were read-only and unrelated to the ingestion failure.
- **Deployment/config boundary:** CTI containers started `2026-09-12T12:55:15Z`–`12:55:20Z`; `config/sources.json` was modified `2026-09-12 19:24:50 -0500`; no deployment or stack update was performed. Compose validation was not run because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported; secrets were not read or printed.

## Recovery gate and actions

The shared recovery gate was evaluated after reading the actionable evidence using the configured 1,800-second cooldown and lock. The gate recorded an attempted event and it was immediately completed as failed because no safe reversible recovery was authorized for a deterministic provider response-size failure:

- **Gate event ID:** `ea679849-fa7a-4807-9370-21cbe694e5fc`
- **Gate correlation ID:** `5c7c63de-0d23-4b02-bf1a-6d9c918afcad`
- **Gate run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Attempt:** recorded at `2026-09-14T23:17:11.356895+00Z`
- **Completion:** `outcome=failed`, recorded at `2026-09-14T23:17:37.316084+00Z`
- **Lock read-back:** absent

No ingestion retry, service restart, migration, response-limit change, credential change, `./scripts/update-app.sh`, volume/data/backup deletion, or publication mutation was performed. Failed-source evidence, successful-source evidence, partial-run data, and recovery audit records remain preserved.

## Rollback and prevention

- **Rollback:** not applicable; no application, service, database, migration, configuration, or publication mutation occurred. Only recovery-gate audit bookkeeping and this incident record were written.
- **Authorized follow-up:** validate ThreatFox filtering/pagination or an alternate endpoint with an offline fixture; retain an oversized-response regression test; reconcile the staged source configuration with the running image; then deploy only via `./scripts/update-app.sh` under explicit authorization and verify the next run, monitor evidence, and publication/data integrity.
- Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback.
- Correct operational diagnostic query/schema drift, independently verify certificate state, and perform encrypted backup restore verification in a maintenance window.
