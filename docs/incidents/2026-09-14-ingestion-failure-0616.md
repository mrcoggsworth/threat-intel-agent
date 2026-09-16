# Production ingestion incident: actionable failure, recovery suppressed (06:16Z)

- **Recorded:** `2026-09-14T06:16:44+00:00`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing changes/deletions present; not modified by this diagnosis
- **Application/image:** `0.1.0`, `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Migration revision:** `0015_contradiction_lifecycle`; no pending/failed migration evidence observed

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`, the configured Compose mount.

- **Monitor state:** `actionable_failure`
- **Latest evidence event:** `6c54bdf1-e9db-4076-9056-a608e84c9341`
- **Observed at:** `2026-09-14T06:16:18.699976+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `b54cc4ca-1165-47a6-a253-bd3b538b2c24`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data`)
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`)

## Diagnosis and impact

The 2026-09-14 02:00Z ingestion run is failed but usable: 38 sources total, 37 successful, 1 failed, and 1,564 new documents persisted. The failed source is `threatfox-recent-indicators-abuse-ch` with `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The database source configuration still records `max_response_bytes=10485760`; the checked-in configuration has the previously identified 50 MiB limit, so the running image/configuration is not reconciled.

Public CTI remains available from persisted successful-source and partial-run data, but complete source coverage and full-success freshness are degraded. Current read-only counts are 31,678 source documents, 186 reports, and 201 publications. No evidence indicates corruption, loss, or unauthorized publication mutation. Reports/publications remain stale as documented in the preceding incident record.

**Cause confidence: high.** This is a deterministic ThreatFox provider/source response-size boundary mismatch, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, or credential outage.

## Current service and operational evidence

- Web liveness/readiness: HTTP `200` / `200`.
- Web, monitor, scheduler, backup, and PostgreSQL containers: running, healthy, restart count `0`.
- Worker: one-shot service; no restart-loop or OOM evidence observed.
- PostgreSQL: accepting connections; `current_database=hermes`, `current_user=hermes`.
- Scheduler/monitor logs: repeated `last successful run stale, latest ingestion attempt failed`; no scheduler error emitted.
- Docker events in the two-hour window: no container restart or OOM event.
- Root filesystem: 43% used, 280 GiB available; memory available approximately 52 GiB; host open-file limit 4096. No resource exhaustion indicated.
- Backup state: encrypted artifacts and metadata present; latest artifact `hermes-20260913T125518Z.dump.enc`, 22,110,800 bytes; metadata mode 600, latest metadata dated `2026-09-13T12:55:20Z`. No backup mutation occurred.
- Certificate/proxy state: Caddy logs show successful local renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate cause indicated.

## Recovery gate and actions

The recovery gate was evaluated before any recovery action with the configured 1,800-second cooldown and lock. It recorded:

- **Gate event:** `a50f49e3-41a2-41f3-a6af-829d7b76e6a2`
- **Gate result:** suppressed, reason `recovery cooldown is active`
- **Gate recorded at:** `2026-09-14T06:16:18.413018+00:00`
- **Lock read-back:** absent

No ingestion retry, service restart, deployment via `./scripts/update-app.sh`, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed. Failed ThreatFox evidence and successful partial-run evidence remain persisted. No rollback is required.

## Prevention and follow-up

Validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture. Retain an oversized-response regression fixture, reconcile the running image with `config/sources.json`, and deploy only after explicit recovery/deployment authorization using `./scripts/update-app.sh`. Verify the next run's failed-source status, response-size handling, monitor evidence, and publication/data integrity. Reconcile the missing operator `HERMES_MONITOR_EVIDENCE_FILE` export in the cron shell while retaining the container-mounted evidence fallback.
