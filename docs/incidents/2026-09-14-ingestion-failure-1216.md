# Production ingestion incident: ThreatFox oversized response, recovery cooldown suppression (12:16Z)

- **Recorded:** `2026-09-14T12:16:26-05:00` (`2026-09-14T12:16:26Z`)
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree had pre-existing modifications, deletions, and untracked files; no application, deployment, database, or publication files were changed by this job.
- **Application/image:** `0.1.0`; running application image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, Compose image label `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`. Web, scheduler, and monitor started on `2026-09-12T12:55:15Z`–`12:55:21Z`; restart count was `0` for all inspected CTI services.
- **Migration/database:** PostgreSQL `16.14`, Alembic revision `0015_contradiction_lifecycle`; PostgreSQL accepted connections and readiness was healthy. No migration failure or pending-migration evidence was observed. A prior diagnostic log entry used nonexistent plural table names; it did not affect the database.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; per the Compose configuration, authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `260780e4-db6a-45b0-b327-75394ae017f3`
- **Observed at:** `2026-09-14T12:15:45.649470+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `de8bc167-bc26-47ac-b91d-74ad1a40f6e8`
- **Run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Signals:** `full_success_freshness=stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; `latest_ingestion_attempt=actionable_failure` with `1 source(s) failed`.
- **Evidence freshness/read-back:** monitor evidence was refreshed at `12:15Z`; scheduler heartbeat was updated at `12:16:04Z`.

## Diagnosis and impact

The latest ingestion run started `2026-09-14T02:00:00.095941Z` and completed `2026-09-14T02:00:06.398193Z` with status `failed` but usable partial output: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source was `threatfox-recent-indicators-abuse-ch`; its source run had no HTTP status, `item_count=0`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and error `response exceeds 10485760 bytes`. The source has five consecutive failures; its last successful retrieval was `2026-09-11T12:06:49.272951Z`.

**Cause confidence: high.** This is a deterministic provider response-size boundary failure combined with configuration/deployment drift. The checked-out `config/sources.json` has a pre-existing change adding `max_response_bytes: 52428800` for ThreatFox, while persisted/running source configuration remains version `2` with `10485760` bytes. The running image was not updated. This is not consistent with a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, or credential outage.

**Impact:** complete source coverage and full-success freshness are degraded. Partial successful-source data remains available. Persisted state includes 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334Z`), 186 reports, 201 report versions, and 201 publications (latest publication `2026-09-11T22:24:37.183379Z`). No corruption, data loss, or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers were healthy; no restart loop or OOM event was observed. Scheduler logs were empty in the inspected window; monitor logs repeatedly reported the same stale-success/latest-failed condition.
- Liveness/readiness checks were healthy (`/health/live` and `/health/ready`); local ops URLs queried from the monitor container returned 404 for the three sampled ops paths despite the monitor's configured run-status endpoint reporting HTTP 200. This topology/route discrepancy is follow-up work, not the ingestion cause.
- Compose validation could not run from this cron shell because required protected variables `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported. The live containers reference `/opt/cti-hermes/env/production.env`.
- Root filesystem was 43% used with 279 GiB available; host memory available was approximately 51 GiB; host open-file limit was `4096`. No resource exhaustion was observed.
- Latest encrypted backup metadata identified `/backups/hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes, with a recorded SHA-256. Backup state was healthy, though freshness requires routine follow-up.
- Caddy was running as container `caddy` (host `systemctl caddy` is inactive); recent logs show successful local certificate renewal for `hermes.cti.scogin.dev`. Certificate/proxy state is not the ingestion cause.
- Git emitted a pre-existing non-monotonic auxiliary pack-index warning. No reset or repository repair was performed.

## Recovery gate and actions

The recovery gate was evaluated only after reading the actionable evidence, using the configured 1,800-second cooldown and shared lock.

- **Gate decision:** `allowed=false`, reason `recovery cooldown is active`.
- **Recorded event:** suppressed event `260780e4-db6a-45b0-b327-75394ae017f3`, recorded `2026-09-14T12:16:11.808037+00`.
- **Lock read-back:** absent.
- **No recovery attempt:** no ingestion retry, service restart, migration, deployment, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was authorized or performed. Prior attempted/completed gate events remain in `/runtime/recovery-events.jsonl`; this run was suppressed by cooldown.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved; the failed ThreatFox source-run record and usable partial-run output remain auditable.
- **Rollback:** not applicable; no application or data mutation occurred. Only the recovery-gate suppression audit and this incident record were written.
- **Smallest reversible follow-up:** validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; and deploy only through `./scripts/update-app.sh` when explicitly authorized. Verify the next run's failed-source status, bounded-response behavior, monitor evidence, and publication/data integrity.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; add a deployment check comparing persisted source configuration to checked-in configuration; verify backup metadata freshness; and investigate the internal-vs-monitor ops-route mismatch and auxiliary Git pack-index warning separately.
