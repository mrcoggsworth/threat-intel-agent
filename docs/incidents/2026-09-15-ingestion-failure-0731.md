# Production ingestion incident: actionable partial-ingestion failure (07:31Z)

## Classification

- **Recorded:** 2026-09-15T07:31:27Z
- **Impact:** ingestion is partially degraded. Latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed overall after 37/38 sources and persisted 13,108 new documents. Successful-source data remains usable; reports and publications have not advanced since 2026-09-11T22:24:37.163555Z.
- **Cause confidence:** high for the deployed source-boundary cause; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The authoritative configured fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=e2f9d4cb-ca48-49cc-959b-12fad6c33810`
- `observed_at=2026-09-15T07:30:08.226558+00:00`
- `correlation_id=227b9155-c695-4eef-9e85-ac0d89dbceb6`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared recovery gate was evaluated before any recovery action with its 1,800-second cooldown and lock:

- `allowed=false`, reason `recovery cooldown is active`
- gate event `c1659287-001f-47bf-aa9c-8bf3b4947e08`
- gate correlation `bc1ec359-5b20-405d-bf9d-3d0c374e6cbb`
- run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- suppressed event was recorded without secrets at `2026-09-15T07:31:27.622613Z`
- read-back verified `/runtime/recovery.lock` is absent; prior attempt state is `2026-09-15T07:01:28.439786+00:00`

No recovery was attempted because the gate suppressed it and this request authorizes diagnosis, not recovery or deployment.

## Evidence collected

- **Time/repository/release:** current UTC `2026-09-15T07:30:51Z`; repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. Substantial pre-existing working-tree changes were observed and not modified.
- **Application/image:** application version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`. The CTI-Hermes application containers use this image.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, and backup are running and healthy with restart count 0. Worker is exited code 0 and intentionally `restart: no`/reserved; it is not the ingestion owner. No relevant Docker restart/start/die events were found in the checked window.
- **Health/readiness:** internal web checks returned `/health/live` HTTP 200 `{"status":"ok"}`, `/health/ready` HTTP 200 with configuration/database `ok`, and `/version` HTTP 200 `{"name":"hermes-cti","version":"0.1.0"}`. Host port 8000 was not published, so direct host probes were connection-refused; this does not contradict the monitor's authenticated internal HTTP 200.
- **Scheduler/monitor:** scheduler heartbeat `/runtime/scheduler.heartbeat` was present at 07:32Z. Monitor remains healthy and repeatedly reports stale full-success plus failed latest attempt.
- **Runs/source:** latest run started `2026-09-15T02:00:00.049118Z` and completed `2026-09-15T02:00:54.439155Z`; status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `ThreatFox Recent Indicators (Abuse.ch)` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`; last success `2026-09-11T12:06:49.272951Z`, consecutive failures 7.
- **Database/migrations:** PostgreSQL accepted read-only queries; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence. Application data is in the authoritative singular tables.
- **Downstream:** report 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication is `2026-09-11T22:24:37.163555Z`; latest relationship is `2026-09-01T08:03:29.014597Z`.
- **Resources:** `/` is 43% used with 279G available; host memory 62GiB total/52GiB available; FD limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backup:** encrypted backups exist through `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) with `latest.metadata` present (198 bytes). Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy or certificate cause observed.
- **Configuration/deployment:** checked-out `config/sources.json` contains an undeployed ThreatFox `max_response_bytes=52428800` change; the running configuration remains the 10 MiB boundary. Running Compose metadata references `/opt/cti-hermes/env/production.env`. Compose validation could not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production outage evidence. No deployment/config mutation was made.

## Diagnosis and rollback

The failure is source/provider-specific: the deployed ThreatFox boundary rejects a response larger than 10 MiB. Web, proxy, worker, scheduler, database, disk, certificate, backup, and migration evidence do not indicate the cause. The smallest reversible follow-up is to review and test the existing bounded 50 MiB configuration (including decompression/memory implications), or prefer provider-side pagination/filtering, then deploy only through `./scripts/update-app.sh` under explicit authorization.

**Action:** diagnosis only; recovery suppressed by cooldown. This incident evidence was recorded. **Rollback:** not applicable; no application or data mutation occurred. Failed run/source records and partial successful-source data remain preserved.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, validate ThreatFox filtering/pagination or the bounded 50 MiB fixture, run focused regression tests, and deploy only with `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Correct operational diagnostics to the singular schema and run encrypted-backup restore verification separately.
5. Add source-specific handling for repeated `oversized_response` failures.
