# Production ingestion incident: ThreatFox oversized response (04:02Z)

- **Recorded:** 2026-09-14T04:02:33Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree has pre-existing unexplained changes
- **Application/image:** `0.1.0`, `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `5a874356-0489-4790-a8e2-b73f6995f8b0`
- **Observed at:** `2026-09-14T04:00:09.041897+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `6738c6b2-29b0-4f23-9045-5b667a895bc8`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`

## Impact and diagnosis

The 2026-09-14 02:00Z collection failed partially: 37 of 38 sources completed and 1,564 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z`. Persisted public CTI remains available, but complete source coverage and full-success freshness are degraded. Reports, detections, hunts, remediations, and publications have not advanced since `2026-09-11T22:24:37Z`.

The failed source is `threatfox-recent-indicators-abuse-ch`: `status=failed`, `cache_state=miss`, `item_count=0`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. Database source configuration still has `max_response_bytes=10485760`, while the dirty working tree contains an un-deployed `config/sources.json` change raising this to `52428800`. The source last succeeded at `2026-09-11T12:06:49.272951Z`, last failed at `2026-09-14T02:00:06.395880Z`, and has consecutive failure count `5`. Cause confidence is **high**: deterministic provider response-size boundary/configuration mismatch, not a web, proxy, worker, scheduler, database, disk, memory, certificate, backup, migration, publication, or credential outage.

## Evidence collected

- Authoritative evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; it contained `full_success_freshness=stale_data` and `latest_ingestion_attempt=actionable_failure` with detail `1 source(s) failed`.
- Web, readiness, and external HTTPS readiness returned HTTP 200; readiness reported configuration and database checks `ok`.
- Web, monitor, scheduler, PostgreSQL, and backup containers were running and healthy with restart count 0. The worker is a one-shot container exited 0; no restart loop was observed. Scheduler heartbeat was current at the observation time.
- PostgreSQL connectivity succeeded as database `hermes`; Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration indication was found in the migration state or recent service logs.
- Persisted counts: 31,678 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships.
- Host root filesystem is 43% used with 280 GiB available; memory available was 52 GiB; `/proc/sys/fs/file-nr` was `6400 0 9223372036854775807`. No OOM or service restart evidence was observed.
- Backup metadata is present: `/backups/latest.metadata` references `hermes-20260913T125518Z.dump.enc`, completed at `2026-09-13T12:55:20Z`, with recorded SHA-256 metadata. Backup contents and secrets were not exposed.
- Caddy logs show successful local certificate renewal for `hermes.cti.scogin.dev`; no certificate expiry failure was observed.
- `docker compose ... ps` could not be rendered from this shell because `HERMES_SECRET_DIR` and `HERMES_IMAGE` are unset. Direct `docker ps`/`inspect` evidence was used; no deployment/configuration mutation was performed.

## Recovery gate and action

The recovery gate was evaluated against the authoritative evidence with its 30-minute cooldown and lock. It returned `allowed=false`, `reason=recovery cooldown is active`, and recorded suppressed event `59c8b801-b055-43fc-a0a6-acc34cff2676` at `2026-09-14T04:01:19.176525+00Z`. The lock was verified absent.

No ingestion retry, service restart, deployment, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed. Diagnosis was authorized, but recovery was not explicitly authorized; retrying the unchanged request would likely reproduce the deterministic provider-size failure.

## State, rollback, and prevention

- **Service state:** web/proxy/database/monitor/scheduler/backup healthy and serving; ingestion and downstream publication freshness degraded.
- **Data integrity:** successful-source evidence, partial-run results, and failed source-run record remain persisted; no destructive action occurred.
- **Rollback:** not applicable; this job made no application or deployment change. The pending source limit change remains un-deployed in the pre-existing working tree.
- **Prevention:** review and deploy the bounded/paginated ThreatFox request or the explicit 50 MiB source limit through `./scripts/update-app.sh`; retain the oversized-response classification and regression fixture. Reconcile missing `HERMES_SECRET_DIR`/`HERMES_IMAGE` before compose-based maintenance. Continue separate follow-up for operational query schema drift and certificate trust/routing.
