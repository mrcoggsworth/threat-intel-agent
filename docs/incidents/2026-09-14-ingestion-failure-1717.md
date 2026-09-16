# Production ingestion incident: ThreatFox bounded-response failure (17:17Z)

- **Observed:** 2026-09-14T17:17:07.165861+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `a458a5af-b562-4778-be31-bef56b5666c7`
- **Monitor correlation ID:** `587f578e-3e90-444e-b066-9583e13d3cef`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Latest failed run:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, monitor state `stale_data`
- **Checked:** 2026-09-14T17:18:13Z

## Impact

The latest scheduled ingestion is a usable partial result, not a full success: 38 sources, 37 successful, 1 failed, and 1,564 new documents persisted. Full-success freshness remains stale since the last full-success run on 2026-09-11T12:06:50Z. The failed source is `threatfox-recent-indicators-abuse-ch`; other source results and the persisted partial run remain available. Reports/publications were not mutated during this diagnosis and remain at 2026-09-11T22:24:37Z.

## Diagnosis and confidence

**Cause confidence: high.** PostgreSQL records the sole failed source as `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The persisted source limit is 10 MiB, five consecutive failures are recorded, and the last successful retrieval was 2026-09-11T12:06:49Z. Checked-in `config/sources.json` contains a pre-existing 50 MiB ThreatFox limit, confirming configuration/deployment drift; the running image predates that uncommitted change.

Evidence does not indicate a web, proxy, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication outage as the primary cause. Web liveness/readiness returned 200, PostgreSQL accepted connections, all CTI containers were healthy with zero restarts, and scheduler logs showed no error/traceback in the inspection window.

## Operational evidence

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76c`; working tree had pre-existing unrelated changes and deletions; no reset or cleanup performed.
- Running application image: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:55:03Z; no deployment performed.
- Database migration revision: `0015_contradiction_lifecycle` (direct `alembic_version` query). `alembic current` from the web container could not connect because its command environment resolved PostgreSQL to localhost; direct PostgreSQL connectivity was healthy. Pending migration status is not proven by that command and requires the normal deployment environment.
- CTI services (web, scheduler, monitor, postgres, backup): healthy, up approximately two days, restart count 0. Caddy was running without a container healthcheck.
- Resource state: root filesystem 43% used with 279G available; 62GiB RAM host with approximately 51GiB available; CTI container file-descriptor counts were web 18, scheduler 7, monitor 3, postgres 10.
- Backup: `/backups/latest.metadata` exists and records completed backup `2026-09-14T12:55:23Z`, 22,608,400 bytes, with a recorded SHA-256; backup container healthy.
- Certificate: Caddy certificate artifacts for `hermes.cti.scogin.dev` and `matrix.scogin.dev` are present in the configured local certificate store. Certificate validity dates were not readable from those artifacts during this check; no certificate failure was observed in the CTI health checks.
- Compose validation was not run because the cron environment lacks the protected `HERMES_SECRET_DIR` and required immutable `HERMES_IMAGE` variables. No secrets were printed or changed.

## Recovery gate and actions

The recovery gate was acquired after the cooldown expired:

- Gate event ID `41840914-5062-4b7b-aabb-d81e44321940`
- Gate correlation ID `e833f624-a987-41bb-ae4b-337a16e999eb`
- Gate run ID `3848465e-e2a0-572a-b522-4c768d790284`
- Gate recorded `attempted`, then `completed` with outcome `suppressed` after diagnosis showed a deterministic source-level boundary failure.

No ingestion retry, service restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Retrying the unchanged oversized request would not be a safe or effective recovery and could add provider load. The gate audit was read back from `/runtime/recovery-events.jsonl`.

## Data-integrity and rollback state

Failed ThreatFox evidence, successful-source evidence, and usable partial-run records remain persisted and auditable. No destructive recovery occurred, so no rollback is required. The active incident remains open pending a bounded ThreatFox retrieval remediation.

## Prevention / follow-up

1. Validate provider-supported filtering/pagination or an alternate ThreatFox endpoint against an offline fixture while retaining the 10 MiB transport safety boundary.
2. Add or retain an oversized-response regression test and preserve partial-run visibility.
3. Reconcile the checked-in 50 MiB source configuration change through review and `./scripts/update-app.sh` only under explicit deployment/recovery authorization; verify the next run, monitor evidence, and publication/data integrity afterward.
4. Export `HERMES_MONITOR_EVIDENCE_FILE` and the protected Compose variables in the operator cron environment while retaining the container fallback.
5. Run migration status checks from the normal deployment environment and separately verify Caddy certificate validity dates.
