# Production ingestion incident: ThreatFox oversized response, diagnosis-only recovery suppression (11:00Z)

- **Recorded:** `2026-09-14T11:02:39Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree contained pre-existing modifications, deletions, and untracked files; no application, deployment, database, or publication files were changed by this diagnosis.
- **Application/image:** version `0.1.0`; running image `cti-hermes:local`, ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web, scheduler, and monitor started `2026-09-12T12:55:15Z`–`12:55:21Z`.
- **Migration:** PostgreSQL `16.14`, Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence. A sampled PostgreSQL log contained an operator diagnostic query against the nonexistent table `ingestion_source_run`; the actual table is `source_run` and ingestion was not blocked by that query.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative evidence was read from the configured Compose fallback `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `4e8d09a1-961e-4840-aa73-526362d599ad`
- **Observed at:** `2026-09-14T11:00:40.247854+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `d12ee9b8-dadb-4d86-96f3-fe083ebf4ee3`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success signal:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Failure signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).
- **Read-back:** at `2026-09-14T11:02:40.393953+00:00`, the monitor still reported `actionable_failure` for the same run with advanced event ID `96fb5181-77ec-49b7-8c09-0b906b0c7388` and correlation ID `1103644c-bcc8-4211-bb63-cf285b9af69a`; no recovery was authorized or triggered.

## Diagnosis and impact

The latest run started `2026-09-14T02:00:00.095941Z` and completed `2026-09-14T02:00:06.398193Z` with status `failed` but usable partial output: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source was `threatfox-recent-indicators-abuse-ch`, with no HTTP status, `item_count=0`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `response exceeds 10485760 bytes`.

Persisted source state is configuration version `2`, `max_response_bytes=10485760`, last successful retrieval `2026-09-11T12:06:49.272951Z`, last failure `2026-09-14T02:00:06.395880Z`, and five consecutive failures. Checked-in `config/sources.json` has a pre-existing working-tree change raising this source limit to `52428800`; the running image/configuration has not been updated. This is high-confidence deployment/configuration drift combined with a deterministic provider response-size boundary failure, not a web, proxy, worker, scheduler, database, resource, certificate, backup, or credential outage.

**Impact:** complete source coverage and full-success freshness are degraded. Successful-source and partial-run data remain available. Persisted counts: 31,678 source documents (latest retrieval `2026-09-14T02:00:06.400617Z`), 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediation records, and 11 relationships. No corruption, data loss, or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers are healthy with restart count `0`; the reserved worker exited `0` and is not in a restart loop.
- Monitor/web logs show repeated HTTP `200` readiness/liveness and run-status requests. Scheduler heartbeat exists and was updated at `2026-09-14T11:02:34Z`.
- Compose configuration validates with the deployed environment file `/opt/cti-hermes/env/production.env`; validation from this cron shell without that environment failed because `HERMES_SECRET_DIR` and `HERMES_IMAGE` are intentionally required variables.
- Root filesystem is 43% used with 279 GiB available; host memory available is approximately 51 GiB; host open-file limit is `4096`. No OOM or resource exhaustion was observed. Docker events in the observation window showed diagnostic exec events only, with no CTI service restart or OOM event.
- Latest visible encrypted backup is `/backups/hermes-20260913T125518Z.dump.enc`; `/backups/latest.metadata` is mode `600`, 198 bytes, completed `2026-09-13T12:55:20Z`, with a recorded SHA-256. Backup freshness requires follow-up; no backup mutation occurred.
- `hermes.cti.scogin.dev` presented a certificate issued by `Caddy Local Authority - ECC Intermediate`, valid `2026-09-14T07:39:23Z` through `2026-09-14T19:39:23Z`; certificate state is not the ingestion cause. Git also reported a pre-existing non-monotonic auxiliary pack-index warning; no reset or repository repair was performed.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable evidence, with the configured 1,800-second cooldown and shared lock.

- **Gate event:** `4e8d09a1-961e-4840-aa73-526362d599ad`; `attempted` recorded at `2026-09-14T11:01:10.767611Z`.
- **Decision:** completed with `outcome=suppressed` at `2026-09-14T11:01:22.671213Z`; this request authorizes diagnosis only, not recovery.
- **Lock read-back:** absent after completion.
- **No recovery mutation:** no ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. Successful-source results, partial-run documents, failed ThreatFox evidence, reports, and publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made. Only recovery gate bookkeeping and this incident record were written.
- **Smallest reversible follow-up:** validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; deploy only through `./scripts/update-app.sh` when explicitly authorized; then verify source status, bounded-response handling, monitor evidence, and publication/data integrity.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; add a deployment check comparing persisted source configuration to checked-in configuration; verify backup freshness; and investigate the inactive host proxy and internal-vs-monitor route topology separately.
