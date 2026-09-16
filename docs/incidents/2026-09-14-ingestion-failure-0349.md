# Production ingestion incident: gated diagnostic suppression (03:49Z)

- **Recorded:** 2026-09-14T03:49:50Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`
- **Application/image:** `0.1.0`, `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `ee1aa973-2d32-45ed-a8bd-1110beb037cc`
- **Observed at:** `2026-09-14T03:49:08.285763+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `7092b25f-6f17-46ed-8619-3b7fd0fa5b52`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`

## Impact and diagnosis

The latest scheduled collection is failed but partially usable: 37 of 38 sources succeeded and 1,564 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z`. Public CTI remains served from persisted successful-source and partial-run data, but complete source coverage and full-success freshness are degraded. Reports and publications are also stale; the latest observed timestamps are `2026-09-11T22:24:37Z`.

The failed source is `threatfox-recent-indicators-abuse-ch`: `status=failed`, `cache_state=miss`, `item_count=0`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. Its persisted source configuration is enabled with `max_response_bytes=10485760`; its last successful retrieval was `2026-09-11T12:06:49.272951Z`, last failure `2026-09-14T02:00:06.395880Z`, and consecutive failure count `5`. Cause confidence is **high**: a deterministic ThreatFox/Abuse.ch response-size boundary mismatch, not a web, proxy, worker, scheduler, database, disk, memory, certificate, backup, migration, publication, or credential outage.

## Evidence

- Monitor evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; it contained both required signals: `full_success_freshness=stale_data` and `latest_ingestion_attempt=actionable_failure` with detail `1 source(s) failed`.
- Web and readiness probes returned HTTP 200 internally; external HTTPS `/health/ready` returned HTTP 200. Web, scheduler, monitor, PostgreSQL, and backup containers were running and healthy with restart count 0. The worker is a one-shot container exited 0 and is not in a restart loop.
- Scheduler heartbeat was current at `2026-09-14T03:48:31Z`. PostgreSQL accepted connections as `hermes` to database `hermes`; Alembic revision is `0015_contradiction_lifecycle`. No pending or failed migration evidence was found.
- Persisted counts: 31,678 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships.
- Host root filesystem is 43% used with 280 GiB available; memory available was 52 GiB; shell open-file limit was 4096. No OOM or restart evidence was observed.
- Backup state is present and readable by metadata only: `/backups/latest.metadata` was updated `2026-09-13T12:55:20Z`; newest backup artifact is `hermes-20260913T125518Z.dump.enc`. Backup contents and secret metadata were not exposed.
- Caddy logs show successful local certificate renewal for `hermes.cti.scogin.dev`; no expiry failure is indicated. The local CA certificate is valid through `2026-09-14T11:39:23Z`.
- `docker compose ... ps` could not be run because this shell lacks required deployment variables `HERMES_SECRET_DIR` and `HERMES_IMAGE`; direct `docker ps`/`inspect` evidence was used instead. No deployment or configuration mutation was performed.

## Recovery gate and action

The recovery gate was evaluated with the configured 30-minute cooldown and lock. It acquired attempt event `50189186-cd79-4ec6-83fe-40ab1f9aab9f` at `2026-09-14T03:46:08.982711Z`; the current evidence advanced to event `ee1aa973-2d32-45ed-a8bd-1110beb037cc` before completion. The gate audit was completed as `outcome=suppressed` at `2026-09-14T03:49:50.543274Z`, and the lock was verified absent.

No ingestion retry, service restart, deployment, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed. Diagnosis was authorized, but recovery was not explicitly authorized; retrying the unchanged oversized request would be unlikely to restore service and could add avoidable provider load.

## State, rollback, and prevention

- **Service state:** internally healthy and serving; ingestion and publication freshness degraded.
- **Data integrity:** successful source evidence, the failed source-run record, and partial-run results remain persisted; no destructive action occurred.
- **Rollback:** not applicable; no application, configuration, or deployment change was made.
- **Prevention:** bound or paginate the ThreatFox request (or use a provider-supported filtered endpoint), retain the oversized-response classification, add/keep an offline oversized-response regression fixture, and deploy only through `./scripts/update-app.sh` after review. Reconcile the missing `HERMES_SECRET_DIR`/`HERMES_IMAGE` operator environment before compose-based maintenance. Continue separate follow-up for external Caddy trust/routing and operational query schema drift.
