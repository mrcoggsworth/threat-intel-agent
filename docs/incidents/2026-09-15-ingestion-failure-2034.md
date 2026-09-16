# CTI-Hermes production ingestion failure diagnostic (20:34Z)

- **Diagnosis time:** 2026-09-15T20:34Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the configured container fallback was used.
- **Monitor state:** `actionable_failure`
- **Event ID:** `37c1048b-8375-4237-aa1e-db23b256e520`
- **Observed at:** `2026-09-15T20:34:04.761655+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `e6b90b99-002b-467d-919b-331c3b995540`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`
- **Gate-input evidence:** event `59916f7e-a86b-41dd-84d0-b424a55faaf5`, observed `2026-09-15T20:32:04.606070+00`, correlation `d60f0240-0fce-44e4-87d0-9d752849f162`

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch ahead of `origin/main` by 3.
- Working tree contained pre-existing modifications and untracked files; this diagnostic added this incident record only.
- Running image: `cti-hermes:local`, image ID and repo digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Persisted application version: `0.1.0`.
- Database migration revision: `0015_contradiction_lifecycle`.

## Impact and cause

The latest persisted run is `failed`: 37/38 sources succeeded and one source failed. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), with `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, and zero items. Its last successful retrieval is `2026-09-11T12:06:49.272951+00`. The five latest persisted runs are failed with 37 successful and 1 failed source. No usable/full-success run is present in the monitor projection; the full-success projection is stale.

**Cause confidence: high.** The failure is isolated to the deployed ThreatFox response-size boundary/configuration mismatch. The checked-in but undeployed source change raises `max_response_bytes` to 50 MiB. No evidence indicates a web, proxy, worker, scheduler, database, disk, memory, descriptor, certificate, backup, or migration outage.

## Operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running healthy with restart count 0 and `OOMKilled=false`; worker is not a separate running service by design. Docker events were health-check `exec_*` events only, with no CTI service restart.
- Scheduler heartbeat was fresh: `2026-09-15T20:33:47Z`. Web live/readiness returned HTTP 200. Internal run-status returned HTTP 200; host-side route probing returned HTTP 404, consistent with the known internal-versus-host operations-route mismatch.
- PostgreSQL accepted connections; database size is 195 MB; `alembic_version` is `0015_contradiction_lifecycle`. The container `alembic current` command could not connect because its maintenance command used localhost rather than the database service; this is an environment/configuration gap, not evidence of a migration failure.
- Persistence counts: 33,797 source documents, 186 reports, 201 report versions, and 201 publications. Failed-source and partial-ingestion records remain preserved.
- Host capacity is healthy: root filesystem 43% used with 278G available, 49G memory available, negligible swap use, and open-file limit 4096.
- Backup container is healthy. Latest metadata: `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore verification was not attempted.
- Caddy certificate revalidation succeeded: issued by `Caddy Local Authority - ECC Intermediate`, valid `2026-09-15T15:39:23Z` through `2026-09-16T03:39:23Z`.

## Recovery gate and actions

The shared 1,800-second recovery gate and `/runtime` lock were evaluated after reading the actionable evidence. The gate acquired and recorded attempted event `59916f7e-a86b-41dd-84d0-b424a55faaf5` with correlation `d60f0240-0fce-44e4-87d0-9d752849f162` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` at `2026-09-15T20:32:44.134573+00`, then recorded completion outcome `suppressed`. Read-back verified `/runtime/recovery.lock` absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed because this scheduled request authorizes diagnosis only.

## Service, data integrity, rollback, and prevention

- **Impact:** partial collection; ThreatFox remains stale; full-success and report/publication freshness remain stale. Web/readiness/database service remains healthy.
- **Data integrity:** preserved. Failed evidence and partial-ingestion records remain visible; no volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no production mutation occurred.
- **Prevention:** under explicit maintenance/deployment authorization, validate bounded or paginated ThreatFox retrieval or the staged 50 MiB configuration change, add mocked oversized-response regression coverage, and deploy only through `./scripts/update-app.sh`. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`; correct the container migration command's database endpoint; separately verify encrypted-backup restoreability and resolve the host/internal operations-route mismatch.
