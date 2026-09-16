# CTI-Hermes production ingestion failure diagnostic (19:19Z)

- **Diagnosis time:** 2026-09-15T19:19:12Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **Monitor state:** `actionable_failure`
- **Event ID:** `25166c93-b122-4cb9-8d6e-50d46eedff74`
- **Observed at:** `2026-09-15T19:15:59.212563+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `e4835078-d948-410b-b812-9e1a22a31a50`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data` and `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- **Repository:** `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Branch/HEAD:** `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch ahead of `origin/main` by 3.
- **Working tree:** pre-existing modifications, deletions, and untracked files; this diagnostic added only this incident record.
- **Running image:** `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53-05:00`.
- **Persisted application version:** `0.1.0`.
- **Migration revision:** `0015_contradiction_lifecycle`.
- **Configuration:** live run hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`; working-tree config adds ThreatFox `max_response_bytes=52428800` but is not deployed.

## Diagnosis and impact

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The failed source is `threatfox-recent-indicators-abuse-ch`, classified as `oversized_response`, with detail `response exceeds 10485760 bytes`. The latest five persisted runs are failed, each with 37 successful and 1 failed source. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`; the latest usable run is the partial failed run above.

**Cause confidence: high.** Evidence isolates the failure to the ThreatFox provider response-size boundary. No evidence indicates web, proxy, worker, scheduler, PostgreSQL, disk, memory, file descriptors, migration, backup, certificate, or persistence-integrity failure as the primary cause.

Impact is limited to stale/partial ThreatFox coverage; full-success, report, and publication freshness remain stale. The 37 successful source results and their persisted documents remain usable, with the partial-coverage limitation visible.

## Operational evidence

- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy; all inspected services have `restart=0` and `OOMKilled=false`. Web and scheduler started `2026-09-12T12:55:15Z`; monitor `12:55:20Z`; PostgreSQL `2026-09-05T16:36:57Z`; backup `12:55:15Z`.
- Internal web checks returned liveness HTTP 200 (`{"status":"ok"}`) and readiness HTTP 200 with database `ok`.
- PostgreSQL accepted `select 1`; `alembic_version` is `0015_contradiction_lifecycle`. `ingestion_run` contains 26 failed and 2 completed runs. The initial plural-table query failed with `relation does not exist`; it was read-only and caused no mutation.
- Latest run row confirms 38 total, 37 successful, 1 failed, 13,108 new documents, and `error_summary='1 source(s) failed'`. Its `source_run` row confirms the exact ThreatFox classification/detail and no HTTP status.
- Scheduler logs show source collection failures at `2026-09-12T12:56:06Z`, `2026-09-13T02:00:06Z`, and `2026-09-15T02:00:54Z`. Monitor heartbeat was fresh through `2026-09-15T19:18:17Z`; monitor repeatedly reported stale full-success/latest failed attempt.
- Host capacity is healthy: root filesystem 43% used with 278G available; host memory has 49Gi available; monitor FD soft limit is 1024. No restart loop or resource exhaustion was observed.
- Backup metadata is present and readable by the backup service: `/backups/latest.metadata`, mode 600, completed `2026-09-15T12:55:26Z`, artifact `hermes-20260915T125523Z.dump.enc`, 24,823,024 bytes, SHA-256 recorded. Restore verification was not attempted.
- Caddy logs show successful local certificate renewal for `hermes.cti.scogin.dev`, with cached expiration `2026-09-16T03:39:24Z`; certificate/edge state is not the ingestion cause. Caddy is the proxy; no separate proxy container exists.
- `docker compose ps/config` from the cron environment could not be interpolated because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is a maintenance-job configuration gap, not evidence of a running service outage.

## Recovery gate and actions

The shared recovery gate was evaluated against the authoritative evidence inside `cti-hermes-monitor-1`, using the 1,800-second cooldown and `/runtime` lock. It recorded attempted event `a3319b94-1b42-42bc-821a-fb13c0e33a0e`, correlation `155fa035-9b6b-4313-b6b1-5f318e6c3539`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Because this request authorizes diagnosis only, the gate event was completed with outcome `suppressed`; read-back verified the recovery lock is absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, data integrity, rollback, and prevention

- **Service state:** web liveness/readiness and database connectivity healthy; ingestion is partial and full-success freshness is stale.
- **Data integrity:** preserved. Failed-source and partial-ingestion evidence remains persisted and visible; no volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no application or production-data mutation occurred.
- **Prevention:** under explicit maintenance/recovery authorization, implement bounded or paginated ThreatFox retrieval and mocked oversized-response regression coverage, then deploy only via `./scripts/update-app.sh`. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`; separately verify encrypted-backup restoreability and investigate internal-versus-host ops-route topology.
