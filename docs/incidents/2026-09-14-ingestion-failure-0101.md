# Production ingestion incident: recovery cooldown suppression (01:01Z)

- **Recorded:** 2026-09-14T01:01:18Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `da01c697-677f-4ed3-8353-aeeba03ae126`
- **Observed at:** `2026-09-14T01:00:56.480928+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `52f986e9-5e77-4b2e-952d-fcb835b789da`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate:** suppressed because the 30-minute recovery cooldown is active; gate event `da01c697-677f-4ed3-8353-aeeba03ae126`. Lock verified absent.

## Impact and cause

The latest ingestion attempt is failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z`; complete source coverage is stale. Public CTI remains available from the partial projection, but the failed source has no new data from this run.

The failed source is `threatfox-recent-indicators-abuse-ch`: `failed`, 0 items, 0 retries, no HTTP status, classification `oversized_response`, detail `response exceeds 10485760 bytes`. The same source failure is present in the preceding failed run, indicating a deterministic provider/source response-size boundary rather than a transient service outage.

**Cause confidence: high.** Evidence does not indicate a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- **Release:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; broad pre-existing working-tree changes were observed and not modified.
- **Application:** version `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T07:54:53-05:00.
- **Containers:** web, scheduler, monitor, PostgreSQL, and backup are running healthy; restart count 0 and OOM false. Docker event inspection found no non-health-check restart/start/die evidence in the window. Scheduler heartbeat was fresh at 2026-09-14T01:03:00Z.
- **Health/readiness:** web `/health/live` 200 `{"status":"ok"}`; `/health/ready` 200 with configuration and database `ok`; `/version` 200 with `0.1.0`. Monitor evidence and web logs show repeated successful run-status, liveness, and readiness checks.
- **Database:** `pg_isready` accepts connections. Alembic revision is `0015_contradiction_lifecycle`. No migration CLI is installed in the web image, so pending/failed migration status was not independently enumerated; the recorded revision and readiness check show no observed migration blockage.
- **Persistence:** 25 ingestion runs; latest failed run has 38 total, 37 successful, 1 failed, and 5,943 new documents. Bounded table counts: 31,107 source documents; 186 reports; 201 report versions; 201 publications; 378 detections; 201 hunts; 201 remediations; 11 relationships.
- **Capacity:** root filesystem 43% used with 280G available; approximately 52 GiB memory available; open-file limit 4096. No resource pressure observed.
- **Backups:** backup service healthy. Latest encrypted backup is `hermes-20260913T125518Z.dump.enc` with mode 600 and companion metadata/latest pointer; no backup mutation or deletion occurred.
- **Certificate:** local certificate for `hermes.cti.scogin.dev` renewed successfully at 2026-09-13T23:39:23Z; observed `notAfter=Sep 14 11:39:23 2026 GMT`.
- **Last deployment/config boundary:** containers started 2026-09-12T12:55:15Z–12:55:21Z. Compose labels reference `/opt/cti-hermes/env/production.env`; no deployment or service restart was performed during this diagnosis. `docker compose ps` could not be used because this shell lacks the protected `HERMES_SECRET_DIR` and required `HERMES_IMAGE` variables; direct Docker inspection was used instead.

## Actions and recovery state

1. Read the authoritative machine-readable evidence from `/runtime/monitor-evidence.json` inside the monitor container and recorded the required event, observation, endpoint/status, correlation, and run identifiers.
2. Evaluated the recovery gate. It recorded a `suppressed` event at 2026-09-14T01:01:18Z because cooldown was active; the recovery lock is absent.
3. Performed read-only health, container, log, Docker-event, capacity, certificate, backup, database, migration-revision, and bounded pipeline checks.
4. Did **not** retry ingestion, restart services, deploy with `scripts/update-app.sh`, run migrations, change source limits, alter credentials, delete data/volumes/backups, or mutate publications.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint against an offline fixture. Retain an oversized-response regression fixture and partial-run visibility. Reconcile the checked-in 50 MiB source limit with the active 10 MiB runtime boundary before any focused change. An approved future fix should run focused tests, then `./scripts/update-app.sh`, and verify full-success and usable-run projections.

No rollback is required: this diagnosis made no application or data mutation. Data integrity is preserved; service availability is healthy, with ingestion completeness degraded for one source. A future approved recovery remains gated by cooldown/lock and should use the smallest reversible source/provider fix rather than a blind rerun.
