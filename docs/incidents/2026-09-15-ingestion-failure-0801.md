# CTI-Hermes production ingestion failure diagnostic (08:01Z)

## Classification

- **Observed:** `2026-09-15T08:01:10.499050+00Z`; diagnostic completed at approximately `2026-09-15T08:02Z`.
- **Impact:** partial ingestion degradation. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox remains stale; full-success freshness is `stale_data` and latest-attempt/usable-run status is `actionable_failure`.
- **Cause confidence:** high for the deployed ThreatFox response-size boundary; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`. Per the deployed Compose fallback, authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=19107326-008f-4ad4-81ba-d2d83c53d7f2`
- `observed_at=2026-09-15T08:01:10.499050+00:00`
- `correlation_id=a3e11508-2f6e-4187-856e-425d1fe03d51`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

A later monitor refresh remained actionable at `2026-09-15T08:02:10.570567+00Z`, event `38002297-6c36-45db-ada4-a3be05754ee0`, correlation `38018463-92fa-4a3d-a6f0-aeaa44dccef0`, same endpoint/status and run ID.

## Recovery gate

The shared recovery gate was evaluated before any recovery action using the 1,800-second cooldown and lock. It recorded a suppressed event for `19107326-008f-4ad4-81ba-d2d83c53d7f2` at `2026-09-15T08:01:36.920476+00Z` with reason `recovery cooldown is active`; read-back verified `/runtime/recovery.lock` is absent. No recovery action was attempted because this scheduled request authorizes diagnosis only.

## Evidence collected

- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and not modified except for this incident record.
- **Application/image:** application version `0.1.0`; web/scheduler/monitor/backup use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; services started `2026-09-12T12:55:15Z` (monitor `12:55:20Z`); PostgreSQL started `2026-09-05T16:36:57Z`.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, and backup are running and healthy with restart count 0. Worker is intentionally exited code 0 with `restart: no`; runtime-init is an old exited initialization container. No relevant CTI container restart events were found; Docker event output was dominated by unrelated health-check execs in other Compose projects.
- **Health/readiness:** monitor observed internal run-status HTTP 200. Web logs show successful `/health/live`, `/health/ready`, and `/api/v1/ops/run-status` requests. Scheduler heartbeat and last-success probes were served with HTTP 200. PostgreSQL `pg_isready` succeeded.
- **Ingestion/database:** PostgreSQL 16.14; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence. Latest run is `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Source state shows last success `2026-09-11T12:06:49.272951+00Z`, last failure `2026-09-15T02:00:54.421527+00Z`, seven consecutive failures, and persisted `max_response_bytes=10485760`.
- **Downstream:** source documents 33,797 (latest `2026-09-15T02:00:54.267448+00Z`); reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication `2026-09-11T22:24:37Z`; latest relationship `2026-09-01T08:03:29Z`.
- **Resources:** root filesystem 43% used with 279G available; host memory 52GiB available; open-file limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backups:** backup container healthy. Latest metadata identifies `/backups/hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with recorded SHA-256 metadata; artifact is readable. Restore verification was not run.
- **Proxy/certificate:** Caddy running with restart count 0. Logs show successful local certificate renewal and managed-certificate reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy or certificate cause indicated.
- **Configuration/deployment:** checked-out `config/sources.json` adds `max_response_bytes=52428800` for ThreatFox, while the running DB/image still enforces 10 MiB. Latest relevant source configuration commit is `62cd5bd` (`fix(deploy): provide Abuse.ch key to web collections`); current running services predate the checked-out configuration change. The Git repository also emits a pre-existing non-monotonic `.idx` warning during log operations.
- **Operational logs:** scheduler logs contain the source collection failure; PostgreSQL logs also contain repeated harmless legacy diagnostic queries against nonexistent tables/columns, indicating probe/schema drift but not a database outage.

## Diagnosis and action

The failure is source/provider-specific: the deployed ThreatFox request is rejected when its response exceeds 10 MiB. The checked-out configuration allows 50 MiB, but it is not deployed and the persisted source configuration remains 10 MiB. Web, proxy, scheduler process, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the primary cause. Re-running unchanged ingestion would reproduce the deterministic failure and was not attempted.

- **Service state:** web, scheduler, monitor, database, backup, and proxy healthy; collection completeness degraded for one source; full-success and analyst/publication freshness stale.
- **Action:** diagnosis only; recovery gate suppressed under cooldown. No stack mutation.
- **Rollback:** not applicable; no application or data mutation occurred. Successful-source data and failed-source records remain preserved.

## Prevention / follow-up

1. With explicit maintenance/deployment authorization, review ThreatFox pagination/filtering or the bounded 50 MiB limit, including decompression and memory impact; retain `oversized_response` classification and add/verify regression coverage.
2. Run focused tests and deploy only through `./scripts/update-app.sh`; verify the next run, ThreatFox status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema to stop emitting misleading relation/column errors.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
