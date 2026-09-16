# CTI-Hermes production ingestion failure — 2026-09-15 16:48Z

## Status and authorization

- **Monitor state:** `actionable_failure`; diagnosis authorized, recovery/deployment not authorized.
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.
- **Monitor event:** `cba40afa-d7fb-4f86-a30e-622981c38baf`.
- **Observed at:** `2026-09-15T16:45:48.675982+00:00`.
- **Correlation ID:** `a8bc9994-1ca0-436c-aa61-7b2bd7fa4a09`.
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`.
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`.
- **Signals:** full-success freshness `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest attempt `actionable_failure`, `1 source(s) failed`.

## Diagnosis

- The 2026-09-15 scheduled collection ran at `2026-09-15T02:00:00.049118+00Z` and ended at `02:00:54.439155+00Z` as `failed`: 38 sources, 37 successful, 1 failed, 13,108 new documents, 0 changed/unchanged documents, and error summary `1 source(s) failed`.
- The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch): `oversized_response`, `response exceeds 10485760 bytes`; no HTTP status was recorded.
- The deployed database source configuration has `max_response_bytes=10485760` and 7 consecutive failures; the checked-in `config/sources.json` has an uncommitted `max_response_bytes=52428800` change. The running image is `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`, indicating the checked-in fix is not deployed.
- **Cause confidence:** high for a source/provider bounded-response/configuration drift cause; no evidence indicates web, proxy, worker, scheduler, database, disk, memory, descriptor, certificate, or backup failure as the cause.
- ACSC also has a historical consecutive failure count of 8, but it was not the failed source in the latest run and requires separate source-level investigation.

## Runtime evidence

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree had pre-existing unrelated modifications and deletions, so no files were reverted or normalized.
- Application version persisted in the run: `0.1.0`; configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Containers: web, scheduler, and monitor up 3 days and healthy; PostgreSQL up 10 days and healthy; worker exited with code 0 and is intentionally reserved for a later analysis phase. Restart counts were 0 for inspected CTI containers.
- Web live/readiness inside the container: HTTP 200; readiness reported configuration/database `ok`. Host port 8000 is not published, so host-local probes returned connection refused. External `https://hermes.cti.scogin.dev/health/ready` returned 200; `/health/live` returned 404, a route/probe mismatch rather than an ingestion cause.
- PostgreSQL: `pg_isready` accepted connections; PostgreSQL 16.14; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence observed. Existing data remained intact: 33,797 source documents, 186 reports, 201 report versions/publications, 378 detections, 201 hunts, and 201 remediation records.
- Resources: root filesystem 43% used with 278G available; memory 62Gi total, 49Gi available; host file descriptor limit 4096.
- Backup: latest metadata `/backups/latest.metadata`, artifact `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 recorded in metadata. Restoreability was not tested during diagnosis.
- Certificate: Caddy certificate presented issuer `Caddy Local Authority - ECC Intermediate`, valid `2026-09-15T15:39:23Z` through `2026-09-16T03:39:23Z`; no expiry indication at observation time.
- Docker events showed routine health/readiness/backup/monitor exec probes only; no service restart or crash event during the observation window.

## Recovery gate and actions

- Recovery gate evaluated with the 1,800-second cooldown and lock using the authoritative monitor evidence.
- Gate event `e3e599c6-da2e-4b23-a4b2-5898fd473cc0` was recorded as `attempted`, then `completed` with outcome `suppressed` because this request authorizes diagnosis only. The lock was verified removed. No service restart, ingestion rerun, deployment, migration, credential change, volume operation, or data mutation was performed.
- This incident document is the only repository-side artifact added by this diagnosis.

## Impact, integrity, rollback, prevention

- Impact: ingestion is partially successful but the latest run is not full-success; ThreatFox-derived freshness is stale since `2026-09-11T12:06:49+00Z`. Existing persisted evidence and publications remain available; no integrity violation was observed.
- Rollback: not applicable; no production change was made. Do not deploy the uncommitted configuration change until it has focused bounded-response/regression validation and explicit deployment authorization. If an authorized deployment fails health checks, use the previous stable image/commit through `./scripts/update-app.sh`.
- Prevention: validate the 50 MiB bounded/paginated ThreatFox request against an offline fixture with decompression/memory limits; add/retain oversized-response regression coverage; reconcile persisted source configuration with checked-in `config/sources.json`; deploy only via `./scripts/update-app.sh`; verify the next run, monitor evidence, source status, and publication integrity. Separately investigate ACSC failures, the external live-route probe mismatch, and encrypted-backup restoreability.
