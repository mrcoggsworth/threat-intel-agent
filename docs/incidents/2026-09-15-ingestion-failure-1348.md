# CTI-Hermes actionable ingestion failure diagnostic

- **Diagnosis time:** 2026-09-15T13:48Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `5525aa86-10cc-4db3-ba9e-b1813847a58b`
- **Observed at:** `2026-09-15T13:46:35.855613+00:00`
- **Correlation ID:** `514e77a1-0878-4d36-91a5-99269a5a7485`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200` (internal monitor route)
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** substantial pre-existing modifications, deletions, and untracked files; this incident file is the only intentional addition from this diagnosis.

## Impact

The latest scheduled ingestion run persisted as `failed`: 37/38 sources completed and one failed. It added 13,108 documents; failed-source evidence remains recorded. The failed source is not fresh. Database projections currently contain 33,797 source documents (latest retrieval `2026-09-15T02:00:54.267448+00`), 186 reports, 201 report versions, and 201 publications. Report/version/publication freshness remains `2026-09-11T22:24:37.163555+00`. The full-success monitor signal is stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`). No evidence of data loss was found.

## Evidence and diagnosis

- The failed source is `threatfox-recent-indicators-abuse-ch`. Its `source_run` has `status=failed`, `http_status` unset, `item_count=0`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.
- The current failed run is `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, with 38 total, 37 successful, 1 failed, and status `failed`. Persisted application version is `0.1.0`; configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running healthy with restart count 0 and OOM false. The application image is `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; CTI application containers started `2026-09-12T12:55Z`.
- Internal web checks returned `/health/live` HTTP 200 (`{"status":"ok"}`) and `/health/ready` HTTP 200 (`configuration=ok`, `database=ok`). The internal run-status route returned HTTP 404 when directly requested despite the monitor evidence being produced from that route; this route mismatch is a follow-up issue, not evidence of web/database unavailability.
- The scheduler heartbeat was current at `2026-09-15T13:48:14Z`. Monitor logs repeatedly report `last successful run stale, latest ingestion attempt failed`; no scheduler traceback or container restart loop was observed. Docker events in the sampled window showed exec health checks only, not container restarts.
- PostgreSQL accepted connections (`/var/run/postgresql:5432 - accepting connections`), and Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration was observed from the available revision evidence. A combined diagnostic query initially referenced incorrect column names; it was corrected without changing data.
- Host capacity is not limiting: root filesystem is 43% used with 279G available; 62 GiB memory with 49 GiB available; swap use is negligible; host open-file limit is 4096. No OOM state was reported.
- Latest encrypted backup is `/backups/hermes-20260915T125523Z.dump.enc`, 24,823,024 bytes, completed `2026-09-15T12:55:26Z`; `/backups/latest.metadata` is present with SHA-256 metadata. Restore/checksum revalidation was not performed.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate renewal error was observed. The configured host certificate path was not present in this shell, so certificate state is based on Caddy's live renewal logs.
- The checked-out `config/sources.json` contains a pre-existing, undeployed ThreatFox `max_response_bytes=52428800` change. The running image's `/app/config/sources.json` has no corresponding field, confirming that change is not deployed.

**Cause confidence: high.** This is a recurring deterministic provider/source response-size failure at the ThreatFox/Abuse.ch boundary: the deployed ingestion path enforces a 10 MiB maximum and the response exceeds it. Web, proxy, worker/scheduler liveness, PostgreSQL, disk, memory, migration, backup, and certificate failures are not supported by the collected evidence. The upstream reason for payload growth is uncertain.

## Recovery gate and actions

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative evidence was read from the configured Compose-mounted fallback `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`. The shared recovery gate was evaluated with its 1,800-second cooldown and lock at `2026-09-15T13:47:12.847451Z`; it returned `allowed=true` and recorded an `attempted` event for the current event/correlation/run IDs. Because this request authorizes diagnosis only, no recovery action was attempted. The gate was completed with outcome `suppressed`, and read-back verified `/runtime/recovery.lock` is absent.

No restart, ingestion retry, deployment, migration, credential change, volume/data deletion, backup deletion, or destructive recovery was performed. `docker compose ps` validation could not run from this shell because protected deployment variables (`HERMES_SECRET_DIR` and `HERMES_IMAGE`) were not exported; live container inspection was used instead.

## Service, integrity, rollback, and prevention

- **Service:** web/readiness and database connectivity healthy; scheduler heartbeat current; ingestion partially degraded for one source; full-success and analyst/publication freshness stale.
- **Data integrity:** preserved. Partial ingestion and failed-source records remain visible; no database, evidence, volume, backup, migration history, or public CTI conclusion was changed.
- **Rollback:** not applicable; no application or production-data mutation was made.
- **Prevention:** validate the bounded/paginated ThreatFox request and the existing 50 MiB configuration change with regression coverage, then deploy only through `./scripts/update-app.sh` when explicitly authorized. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback. Investigate the internal-versus-host run-status route mismatch. Perform encrypted-backup restore verification separately.
