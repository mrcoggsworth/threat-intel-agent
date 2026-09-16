# CTI-Hermes production ingestion failure diagnostic (18:18Z)

- **Diagnosis time:** 2026-09-15T18:18:13Z
- **Authoritative monitor evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (the cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was used before any model work)
- **Monitor state:** `actionable_failure`
- **Event ID:** `711aef7f-1366-4c41-90b2-f4e448c34293`
- **Observed at:** `2026-09-15T18:15:54.948569+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `26416eb1-2380-4386-b80b-89dfdbcf6f8`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data`, `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- **Repository:** `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Branch/HEAD:** `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch was ahead of `origin/main` by 3 at diagnosis.
- **Working tree:** pre-existing modifications, deletions, and untracked files; this diagnostic added only this incident record.
- **Running image:** `cti-hermes:local`; web image/container ID prefix `9e8d0a379cc5`, monitor `a471ee44d486`, scheduler `92e77d7ae50a`; all started 2026-09-12 and have restart count 0.
- **Application version:** `0.1.0` from `/version`.
- **Migration revision:** `0015_contradiction_lifecycle`.
- **Last relevant configuration boundary:** database source configuration still has ThreatFox `max_response_bytes=10485760`; the checked-in/pre-existing 50 MiB change was not deployed by this job.

## Diagnosis and impact

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The only failed source is `threatfox-recent-indicators-abuse-ch`, classified as `oversized_response` with detail `response exceeds 10485760 bytes`. Its last successful retrieval was 2026-09-11T12:06:49.272951Z; consecutive failure count is 7. The latest five runs are failed with 37 successful and 1 failed source. The run is **partially usable**, but not a full-success run; full-success freshness is stale. Reports, report versions, publications, detections, hunts, and remediation artifacts were last updated at 2026-09-11T22:24:37.163555Z.

**Cause confidence: high.** Evidence points to an isolated ThreatFox response-size boundary/provider configuration mismatch, not a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, migration, backup, certificate, publication, or persistence-integrity failure.

## Evidence captured

- Web, monitor, scheduler, PostgreSQL, and backup containers are running and healthy. `OOMKilled=false`, restart count 0, and no restart loop observed.
- Internal `/health/live`, `/health/ready`, and `/version` returned HTTP 200; readiness reported configuration and database `ok`.
- Scheduler heartbeat was fresh at `2026-09-15T18:17:16Z`.
- PostgreSQL accepted connections (`pg_isready`), reported PostgreSQL 16.14, and confirmed Alembic revision `0015_contradiction_lifecycle`.
- Host capacity: root filesystem 43% used with 278G available; 49G memory available; swap 1.8 MiB used; open-file limit 4096. Container memory remained low in `docker stats` (scheduler 378.7 MiB, web 307 MiB, PostgreSQL 259.4 MiB).
- Latest encrypted backup metadata: `/backups/hermes-20260915T125523Z.dump.enc`, completed 2026-09-15T12:55:26Z, 24,823,024 bytes; checksum metadata is present. Restore/checksum verification was not attempted.
- Certificate was not re-verified in this run because the Caddy image lacks `openssl`; prior evidence recorded validity through 2026-09-16T03:39:23Z. This is not indicated as the ingestion cause.
- `docker compose config` could not be interpolated from the cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is a maintenance-job configuration gap, not evidence of a running service outage.
- Recent PostgreSQL diagnostic log entries include prior operator queries using incorrect table/column names; those statements failed read-only and did not mutate data.

## Recovery gate and action

The shared recovery gate was evaluated after reading the authoritative actionable evidence, using the configured 1,800-second cooldown and `/runtime` lock. It returned `allowed=false`, reason `recovery cooldown is active`, and recorded suppressed gate event `1c3fa9ab-e5f1-4613-8aeb-2a2339dc2b2b` with correlation `f7651018-f071-4db3-a1bc-6c9dabec320d` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Read-back verified `/runtime/recovery.lock` is absent. The preceding gate attempt `52c5aca7-682f-4f7a-920a-48f08cf41ee6` was recorded as `attempted` at 18:02:55Z and completed as `suppressed` at 18:03:19Z. No retry, restart, deployment, migration, credential change, or destructive recovery was authorized or performed.

## Service, data integrity, rollback, and prevention

- **Impact:** one public source is stale; collection remains partial; full-success and downstream report/publication freshness are stale. Web readiness and database connectivity remain healthy.
- **Data integrity:** preserved. Failed-source and partial-ingestion evidence remains persisted and visible; 13,108 new documents from the failed run were retained. No volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no application or production-data mutation occurred.
- **Prevention/follow-up:** under explicit maintenance/deployment authorization, validate bounded or paginated ThreatFox retrieval, add mocked oversized-response regression coverage, reconcile persisted source configuration with the intended checked-in limit, and deploy only through `./scripts/update-app.sh`. Export `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` to maintenance jobs while retaining the container fallback. Separately verify encrypted-backup restoreability and certificate state when the required tooling is available. Do not retry until the recovery gate permits it.
