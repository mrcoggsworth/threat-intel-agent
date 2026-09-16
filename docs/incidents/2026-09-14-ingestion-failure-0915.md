# Production ingestion incident: ThreatFox oversized response, recovery suppressed (09:15Z)

- **Recorded:** `2026-09-14T09:19:33Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present before this diagnosis. No application source, deployment, database, or publication files were changed.
- **Application/image:** version `0.1.0`; running image tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; application containers started `2026-09-12T12:55Z`.
- **Migration:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence was found.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured Compose fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `4a5f8a4c-0f77-4a91-9a4b-61471a6dcc18`
- **Observed at:** `2026-09-14T09:15:32.657048+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `ab904e16-d767-4e75-bb60-0c974de032c7`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Failure signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).

## Diagnosis and impact

The latest scheduled run began at `2026-09-14T02:00:00.095941+00Z` and completed at `2026-09-14T02:00:06.398193+00Z` as failed but usable: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`, with `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.

The persisted source configuration is `max_response_bytes=10485760`; checked-in `config/sources.json` did not produce a matching running configuration in this deployed image. This is a deployment/configuration drift and deterministic provider response-size boundary failure, not an application availability failure.

**Cause confidence: high.** Evidence does not support web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage as the primary cause.

**Impact:** complete source coverage and full-success freshness are degraded. Successful-source and partial-run data remain available. The latest persisted counts are 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334+00Z`), 186 reports, 201 publications, 11 relationships, 378 detections, 201 hunts, and 201 remediation records. No corruption, data loss, or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy; restart count is `0` for running services. The reserved worker exited `0` after startup and is not in a restart loop.
- In-container liveness/readiness returned HTTP `200`: `{"status":"ok"}` and `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`.
- Scheduler heartbeat file was present and current during diagnosis. Scheduler logs had no exception in the sampled window; monitor logs repeatedly reported the same stale/full-success and latest-attempt failure.
- PostgreSQL 16.14 accepts connections; database `hermes` is `182 MB`; migration revision is `0015_contradiction_lifecycle`.
- Root filesystem and memory were not pressure conditions during diagnosis; no OOM or restart event was observed. Host open-file limit was `4096`.
- Backup volume contains encrypted artifacts through `hermes-20260913T125518Z.dump.enc` and `/backups/latest.metadata`; latest visible backup is from `2026-09-13T12:55:20Z`. Backup freshness requires follow-up, but no backup mutation occurred.
- Host `caddy` service is inactive, but the endpoint presented a Caddy Local Authority certificate valid `2026-09-14 07:39:23Z` through `2026-09-14 19:39:23Z`. The failed ingestion is internal and does not correlate with a certificate outage.
- Git reported a pre-existing non-monotonic auxiliary pack-index warning; no reset or repository repair was performed.

## Recovery gate and actions

The gate was evaluated only after reading the actionable evidence, with the configured 1,800-second cooldown and shared lock.

- **Gate:** allowed and recorded `attempted` for event `4a5f8a4c-0f77-4a91-9a4b-61471a6dcc18` at `2026-09-14T09:16:06.689616+00Z`.
- **Decision:** completed as `suppressed`; the current request authorizes diagnosis but not recovery. Gate completion was recorded without a service mutation.
- **Lock read-back:** absent after completion.
- **No recovery mutation:** no ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. Successful-source results, partial-run documents, failed ThreatFox evidence, existing reports, and publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made. Gate bookkeeping only was recorded and the recovery lock was removed after suppression.
- **Smallest reversible follow-up:** validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; deploy only through `./scripts/update-app.sh` when explicitly authorized; then verify source status, response-size handling, monitor evidence, and publication/data integrity.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; verify backup metadata freshness/publication; investigate the inactive host proxy service and internal-vs-monitor route topology separately; add a deployment check that compares the persisted source configuration hash to the checked-in configuration.
