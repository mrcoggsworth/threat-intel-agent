# Production ingestion incident: ThreatFox oversized response, diagnosis-only recovery suppression (10:17Z)

- **Recorded:** `2026-09-14T10:17:32Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present. No application source, deployment, database, or publication files were changed by this diagnosis; this incident record is the only new artifact.
- **Application/image:** version `0.1.0`; running image tag `cti-hermes:local`; web/monitor/scheduler started `2026-09-12T12:55:15Z`–`12:55:21Z`.
- **Migration:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence was found.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`. Authoritative evidence was read from the configured Compose fallback `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `ec731e6f-047a-4ec0-8b26-b6ebdd3cab11`
- **Observed at:** `2026-09-14T10:15:36.948325+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `db747108-e007-4a3d-bee6-e01679f3f7bb`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Failure signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).

## Diagnosis and impact

The latest scheduled run began at `2026-09-14T02:00:00.095941+00Z` and completed at `2026-09-14T02:00:06.398193+00Z` as failed but usable: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`, with `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.

The running database source configuration is `max_response_bytes=10485760` (configuration version 2), while checked-in `config/sources.json` contains a 50 MiB value for the relevant source configuration. This is deployment/configuration drift combined with a deterministic provider response-size boundary failure, not an application availability failure.

**Cause confidence: high.** Evidence does not support web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage as the primary cause.

**Impact:** complete source coverage and full-success freshness are degraded. Successful-source and partial-run data remain available. Current persisted counts are 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334+00Z`), 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediation records, and 11 relationships. No corruption, data loss, or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy with restart count `0`; PostgreSQL is accepting connections to database `hermes`. The worker is an intentional one-shot container, exited `0`, and is not in a restart loop.
- Web liveness/readiness checks were returning HTTP `200` in the sampled monitor/web logs. Scheduler heartbeat was current at `2026-09-14T10:17:03Z`; scheduler logs showed no exception in the sampled window. Monitor logs repeatedly reported only the stale/full-success and latest-attempt failure signals.
- Docker events during the observation window showed diagnostic `exec_*` events only; no service restart or OOM event was observed.
- Root filesystem is 43% used with 279 GiB available; host memory available is approximately 51 GiB; host open-file limit is `4096`. No resource exhaustion is indicated.
- Backup volume contains encrypted artifacts through `hermes-20260913T125518Z.dump.enc`; `/backups/latest.metadata` is mode `600`, size 198 bytes, mtime `2026-09-13T12:55:20Z`. Backup freshness requires follow-up; no backup mutation occurred.
- Presented certificate for `hermes.cti.scogin.dev` is issued by `Caddy Local Authority - ECC Intermediate`, valid `2026-09-14T07:39:23Z` through `2026-09-14T19:39:23Z`. Certificate state is not the ingestion cause.
- Git emitted a pre-existing non-monotonic auxiliary pack-index warning; no repository repair or reset was performed.

## Recovery gate and actions

The recovery gate was evaluated after reading actionable evidence, using the configured 1,800-second cooldown and shared lock.

- **Gate:** allowed and recorded `attempted` for event `ec731e6f-047a-4ec0-8b26-b6ebdd3cab11` at `2026-09-14T10:16:17.962722+00:00`.
- **Decision:** completed with `outcome=suppressed`; this request authorizes diagnosis only, not recovery.
- **Lock read-back:** absent after completion.
- **No recovery mutation:** no ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. Successful-source results, partial-run documents, failed ThreatFox evidence, reports, and publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made. Only recovery gate bookkeeping and this incident record were written.
- **Smallest reversible follow-up:** validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; deploy only through `./scripts/update-app.sh` when explicitly authorized; then verify source status, response-size handling, monitor evidence, and publication/data integrity.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; add a deployment check comparing persisted source configuration to checked-in configuration; verify backup metadata freshness/publication; investigate the inactive host proxy and internal-vs-monitor route topology separately.
