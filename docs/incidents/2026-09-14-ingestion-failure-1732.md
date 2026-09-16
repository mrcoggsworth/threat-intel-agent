# Production ingestion incident: ThreatFox bounded-response failure (17:32Z)

- **Observed:** 2026-09-14T17:30:08.092894+00:00
- **Recorded:** 2026-09-14T17:32:08Z monitor evidence; 2026-09-14T17:31:12.624149Z gate suppression
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `62fa801e-fe60-4031-b574-a851956abec1`
- **Monitor correlation ID:** `30574f52-4e27-444e-b10a-91312d1513c3`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Latest failed run:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, monitor state `stale_data`

## Impact

The latest scheduled run is a usable partial result: 38 sources, 37 successful, 1 failed, and 1,564 new documents persisted. Full-success freshness remains stale; the latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`. The failed source is `threatfox-recent-indicators-abuse-ch`. Reports/publications were not mutated and their latest persisted timestamp remains 2026-09-11T22:24:37.163555+00:00.

## Diagnosis and confidence

**Cause confidence: high.** PostgreSQL records the sole failed source as `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The source has `max_response_bytes=10485760`, `last_successful_retrieval=2026-09-11T12:06:49.272951+00:00`, and `consecutive_failure_count=5`. The checked-in `config/sources.json` has an uncommitted 50 MiB ThreatFox limit, while the running database/image boundary remains 10 MiB: deployment/configuration drift.

Evidence does not indicate a web, proxy, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication outage as the primary cause. Web live/readiness and database connectivity were healthy. All CTI containers were healthy with zero restarts and no OOM kills. Scheduler heartbeat was fresh. Caddy renewed both managed certificates successfully in its logs; no TLS failure was observed. Caddy did return HTTP 404 for the tested public `/health/live` route, while the internal application health endpoint returned HTTP 200; this is a routing-surface observation, not evidence of the ingestion failure.

## Operational evidence

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree contains pre-existing unrelated modifications/deletions and untracked files; no reset/cleanup performed.
- Running application: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:55:03Z; `/version` reports `0.1.0`.
- Latest run: started 2026-09-14T02:00:00.095941+00, completed 2026-09-14T02:00:06.398193+00, status `failed`, application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Migration: database `alembic_version=0015_contradiction_lifecycle`; repository head is `0015_contradiction_lifecycle`. `alembic current` from the web container could not connect because its command environment resolves PostgreSQL to localhost; direct `pg_isready` and direct SQL connectivity succeeded. No pending migration is indicated by revision comparison, but the normal deployment-environment command remains unverified.
- Containers: web, scheduler, monitor, postgres, backup healthy; Caddy running without a Docker healthcheck. CTI restart counts are 0; OOM killed is false. Started times: application services 2026-09-12T12:55:15–20Z; PostgreSQL 2026-09-05T16:36:57Z.
- Scheduler heartbeat: `/runtime/scheduler.heartbeat` updated 2026-09-14T17:31:36Z. Runtime monitor evidence updated 2026-09-14T17:31:08Z. Recovery lock is absent; recovery state last attempt is 2026-09-14T17:16:09.323749+00:00.
- File descriptors: web 18, scheduler 7, monitor 3, postgres 10, backup 4; host `ulimit -n=4096`.
- Resources: root filesystem 43% used with 279G available; host memory 62 GiB total, 51 GiB available; swap 1.5 MiB used.
- Backup: `/backups/latest.metadata` records completed backup 2026-09-14T12:55:23Z, 22,608,400 bytes, SHA-256 recorded; backup container healthy. No restore was performed.
- Certificate: Caddy logs show successful renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate validity failure observed.
- Compose validation was not run because this cron environment lacks protected `HERMES_SECRET_DIR` and required `HERMES_IMAGE`; no secrets were printed or changed.

## Recovery gate and actions

The required gate was evaluated after reading the authoritative monitor evidence:

- Gate event ID: `d10b2e62-f013-4305-8d87-6cfb1181bada`
- Gate correlation ID: `374aed32-47bf-46b5-9022-1a25458b4d7f`
- Gate run ID: `3848465e-e2a0-572a-b522-4c768d790284`
- Decision: `allowed=false`; reason `recovery cooldown is active`
- Audit: suppressed event read back from `/runtime/recovery-events.jsonl`; lock verified absent.

No ingestion retry, service restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. This request authorizes diagnosis only and destructive recovery is not authorized.

## Data integrity, rollback, and prevention

Failed ThreatFox evidence, successful-source evidence, and usable partial-run records remain persisted and auditable. Data integrity risk is limited to incomplete source coverage and stale full-success freshness; no evidence of database corruption or publication mutation was found. No rollback is required because no application/data mutation occurred.

Smallest reversible follow-up after explicit recovery/deployment authorization: validate provider-supported filtering/pagination or an alternate ThreatFox endpoint against an offline fixture while retaining a bounded transport limit; preserve an oversized-response regression test; reconcile the checked-in source configuration via `./scripts/update-app.sh`; then verify the next run, source status, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the operator cron environment. Separately validate the Caddy public health route and run migration status from the normal deployment environment.
