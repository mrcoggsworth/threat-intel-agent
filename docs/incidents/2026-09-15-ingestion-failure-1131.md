# CTI-Hermes production ingestion failure diagnostic (11:31Z)

- **Diagnosis time:** 2026-09-15T11:31:52Z
- **Monitor evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the configured container-mounted fallback was used.
- **Monitor state:** `actionable_failure`
- **Event ID:** `1fc1d9f1-54b7-49dd-ab95-42da0d3d67b8`
- **Observed at:** 2026-09-15T11:30:26.072888+00:00
- **Correlation ID:** `e4d707bc-10bd-4346-8c9a-231d88ac7ccd`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Latest failed run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (monitor signal `stale_data`)
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing changes are present; no source or deployment files were changed by this diagnosis. The incident record is the only intentional new artifact.
- **Running application:** version `0.1.0`, image tag `cti-hermes:local`; web/monitor/scheduler/worker containers started 2026-09-12T12:55Z, PostgreSQL 2026-09-05T16:36Z. Last known deployment boundary is the running local image; the checked-out source/config changes are not deployed.

## Impact and data state

The latest scheduled collection is persisted as `failed` but usable: 38 sources attempted, 37 succeeded, 1 failed, and 13,108 new documents were persisted. The ThreatFox/Abuse.ch source is not fresh. Database state contains 2 completed and 26 failed ingestion runs; partial successful-source data and the failed-source record remain preserved. Current projections are 33,797 source documents (latest retrieval `2026-09-15T02:00:54.267448Z`), 186 reports, 201 report versions, and 201 published publications. Report/version/publication freshness remains `2026-09-11T22:24:37.163555Z`. No evidence of data loss or publication rollback was found.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`.
- Source run: `status=failed`, `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, HTTP status unavailable.
- Persisted source configuration: `max_response_bytes=10485760`, configuration version 2, 7 consecutive failures, last successful retrieval `2026-09-11T12:06:49.272951Z`.
- Cause confidence: **high**. The failure is at the ThreatFox provider/source response-size boundary and is not a web, proxy, scheduler, PostgreSQL, disk, memory, migration, backup, or certificate-renewal failure.
- Web liveness and readiness both returned HTTP 200; readiness checks reported configuration and database `ok`.
- Monitor and scheduler containers are running healthy with restart count 0. Monitor logs repeatedly report stale full-success data and failed latest ingestion; no scheduler traceback or restart loop was observed.
- Worker is exited with exit code 0 and no restart; its configured health command is a zero-exit one-shot check. Runtime-init is likewise an exited one-shot container. These states are recorded but do not explain the persisted ingestion failure.
- PostgreSQL is accepting connections (`pg_isready`); database size was not re-measured in this run, and the current Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration was observed from the available revision evidence. `docker compose config --quiet` could not validate because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` values; no secrets were printed.
- Host capacity: root filesystem 43% used with 278G available, 51G memory available, swap use approximately 1.5 MiB, and host open-file limit 4096. No container is OOM-killed.
- Latest backup artifact observed: `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) with metadata present; backup container healthy. No restore or checksum validation was attempted.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no renewal error was observed. Client-disconnect warnings were unrelated.
- The checked-out but undeployed `config/sources.json` already contains a pre-existing ThreatFox `max_response_bytes=52428800` change; it was not deployed or modified by this diagnosis.

## Recovery gate and actions

The shared recovery gate was evaluated after reading the actionable evidence with cooldown 1,800 seconds and shared `/runtime` lock state:

- **Gate decision:** `allowed=false`
- **Reason:** `recovery cooldown is active`
- **Suppressed gate event:** `8ddbfea6-bced-4307-b61b-b9e9b34d7849`
- **Gate correlation ID:** `5122f92e-b132-412e-a527-939e7d1e23f0`
- **Gate run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Recorded at:** `2026-09-15T11:31:52.008411+00:00`
- **Lock read-back:** `/runtime/recovery.lock` absent.

No ingestion retry, restart, deployment, migration, credential change, or destructive recovery was performed. The suppressed event was recorded by the gate and read back from its audit log.

## Operational status, rollback, and prevention

- **Service:** web/readiness/database healthy; scheduler and monitor healthy; collection degraded for one source; full-success, analyst, and publication freshness stale.
- **Data integrity:** preserved. Failed and partial run evidence remains recorded; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no production application or data mutation occurred.
- **Smallest reversible follow-up after explicit maintenance authorization:** validate a bounded/paginated ThreatFox request or the existing 50 MiB response-limit change against an offline fixture, retain `oversized_response` classification, add regression coverage, and deploy only with `./scripts/update-app.sh`. Verify the next run, source status, full-success/usable projections, monitor evidence, and publication freshness.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` plus protected Compose variables in the recovery cron environment while retaining the container fallback; add a persisted-versus-checked-in source configuration deployment check; investigate the internal-versus-host `/api/v1/ops/run-status` route mismatch; separately perform encrypted-backup restore verification.
