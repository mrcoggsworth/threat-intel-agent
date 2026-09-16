# Production ingestion incident: actionable partial-ingestion failure (07:16Z)

## Classification

- **Recorded:** 2026-09-15T07:16:07Z
- **Impact:** ingestion is partially degraded. Latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed overall after processing 37/38 sources and persisted 13,108 new documents. Successful-source data remains usable; the last full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`. Reports/publications have not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the immediate deployed source-boundary cause; low-to-medium for the upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured Compose fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=9ea29cdd-26af-4cd0-92ee-4ef7002db870`
- `observed_at=2026-09-15T07:16:07.235204+00:00`
- `correlation_id=0663ff9b-be3b-4f56-9959-3bdf02164d45`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared gate was evaluated before any recovery action with its configured 1,800-second cooldown and lock:

- decision `allowed=false`
- reason `recovery cooldown is active`
- event/correlation/run: `9ea29cdd-26af-4cd0-92ee-4ef7002db870` / `0663ff9b-be3b-4f56-9959-3bdf02164d45` / `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- the suppressed event was recorded by the gate without secrets
- read-back verified `/runtime/recovery.lock` is absent

No recovery was attempted because the gate suppressed it and this scheduled request authorizes diagnosis, not destructive recovery or deployment.

## Evidence collected

- **Time/repository/release:** current UTC `2026-09-15T07:15:55Z`; repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; substantial pre-existing working-tree changes are present and were not modified. Remote is `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- **Application/image:** running application image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, application version `0.1.0` from the latest persisted run. All application containers use the same image.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, and backup are running/healthy with restart count 0. Worker is exited code 0 with `restart: no` by design and is reserved for a later analysis phase; it is not the ingestion owner. No Docker container events were observed in the checked eight-hour window.
- **Health/readiness:** host checks returned `/health/live` HTTP 200 `{"status":"ok"}` and `/health/ready` HTTP 200 with configuration and database `ok`. Monitor reached the internal run-status endpoint at HTTP 200. Compose config validation could not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production outage evidence.
- **Scheduler/monitor:** scheduler heartbeat exists and is fresh; monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`. Recovery state records a prior attempt at `2026-09-15T07:01:28.439786+00`; lock is absent after suppression.
- **Runs/source:** latest run started `2026-09-15T02:00:00.049118Z` and completed `2026-09-15T02:00:54.439155Z`; status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents, error summary `1 source(s) failed`. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Persisted source configuration is `max_response_bytes=10485760`, last successful retrieval `2026-09-11T12:06:49.272951Z`, consecutive failures 7.
- **Database/migrations:** PostgreSQL is accepting connections; database/user `hermes|hermes`; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence was found. Authoritative schema is singular (`ingestion_run`, `source_run`, etc.). Repeated PostgreSQL errors in recent logs are malformed operator diagnostic queries against wrong table/column names, not application transaction failures.
- **Downstream:** reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp is `2026-09-11T22:24:37.163555+00`; latest relationship timestamp is `2026-09-01T08:03:29.014597+00`.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total with 52GiB available; shell FD limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backup:** encrypted artifacts exist through `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) with `/backups/latest.metadata` mtime `2026-09-14T12:55`. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy or certificate cause observed.
- **Configuration/deployment:** checked-out `config/sources.json` contains an undeployed ThreatFox `max_response_bytes=52428800` change, while the running configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`. No deployment or stack update was run.

## Diagnosis, action, rollback

The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. Web, proxy, worker, scheduler, database, disk, certificate, backup, and migration evidence do not indicate the cause. The smallest reversible follow-up is to review and test the existing bounded 50 MiB source configuration (including memory/decompression implications), then deploy only through `./scripts/update-app.sh` under explicit maintenance authorization. A paginated/provider-bounded request is preferable if available.

**Action taken:** diagnosis only; recovery suppressed by cooldown. Incident evidence recorded in this file. No production state mutation occurred.

**Rollback:** not applicable; no application or data mutation was made. Failed run/source records and partial successful-source data remain preserved; recovery lock is absent.

## Prevention / follow-up

1. Review the 50 MiB bound or implement a paginated ThreatFox request; add/retain an oversized-response regression fixture and run focused tests before any deployment.
2. If authorized, deploy only with `./scripts/update-app.sh`, then verify failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose environment variables in the maintenance cron environment while retaining the container fallback.
4. Correct operational diagnostics to the singular schema and valid column names to stop avoidable PostgreSQL log noise.
5. Run encrypted-backup restore verification separately; artifact presence alone does not establish restore integrity.
6. Add source-specific monitor/runbook handling for repeated `oversized_response` failures.
