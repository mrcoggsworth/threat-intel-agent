# CTI-Hermes production ingestion failure diagnostic (19:47Z)

- **Diagnosis time:** 2026-09-15T19:48Z
- **Authoritative monitor evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`)
- **Monitor state:** `actionable_failure`
- **Event ID:** `4db73798-dff1-43d2-9d9c-79fbb29beae0`
- **Observed at:** `2026-09-15T19:46:01.345804+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `b42827aa-418f-40b7-b2f7-4769a478d90`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data` (run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`); `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`
- **Post-check evidence:** at `2026-09-15T19:49:01.559300+00`, monitor event `800ed97a-f4a4-4246-9f92-4b40de3cebbf`, correlation `b8837120-15a9-4034-b9ab-b47042af4a74`, same actionable state and run; endpoint/status remained `http://web:8000/api/v1/ops/run-status`, HTTP `200`.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch is ahead of `origin/main` by 3.
- Working tree: pre-existing modifications, deletions, and untracked files; this diagnostic added this incident record only.
- Running application image: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; all web/scheduler/monitor containers use it.
- Application version: `0.1.0`.
- Database migration revision: `0015_contradiction_lifecycle`; image reports the same Alembic head. `alembic current` could not connect using the image's default localhost database URL, while direct `pg_isready` and bounded `psql` connectivity checks succeeded against the PostgreSQL container; no migration was run.
- Last checked-in configuration change: pre-existing ThreatFox `max_response_bytes` increase from 10 MiB to 50 MiB; it is not deployed. The persisted source row remains at 10 MiB.

## Impact and cause

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), classified as `oversized_response` with detail `response exceeds 10485760 bytes`. The source has seven consecutive failures and its last successful retrieval is `2026-09-11T12:06:49.272951+00`. The latest five runs are failed with 37 successful and 1 failed source. Full-success freshness and report/publication freshness remain stale; latest report and publication timestamps are `2026-09-11T22:24:37.163555+00`.

**Cause confidence: high.** Evidence isolates the failure to the deployed ThreatFox response-size boundary. No evidence indicates web, proxy, worker/scheduler process health, PostgreSQL, disk, memory, file descriptors, migration state, backup, certificate, or persistence integrity as the primary cause.

## Operational evidence

- Web, scheduler, monitor, and PostgreSQL containers are running and healthy; each relevant application container has restart count 0 and exit code 0. Monitor heartbeat/evidence is fresh through `2026-09-15T19:47Z`; monitor logs repeatedly report stale successful run/latest failed attempt.
- Scheduler logs show source-collection failures at `2026-09-12T12:56:06Z`, `2026-09-13T02:00:06Z`, and `2026-09-15T02:00:54Z`; no crash-loop evidence was observed. Web liveness/readiness and run-status probes inside the web container return HTTP 200.
- PostgreSQL 16 accepted connections (`pg_isready`); bounded read-only queries returned the expected 38 source runs, 37 completed and one failed in the latest run, 2 completed and 26 failed ingestion runs overall, and no persistence constraint error. There are 16 database connections, with one active Hermes query and seven idle Hermes connections.
- Host capacity is healthy: root filesystem 43% used with 278G available; 49G memory available; swap use negligible; open-file limit 4096.
- Latest encrypted backup: `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes; metadata SHA-256 is recorded as `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore/checksum verification was not attempted.
- Caddy is running and the certificate is mounted under `/data/caddy/certificates/local/hermes.cti.scogin.dev`; certificate parsing was unavailable in the minimal Caddy image. Prior certificate evidence remains separate from this ingestion failure. No separate proxy container exists.
- `docker compose config` could not be interpolated from the cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is a maintenance-job configuration gap, not evidence of a running service outage.

## Recovery gate and actions

The shared recovery gate was evaluated before any recovery action with the 1,800-second cooldown and `/runtime` lock. It returned `allowed=false`, reason `recovery cooldown is active`, for gate event `aa15892e-18aa-4916-a68b-e5ca8fafbc91`, correlation `3024eb89-dad7-401e-931a-d72ee1ca3773`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. The suppression was recorded in `/runtime/recovery-events.jsonl`; read-back verified `/runtime/recovery.lock` is absent. No retry, restart, deployment, migration, credential change, collection, or destructive recovery was performed.

## Service, data integrity, rollback, and prevention

- **Impact:** one public source is stale; collection is partial; full-success and report/publication freshness are stale. Web liveness/readiness and database health remain available.
- **Data integrity:** preserved. Successful-source results, the failed source record, partial-ingestion documents, failed-run evidence, backups, migration history, and public CTI conclusions remain unchanged.
- **Rollback:** not applicable; no application or production-data mutation occurred.
- **Prevention:** under explicit maintenance/deployment authorization, validate bounded or paginated ThreatFox retrieval, retain mocked oversized-response regression coverage, reconcile persisted source configuration with checked-in `config/sources.json`, and deploy only with `./scripts/update-app.sh`. Export `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` in maintenance cron while retaining the container fallback. Separately verify encrypted-backup restoreability and certificate/edge state with host tooling.
