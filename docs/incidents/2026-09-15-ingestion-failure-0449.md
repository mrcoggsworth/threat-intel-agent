# Production ingestion incident: actionable partial-ingestion failure (04:49Z)

## Classification

- **Recorded:** 2026-09-15T04:49Z
- **Impact:** ingestion is partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. Existing successful-source data remains usable; no new full-success run is established and downstream report/publication freshness remains stale.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream ThreatFox payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, publication mutation, or deletion was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event:** `61148966-7b22-4c12-99ba-c37bd6d4f2ed`
- **Observed:** `2026-09-15T04:48:56.763565+00:00`
- **Correlation:** `e6bbc4f2-0cab-4cbf-a240-fff6ca6f43e3`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- Full-success signal was `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest-attempt signal was `actionable_failure`, detail `1 source(s) failed`.

## Recovery gate and action

The shared gate was evaluated before any recovery action. The first evaluation acquired attempted event `052b0366-6960-4b68-bcde-1587e7770bb9` at `2026-09-15T04:46:45.228099+00`, with the 1,800-second cooldown and lock. This scheduled job authorizes diagnosis only, so no recovery mutation was attempted; the event was completed with outcome `suppressed` and lock read-back was `absent`. While monitor evidence rotated, the gate audit also contains an intermediate completion record for event `084091da-0e7a-4268-8a7f-a7ba9a269533`; no production service or data was changed and the lock remained absent. A subsequent evaluation of the newer monitor event `61148966-7b22-4c12-99ba-c37bd6d4f2ed` recorded `suppressed` at `2026-09-15T04:49:22.764148+00` because `recovery cooldown is active`; lock read-back was `absent`.

## Evidence collected

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is ahead of `origin/main` by 3 commits. Working tree contains substantial pre-existing modifications, deletions, scratch files, and the checked-out `config/sources.json` change; this incident adds only this record.
- **Running application:** `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`. Web, scheduler, monitor, and backup started 2026-09-12 with restart count 0. No deployment or config update was run.
- **Runs:** latest run started `2026-09-15T02:00:00.049118+00` and failed `2026-09-15T02:00:54.439155+00`; application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`, totals 38/37/1, 13,108 new documents. Failed source is `threatfox-recent-indicators-abuse-ch`, no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`; source consecutive failures `7`, last successful retrieval `2026-09-11T12:06:49.272951+00`.
- **Configuration drift:** persisted/running source limit is `10,485,760` bytes, configuration version `2`; checked-out but undeployed `config/sources.json` adds `max_response_bytes: 52428800` for ThreatFox. This is a candidate fix, not deployed or validated here.
- **Database/migrations:** `pg_isready` accepted; Alembic revision `0015_contradiction_lifecycle`; authoritative schema is singular (`ingestion_run`, `source_run`, etc.) and no pending/failed migration evidence was observed. Repeated PostgreSQL errors are from operator diagnostics using plural table names or wrong columns, not application transaction failures.
- **Service state:** monitor, web, scheduler, PostgreSQL, and backup are running and healthy with zero restarts. Worker is exited code 0 by design (`restart: no`) and is reserved for a later analysis phase. Web live/readiness returned HTTP 200 with database ready. The requested run-status path was not available from the direct web probe (HTTP 404), while monitor evidence obtained it through the internal route; no web liveness outage was indicated. No container named `cti-hermes-proxy-1` exists; the host `caddy` proxy is running with zero restarts.
- **Scheduler/monitor/logs:** scheduler heartbeat file was fresh at `2026-09-15T04:48:11Z`; scheduler logged `source collection failed`; monitor repeatedly reported stale full-success and failed latest attempt. Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`.
- **Data projections:** database counts/latest timestamps: `source_document` 33,797 (latest `2026-09-15T02:00:54.44279+00`), `report` 186 (latest `2026-09-11T22:24:37.163555+00`), `report_version` 201, `publication` 201, `detection` 378, `hunt` 201, `remediation` 201, `relationship` 11 (latest `2026-09-01T08:03:29.014597+00`).
- **Resources:** root filesystem 43% used, 279G available; host memory 62GiB total/52GiB available; file-descriptor limit 4096; no resource exhaustion indication. Docker reports 46.45GB images and 37.29GB build cache; no pruning was performed.
- **Backup:** latest metadata identifies `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; restore verification was not run.
- **Compose evidence gap:** host-side Compose interpolation is unavailable in this cron shell because production `HERMES_SECRET_DIR`/`HERMES_IMAGE` are not exported. Direct Docker inspection was used instead; this is an operational evidence gap, not evidence of stack failure.

## Diagnosis, rollback, and prevention

The immediate cause is source/provider-specific: the running implementation rejects the ThreatFox response above 10 MiB. The checked-out 50 MiB bound is a candidate reversible remediation but requires review of memory/decompression impact, focused regression tests, and deployment only via `./scripts/update-app.sh` under explicit authorization. Do not re-run unchanged ingestion during cooldown; it would reproduce the provider failure without repairing it.

Rollback is not applicable because no application or data mutation occurred. Recovery remains suppressed by the gate. Follow-up: reconcile the running image with checked-in source configuration, validate bounded ThreatFox filtering/pagination or an alternate endpoint using an offline fixture, retain an oversized-response regression fixture, export the monitor evidence path and protected Compose environment for maintenance jobs, and correct operational diagnostic schema drift. Verify the next run's failed-source status, full-success/usable-run projections, monitor state, and publication freshness after any authorized deployment.
