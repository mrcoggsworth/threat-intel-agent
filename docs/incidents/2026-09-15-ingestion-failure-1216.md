# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T12:16:29.425692+00:00
- **Diagnosis time:** 2026-09-15T12:17:42.741176128Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `3b94c8c8-3446-43c2-9641-15a5efe1cc46`
- **Correlation ID:** `58cf1276-f76c-48eb-9f79-c74cd7807566`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data`)
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present. No application code, configuration, database, or stack state was changed by this diagnosis. This incident record is the only new diagnostic artifact.

## Impact

The latest scheduled collection is persisted as `failed`: 37 of 38 sources succeeded, one failed, and 13,108 new documents were persisted. ThreatFox/Abuse.ch is not fresh. The full-success projection remains stale, so collection freshness is degraded and downstream full-success/analyst/publication freshness remains stale. No evidence of data loss was found; successful partial-ingestion evidence and the failed-source record remain persisted.

## Evidence and cause

- The failed source is `threatfox-recent-indicators-abuse-ch` with `error_classification=oversized_response` and `error_detail=response exceeds 10485760 bytes`; no HTTP status was recorded.
- Direct PostgreSQL read-back confirms run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` has status `failed`, `total_sources=38`, `successful_sources=37`, `failed_sources=1`, `new_documents=13108`, and error summary `1 source(s) failed`.
- Web, scheduler, monitor, PostgreSQL, and backup containers are healthy with restart count 0 and OOM false. The worker container is exited with code 0 and was not identified as the failing stage. Web `/health/live`, `/health/ready`, and `/version` returned HTTP 200, HTTP 200, and `0.1.0`; readiness reported configuration and database `ok`.
- PostgreSQL accepted connections; version is 16.14 and Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration was observed from the available revision evidence.
- Host capacity is not limiting: root filesystem is 43% used with 279G available; 49Gi memory available; swap usage is 1.8MiB; open-file limit is 4096. Container event sampling showed health-check exec events and no application-container restart.
- Running application image is `cti-hermes:local`, Compose image label digest `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`, started 2026-09-12T12:55:15Z. Persisted application version is `0.1.0`.
- Checked-out `config/sources.json` already contains a pre-existing ThreatFox `max_response_bytes=52428800` change, but the running image/configuration hash still reflects the deployed 10MiB limit (`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`). This diagnosis did not deploy or alter it.
- Latest backup metadata is present (`latest.metadata`, 198 bytes, modified 2026-09-14T12:55:23Z); the newest encrypted dump is `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes. Backup checksum/restore was not revalidated because this request authorizes diagnosis only.
- Caddy logs show successful local certificate renewal and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate-renewal failure was observed.
- Compose validation was attempted but could not run in the cron shell because required protected environment variables `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported. This is an operational configuration gap, not evidence of a runtime outage.

**Cause confidence: high.** This is a recurring ThreatFox/Abuse.ch provider response-size failure at the bounded ingestion boundary, not a web, proxy, worker/scheduler liveness, PostgreSQL, disk, memory, migration, backup, or certificate failure.

## Recovery gate and actions

The authoritative machine-readable evidence was read before further diagnosis from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. Required identifiers and endpoint/status were recorded above.

The recovery gate was evaluated in the monitor container with the shared 1,800-second cooldown and lock. It returned:

- `allowed=false`
- reason: `recovery cooldown is active`
- gate event: `3b94c8c8-3446-43c2-9641-15a5efe1cc46`
- lock read-back: `/runtime/recovery.lock` absent
- audit read-back: suppressed event appended to `/runtime/recovery-events.jsonl` at `2026-09-15T12:16:46.863995+00Z`

This diagnosis-only request did not authorize retry, restart, deployment, migration, credential change, database mutation, or destructive recovery. None was performed.

## Service, integrity, rollback, and prevention

- **Service state:** web and database readiness healthy; scheduler heartbeat current; one source failing; full-success freshness stale; reports/publications remain stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded. No volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no application or production-data mutation was made.
- **Smallest reversible follow-up under explicit maintenance/deployment authorization:** validate bounded/paginated ThreatFox retrieval or the existing 50MiB response-limit change with mocked oversized-response coverage, then deploy only through `./scripts/update-app.sh`. Verify the next source status, full-success/usable run projections, monitor evidence, and report/publication freshness.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables to maintenance cron while retaining the container fallback; separately perform encrypted-backup restore verification and reconcile the host/internal ops-route mismatch.
