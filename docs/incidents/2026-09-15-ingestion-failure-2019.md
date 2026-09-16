# Production ingestion incident: ThreatFox bounded-response failure (20:19Z)

## Classification

- **Recorded:** 2026-09-15T20:19:03Z
- **Impact:** ingestion remains partially degraded. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and persisted 13,108 new documents, but failed ThreatFox. Successful-source data remains usable; the latest full-success run is stale and downstream analyst/publication projections have not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the deployed source-boundary mismatch; low-to-medium for upstream response growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before diagnosis:

- `state=actionable_failure`
- `event_id=1503528a-9093-495d-a8de-b2f845a0b224`
- `observed_at=2026-09-15T20:19:03.684968+00:00`
- `correlation_id=9fefc4cb-8ce3-4ca4-a389-7114089c8a90`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

No recovery was attempted because this scheduled request authorizes diagnosis only. The shared gate history shows the same run was most recently suppressed at 2026-09-15T19:47:10Z while cooldown was active; the gate was unlocked after that evaluation. No service restart, collection retry, or deployment was run.

## Evidence collected

- **Repository/release:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; 59 pre-existing working-tree status entries remain unexplained and were not modified.
- **Application/image:** running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:54:53Z; application package version remains `0.1.0`.
- **Container state/restarts:** web, scheduler, monitor, PostgreSQL, and backup are running and healthy with restart count 0. Worker is not running by design (`restart: no`). No OOM signal was observed. Scheduler heartbeat was current at 2026-09-15T20:19:17Z; monitor evidence was current at 20:19:03Z.
- **Health/readiness/logs:** web health/readiness and run-status requests returned HTTP 200. Monitor repeatedly reports only stale full-success and failed latest attempt. No scheduler crash-loop or web failure was observed.
- **Run/source:** latest run completed 2026-09-15T02:00:54.439155Z with 38 total, 37 successful, 1 failed, and 13,108 new documents. `ThreatFox Recent Indicators (Abuse.ch)` failed with no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. The database source row still has `max_response_bytes=10485760` and seven consecutive failures.
- **Database/migrations:** `pg_isready` accepted connections; Alembic revision is `0015_contradiction_lifecycle`. The authoritative `ingestion_run`, `source_run`, and `source` queries succeeded. Recent PostgreSQL errors are malformed operator queries against nonexistent plural tables/columns, not application transaction failures.
- **Downstream:** reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp remains 2026-09-11T22:24:37Z.
- **Resources/events:** root filesystem is 43% used with 278G available; host memory reports 49GiB available; shell FD limit is 4096. No CTI-Hermes container restart event was identified; observed Docker events were health-check exec activity from other stacks and read-only diagnostics.
- **Backup:** latest artifact `/backups/hermes-20260915T125523Z.dump.enc`, 24,823,024 bytes, completed 2026-09-15T12:55:26Z; metadata SHA-256 is recorded in the protected backup metadata. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and cache reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no relevant TLS/proxy failure was observed.
- **Configuration/deployment:** checked-out `config/sources.json` contains an undeployed bounded ThreatFox `max_response_bytes` change to 52,428,800 bytes (50 MiB), while the running database and image behavior remain at 10 MiB. Compose config validation could not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not evidence of a production stack failure.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, scheduler, worker, database, disk, certificate, backup, and migration state do not indicate the primary cause. The smallest reversible next step is explicit review of the existing bounded 50 MiB configuration change, focused oversized-response regression tests, and deployment only through `./scripts/update-app.sh`. No authorized mutation exists in this request.

## Rollback/recovery state

Rollback is not applicable. The failed run/source records remain preserved, partial successful-source data remains available, the recovery lock is absent, and no production state was changed.

## Prevention/follow-up

1. Under explicit maintenance/deployment authorization, assess memory/decompression implications of the 50 MiB bound, run focused regression tests, and deploy only through `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox result, full-success/usable-run projections, monitor evidence, and report/publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Use the authoritative singular schema in operational queries and perform encrypted-backup restore verification separately.
5. Add source-specific alert context for repeated `oversized_response` failures.
