# Production ingestion incident: ThreatFox bounded-response failure (17:47Z)

- **Observed:** 2026-09-14T17:46:09.229768+00:00
- **Recorded:** 2026-09-14T17:47:08Z recovery-gate completion
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `66d97107-e06a-42cb-b3c7-5cd98de2cbe4`
- **Monitor correlation ID:** `abb1cb84-9eed-4ffb-9c6e-e784a4d2a640`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Latest failed run:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`

## Impact

The latest scheduled run is a usable partial result: 38 sources, 37 successful, 1 failed, and 1,564 new documents persisted. Full-success freshness remains stale; the latest full-success run completed at 2026-09-11T12:06:50.050468+00. The failed source is `threatfox-recent-indicators-abuse-ch`. Reports and publications were not mutated; both latest persisted timestamps remain 2026-09-11T22:24:37.163555+00.

## Diagnosis and confidence

**Cause confidence: high.** PostgreSQL records the sole failed source as `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The running source boundary is `max_response_bytes=10485760`, while the checked-in but uncommitted `config/sources.json` raises the ThreatFox limit to 52428800. This is deployment/configuration drift; the running image/database boundary has not received the checked-in change.

No evidence indicates a web, proxy, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication outage as the primary cause. Web liveness/readiness returned HTTP 200; readiness reported database `ok`; PostgreSQL accepted connections; scheduler heartbeat was fresh; CTI containers were healthy with zero restarts and no OOM kills. The worker container is exited/unhealthy but is not used by the scheduled ingestion path evidenced here and requires separate operator review. Caddy has no Docker healthcheck; no new proxy evidence was collected in this run.

## Operational evidence

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree has pre-existing modifications/deletions and untracked files. No reset or cleanup performed.
- Running application: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; `/version` reports `0.1.0`.
- Latest run: scheduled 2026-09-14T02:00:00Z, started 02:00:00.095941Z, completed 02:00:06.398193Z, status `failed`, application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Migration/database: PostgreSQL 16.14; `alembic_version=0015_contradiction_lifecycle`; no pending revision was established from this read-only check. Database connectivity and readiness are healthy.
- Containers: web, scheduler, monitor, postgres, and backup running/healthy; restart count 0 and OOM false. Caddy running without a Docker healthcheck. Worker is exited/unhealthy, restart count 0.
- Scheduler heartbeat endpoint returned `2026-09-14T17:47:06Z`; runtime heartbeat was fresh. Monitor evidence was refreshed at 17:47:09Z.
- Resources: root filesystem 43% used with 279G available; host memory 62 GiB total / 54 GiB available; swap 1.5 MiB used; host `ulimit -n=4096`.
- Backup metadata exists and was modified 2026-09-14T12:55:23Z; backup container is healthy. Metadata contents were not exposed because the monitor container lacks permission to read it. No restore was performed.
- Certificate state: not revalidated in this pass; prior incident evidence recorded successful Caddy renewals and no TLS expiry failure.

## Recovery gate and actions

The authoritative evidence was read from `/runtime/monitor-evidence.json` in the running monitor container before any model work. It contained the state, event ID, observed time, endpoint/status, correlation ID, and run ID above.

- Gate decision: `allowed=true` after the 30-minute cooldown elapsed.
- Gate event: `66d97107-e06a-42cb-b3c7-5cd98de2cbe4`.
- Gate audit: attempted at 2026-09-14T17:46:54.322482+00, then completed with `outcome=suppressed` at 17:47:08.619710Z; lock verified absent.
- No ingestion retry, service restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed because this request authorizes diagnosis only.

## Data integrity, rollback, and prevention

Failed ThreatFox evidence, successful-source evidence, and usable partial-run records remain persisted and auditable. Current risk is incomplete ThreatFox coverage and stale full-success freshness; no database corruption or publication mutation was found. No rollback is required because no application/data mutation occurred.

After explicit recovery/deployment authorization, the smallest reversible follow-up is to validate bounded ThreatFox filtering/pagination or an alternate endpoint against an offline fixture, retain a bounded transport limit and regression test, reconcile the checked-in source configuration with `./scripts/update-app.sh`, then verify the next run, source status, monitor evidence, and publication/data integrity. Separately investigate the exited/unhealthy worker and repair the cron environment so `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables are explicitly exported.
