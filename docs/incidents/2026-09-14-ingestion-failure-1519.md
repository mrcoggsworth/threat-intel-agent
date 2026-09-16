# Production ingestion incident: actionable failure diagnostic (15:19Z)

- **Observed at:** 2026-09-14T15:15:58.537616Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `bd4a9d30-640c-4cb7-9796-bc73c351ada2`
- **Correlation ID:** `00a5f6e2-4a04-4027-9972-e9be6a05dfd5`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; the cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured container-mounted fallback was used.
- **Repository:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`
- **Application:** version `0.1.0`; local image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T12:54:53Z

## Impact and persisted data

The latest scheduled collection was failed but usable in part: 37 of 38 sources succeeded, with 1,564 new documents and the failed source retained as a failed `source_run`. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at 2026-09-11T12:06:50.050468Z, so full-success freshness is stale. Source documents remain persisted (31,678 total; latest `2026-09-14T02:00:06.400617Z`). Reports/publications remain unchanged since 2026-09-11T22:24:37.163555Z (186 reports, 201 report versions, 201 publications).

## Diagnosis and evidence

Cause confidence is **high**: the failure is at the ThreatFox/Abuse.ch source/provider response-size boundary, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, or publication outage.

- Failed source: `threatfox-recent-indicators-abuse-ch`
- Source status: `failed`; item count `0`; cache `miss`
- Classification: `oversized_response`
- Detail: `response exceeds 10485760 bytes`
- Run: scheduled `2026-09-14T02:00:00Z`, completed `2026-09-14T02:00:06.398193Z`; 38 total / 37 successful / 1 failed
- Source consecutive failures: `5`; last successful retrieval `2026-09-11T12:06:49.272951Z`
- PostgreSQL accepts connections; Alembic revision is `0015_contradiction_lifecycle`; all expected public tables are present and no pending/failed migration evidence was found.
- Web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart counts are zero. Worker is an intentional exited service and has no restart loop.
- In-container web checks: `/health/live` HTTP 200, `/health/ready` HTTP 200 with database/configuration `ok`, `/version` HTTP 200 (`0.1.0`). Host loopback port 8000 is not published, so host curl is not an applicable probe.
- Scheduler logs show `source collection failed`; monitor continues refreshing once per minute and reports the same two failures: stale full-success run and failed latest attempt.
- Root filesystem is 43% used with 279G available; host memory available is 51GiB; host open-file limit is 4096. Web container soft open-file limit is 1024 (hard 524288). No OOM or restart evidence was observed.
- Backup state is healthy; encrypted artifacts include `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) and `latest.metadata` at 2026-09-14T12:55:23Z.
- Caddy logs show successful local certificate renewal for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; certificate is not the ingestion cause. Any external route/TLS trust issue remains separate.
- Checked-in working tree has unrelated existing modifications and deletions; no reset, cleanup, or deployment was performed. The repository's uncommitted `config/sources.json` raises `max_response_bytes` for ThreatFox to 50 MiB, but the running image predates that uncommitted change and was not altered.

## Recovery gate and actions

The monitor evidence was read before gate evaluation. The 30-minute cooldown/lock gate allowed an evidence-backed attempt at `2026-09-14T15:16:44.022390Z` and recorded event `bd4a9d30-640c-4cb7-9796-bc73c351ada2`. Because this scheduled request authorizes diagnosis but not recovery, no retry, restart, deployment, migration, source-limit change, credential change, or data mutation was performed. The gate was completed with `outcome=suppressed` at `2026-09-14T15:19:06.536547Z`; the runtime lock was verified absent and the audit record was read back.

## Service, integrity, and rollback state

- **Service:** internally live and ready; CTI collection freshness degraded and one source is unavailable.
- **Data integrity:** preserved. Successful source results, the failed source record, and prior backups remain present. No destructive recovery occurred.
- **Rollback:** not applicable; no application or deployment change was made.

## Prevention / follow-up

1. Bound or paginate the ThreatFox request so provider responses remain below the transport limit while retaining the `oversized_response` classification; add a mocked oversized-response regression test.
2. Reconcile the uncommitted source configuration with the running image and deploy only under an explicitly authorized maintenance/deployment action using `./scripts/update-app.sh`; verify the next run and monitor evidence afterward.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback.
4. Investigate the separate external Caddy route/TLS trust result and the known CLI asyncpg event-loop cleanup traceback.
