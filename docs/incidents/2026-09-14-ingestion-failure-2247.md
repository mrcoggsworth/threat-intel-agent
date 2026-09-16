# Production ingestion incident: ThreatFox oversized response, cooldown suppression (22:47Z)

- **Recorded:** `2026-09-14T22:47:09Z` (host clock)
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present; this incident record is the only change made by this diagnosis.
- **Evidence source:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured container fallback was used.

## Authoritative monitor evidence

Evidence was read before gate evaluation and was actionable:

- **State:** `actionable_failure`
- **Event ID:** `cf1ce4c5-fb15-4d21-bfd8-9dc4f60bfa7f`
- **Observed at:** `2026-09-14T22:47:30.849727+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `5fadeee9-5612-4b28-bc20-dfa906b745c7`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** full-success freshness is `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest ingestion attempt is `actionable_failure`, HTTP `200`, detail `1 source(s) failed`.

## Diagnosis and impact

The latest run is failed but usable: 38 sources attempted, 37 succeeded, 1 failed, and 12,831 new documents persisted. The failed source is `threatfox-recent-indicators-abuse-ch`:

- `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`
- persisted source configuration has `max_response_bytes=10485760`
- checked-in `config/sources.json` has a staged `max_response_bytes=52428800`, but the running image omits that value and has not been updated
- source consecutive failure count is `6`; last successful retrieval was `2026-09-11T12:06:49.272951+00Z`

**Cause confidence: high.** This is a deterministic provider response-size boundary mismatch, not an observed web, proxy, scheduler, database, disk, certificate, backup, or credential outage. Public CTI remains available from successful-source and partial-run data; ThreatFox coverage and complete-source freshness are degraded. No database-integrity, corruption, or unauthorized publication mutation was observed.

## Operational evidence

- **Application/image:** web, scheduler, and monitor use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; database is `postgres:16-alpine`; `/version` is not exposed as a file in the checked path, while the persisted run reports application version `0.1.0`.
- **Container state:** web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart count `0`, OOM `false`; worker is intentionally absent/reserved. No restart loop or Docker resource pressure observed. Containers started `2026-09-12T12:55:15Z`–`12:55:20Z` except PostgreSQL, which started `2026-09-05T16:36:57Z`.
- **Health/readiness:** container health checks are healthy. Internal monitor checks to `/api/v1/ops/run-status` return HTTP 200. No external ingress change was made; direct web curl from the container was unavailable because curl is not installed there.
- **Scheduler/monitor:** monitor repeatedly logs `last successful run stale, latest ingestion attempt failed`; no scheduler exception appeared in the bounded log sample. Recovery lock read-back is absent.
- **Database/migrations:** `pg_isready` reports accepting connections; `current_database=hermes`, `current_user=hermes`; Alembic revision is `0015_contradiction_lifecycle`. The `alembic` executable is not installed in the application image, so `alembic check` could not be run; no pending/failed migration evidence was observed from the available runtime checks.
- **Persistence/publication:** database currently contains 27 ingestion runs, 800 source runs, 32,890 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Latest full-success run completed `2026-09-11T12:06:50.050468Z`; latest report/version/publication timestamps are `2026-09-11T22:24:37Z`.
- **Docker events/restart history:** the 24-hour event stream showed only health-check `exec_create`/`exec_start`/`exec_die` activity for CTI containers, including successful readiness checks; no `restart`, `die`, `oom`, or recreate event was observed. Container inspect restart counts remain `0`.
- **Capacity:** root filesystem is 43% used with 279 GiB available; host memory availability is approximately 52 GiB; host open-file limit is 4,096 and web container limit is 1,024. No exhaustion is indicated. Current container memory is low (web 281.7 MiB, scheduler 361.5 MiB, monitor 24.6 MiB, PostgreSQL 257.7 MiB).
- **Backups:** `/backups/latest.metadata` reports `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. No backup mutation or deletion occurred.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no TLS/proxy error was observed.
- **Last deployment/config boundary:** CTI containers started `2026-09-12T12:55:15Z`–`12:55:20Z`; checked-in `config/sources.json` mtime is `2026-09-12 19:24:50 -0500`; no deployment or stack update was performed.

## Recovery gate and actions

The shared recovery gate was evaluated after authoritative evidence with the 1,800-second cooldown and lock:

- **Gate decision:** `allowed=false`, reason `recovery cooldown is active`
- **Gate event ID:** `9126c726-a744-447b-8c2b-ff729b4c0918`
- **Gate correlation ID:** `d43c5e22-0662-4dd7-b9d8-8dfacd24e4b0`
- **Gate run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Suppressed event:** read back from `/runtime/recovery-events.jsonl` at `2026-09-14T22:46:51.669984+00Z`
- **Lock read-back:** absent

Because this cron request authorizes diagnosis but not destructive recovery, no retry, restart, migration, source-limit change, credential change, `./scripts/update-app.sh`, volume/data/backup deletion, or publication mutation was performed. No rollback is required because no application or data mutation occurred.

## Prevention and follow-up

Under explicit recovery/deployment authorization, validate ThreatFox provider-side filtering or pagination (or an alternate endpoint) against an offline fixture, retain an oversized-response regression test and bounded transport limit, reconcile the staged `config/sources.json` with the running image via `./scripts/update-app.sh`, and verify the next source status, full-success/usable run semantics, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback. Install or expose the migration check command in the operational image so pending-migration status can be verified directly.
