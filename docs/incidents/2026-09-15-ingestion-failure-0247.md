# Production ingestion incident: ThreatFox bounded-response failure (02:47Z)

## Classification

- **Recorded:** 2026-09-15T02:47Z
- **Impact:** ingestion remains partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. Successful source data remains usable, but the latest run is not full-success; downstream analysis/publication has not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container-default evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- `state=actionable_failure`
- `event_id=b9c3ad78-909f-46cc-9916-1c2ad6bc064f`
- `observed_at=2026-09-15T02:46:48.011203+00:00`
- `correlation_id=c0de4e4d-a535-426e-963e-83a226f3b8f2`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The recovery gate was evaluated in the monitor container with its 1,800-second cooldown and shared lock. It returned `allowed=false`, reason `recovery cooldown is active`, for event `b9c3ad78-909f-46cc-9916-1c2ad6bc064f`. Read-back verified `/runtime/recovery.lock` is absent. No recovery action was attempted.

## Evidence collected

- **Release/deployment:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; running image tag `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; application version `0.1.0`; application containers started 2026-09-12T12:55:15Z-12:55:21Z with restart count 0. The checked-out working tree has substantial pre-existing changes; no deployment/config update was run.
- **Runs/source:** latest run started `2026-09-15T02:00:00.049118Z` and completed `2026-09-15T02:00:54.439155Z`; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` had no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Last full-success run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` completed 2026-09-11T12:06:50Z with 38/38 sources and 23,841 new documents.
- **Database/migrations:** `pg_isready` accepted; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence observed. The authoritative schema is singular (`ingestion_run`, `source_run`).
- **Services:** monitor, web, scheduler, PostgreSQL, and backup are running and healthy with zero restarts. Worker is exited code 0 by design (`restart: no`). Scheduler heartbeat was `2026-09-15T02:47:40Z`. Web liveness/readiness were confirmed by application logs as HTTP 200; direct ops paths on the web container returned 404 because those routes are served on the private routed surface, not the loopback route used for this check.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total with 52GiB available; shell FD limit 4096. No resource exhaustion indication.
- **Downstream:** report 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. All except relationships have latest timestamps 2026-09-11T22:24:37Z; relationships latest 2026-09-01T08:03:29Z.
- **Backup:** latest metadata identifies encrypted artifact `hermes-20260914T125520Z.dump.enc`, completed 2026-09-14T12:55:23Z, 22,608,400 bytes, with recorded SHA-256. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no proxy or certificate failure observed.
- **Logs/events:** monitor repeatedly reports stale full-success and failed latest attempt; scheduler has no useful application output. Docker event history showed no service restart. Web logs show health/ops HTTP 200 activity and unrelated internet probing requests receiving 404 responses.
- **Configuration:** checked-out `config/sources.json` includes `max_response_bytes=52428800` for ThreatFox, but the running image/database run configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`, and the change is not deployed.

## Diagnosis and follow-up

The failure is source/provider-specific: the running implementation rejects a ThreatFox response larger than 10 MiB. The checked-out but undeployed configuration increases the bound to 50 MiB. Web, proxy, worker, scheduler, database, disk, certificate, and backup services are not indicated as causes.

Under explicit maintenance/deployment authorization, review the 50 MiB limit for memory/decompression implications, run focused regression tests, and deploy only with `./scripts/update-app.sh`. Then verify the failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Export `HERMES_MONITOR_EVIDENCE_FILE` and provide protected Compose environment to maintenance jobs; use singular schema names in operational diagnostics.

**Rollback:** not applicable; no application or data mutation was performed. Recovery gate suppression and lock read-back were verified.
