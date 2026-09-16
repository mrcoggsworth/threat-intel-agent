# Production ingestion incident: actionable partial-run failure (00:50Z)

- **Recorded:** 2026-09-14T00:49:38Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `efac2d6f-611c-412e-83a1-372dbb578026`
- **Observed at:** `2026-09-14T00:47:55.548981+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `a1f77ffe-8b63-4da1-b170-01bc6eca05d4`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate:** acquired after cooldown; completed as `suppressed` because this request authorizes diagnosis only. Gate event: `2ad4481a-96cd-434e-b2a2-c281dfc25544`. Lock verified absent after completion.

## Impact and cause

The latest ingestion attempt remains failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z`, so complete source coverage is stale. Public CTI remains available from the partial projection; the failed source is not represented by new data from this run.

The failed source is `threatfox-recent-indicators-abuse-ch`: status `failed`, item count `0`, retry count `0`, cache `miss`, HTTP status null, classification `oversized_response`, detail `response exceeds 10485760 bytes`.

**Cause confidence: high.** This is a deterministic provider/source response-size boundary failure. Evidence does not indicate a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, publication, backup, migration, or credential outage.

## Evidence and operational state

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; broad pre-existing working-tree changes were present and were not modified by this diagnosis.
- Application: version `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Containers: monitor, web, scheduler, PostgreSQL, and backup running healthy; restart count 0, OOM false. Worker is an intentional one-shot container, exited 0, restart count 0. Proxy Caddy is running; no service restart was performed. The Docker event query was dominated by high-volume health-check `exec` events and timed out; container restart counters and service logs show no application start/die or restart-loop evidence in the observation window.
- Health/readiness: web `/health/live` 200 `{"status":"ok"}`; `/health/ready` 200 with configuration and database `ok`; `/version` 200 with `0.1.0`. The monitor's run-status check is HTTP 200. A direct unauthenticated web-container request to that path returned 404 and is not used over the monitor's authoritative result.
- Scheduler: heartbeat file was fresh at `2026-09-14 00:49:30Z`; scheduler logs showed no crash evidence.
- Database: PostgreSQL accepts connections; Alembic revision is `0015_contradiction_lifecycle`. No migration CLI is installed in the web image, so pending/failed migration status was not independently enumerated; the database revision and readiness check show no observed migration blockage.
- Bounded persistence reads: 31,107 source documents; 186 reports; 201 report versions; 201 publications; 378 detections; 201 hunts; 201 remediations; 11 relationships. Latest analyst/publication rows are from `2026-09-11T22:24:37.163555Z`; latest source documents are from `2026-09-13T02:00:07.876047Z`.
- Host capacity: root filesystem 43% used with 280G available; approximately 52GiB memory available; open-file limit 4096. No resource pressure was observed.
- Backups: backup service healthy. Latest encrypted backup is `hermes-20260913T125518Z.dump.enc`, metadata timestamp `2026-09-13T12:55:20Z`, mode 600; no backup mutation or deletion occurred.
- Certificate: Caddy logs show successful local renewal for `hermes.cti.scogin.dev` at `2026-09-13T23:39:23Z`. Current local certificate observed on port 9444 has `notAfter=Sep 14 11:39:23 2026 GMT`; certificate state is healthy but should continue to be monitored.
- Last application service start: `2026-09-12T12:55:15Z`–`12:55:21Z`; no restart or deployment/configuration change during this diagnosis.

## Actions and recovery state

1. Read the authoritative machine-readable monitor evidence from `/runtime/monitor-evidence.json` inside the monitor container and recorded all required identifiers.
2. Evaluated the recovery gate with cooldown and lock. It acquired the gate after cooldown expiry, recorded an `attempted` event, then recorded a `completed` event with outcome `suppressed` because recovery is not authorized by this diagnosis-only request. The recovery lock is absent.
3. Performed read-only health, container, log, Docker, capacity, certificate, backup, database, and bounded pipeline checks.
4. Did **not** retry ingestion, restart services, deploy with `scripts/update-app.sh`, run migrations, change source limits, alter credentials, delete data/volumes/backups, or mutate publications.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint against an offline fixture. Retain an oversized-response regression fixture and partial-run visibility. Reconcile the checked-in 50 MiB source limit with the active 10 MiB runtime boundary before any focused change. A future approved fix should run focused tests, then `./scripts/update-app.sh`, and verify full-success and usable-run projections afterward.

No rollback is required: this diagnosis made no application or data mutation. Data integrity is preserved; service availability is healthy, with ingestion completeness degraded for one source.
