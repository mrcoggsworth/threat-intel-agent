# Production ingestion incident: ThreatFox bounded-response failure (03:47Z)

## Classification

- **Recorded:** 2026-09-15T03:47:54Z
- **Impact:** ingestion remains partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and failed only ThreatFox, while persisting 13,108 new documents. Successful-source data remains usable, but no full-success run has completed since `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` and downstream analysis/publication has not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the immediate deployed source-boundary cause; low-to-medium for the upstream payload growth.
- **Data integrity:** preserved. No ingestion retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured authoritative fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=311b844b-c985-4854-9356-ae392493a730`
- `observed_at=2026-09-15T03:45:52.258919+00:00`
- `correlation_id=5304b6da-9e15-426d-b0cd-e49a133cbcd8`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

The monitor refreshed during diagnosis. Post-check evidence at 2026-09-15T03:46:52.333957+00Z remained `actionable_failure`, event `c618be3f-b736-4a1e-9a0d-42bc9e4509e7`, correlation `2b8d25b3-49b4-4658-93af-a59bb9d02670`, endpoint/status unchanged, and the same run ID.

## Recovery gate

The shared recovery gate was evaluated before any recovery action with a 1,800-second cooldown and lock. It acquired attempted event `311b844b-c985-4854-9356-ae392493a730` at `2026-09-15T03:46:38.175892+00Z`, with correlation `5304b6da-9e15-426d-b0cd-e49a133cbcd8` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Because this scheduled request authorizes diagnosis only and the failure is source/provider-specific, no recovery action was attempted. The gate audit was completed with `outcome=suppressed`, and read-back verified `/runtime/recovery.lock` absent. The gate CLI left the lock until completion; it was explicitly completed and then verified absent.

## Evidence collected

- **Repository/release:** repository `main`, HEAD `c925cd5` (`c925cd5bbb1b2c872841205b90ea05ea4636da76`), three commits ahead of `origin/main`; substantial pre-existing working-tree changes are present. No deployment or stack update was run.
- **Application/image:** image `cti-hermes:local`, ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:54:53Z; application version `0.1.0`. Web, scheduler, monitor, backup, and PostgreSQL have zero restarts. Worker is exited code 0 by design (`restart: no`).
- **Container health:** web, scheduler, monitor, PostgreSQL, and backup are running/healthy. Web `/health/live` and `/health/ready` both returned HTTP 200; readiness reported configuration and database `ok`. Scheduler heartbeat mtime was 2026-09-15T03:47:40Z. No Docker container events occurred in the six-hour window.
- **Runs/source:** latest run started 2026-09-15T02:00:00.049118Z and completed 2026-09-15T02:00:54.439155Z; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Persisted source configuration remains `max_response_bytes=10485760`, last success 2026-09-11T12:06:49Z, consecutive failures 7, and two recorded failures.
- **Database/migrations:** PostgreSQL accepted read-only queries; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence. Authoritative singular tables are present (`ingestion_run`, `source_run`, etc.). Repeated PostgreSQL errors in recent logs are operator diagnostic queries against nonexistent plural tables/columns, not application transaction failures.
- **Downstream:** counts are reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp is 2026-09-11T22:24:37Z; relationship latest is 2026-09-01T08:03:29Z.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total with 52GiB available; shell FD limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backup:** latest backup artifact is `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with `latest.metadata` present and mtime 2026-09-14T12:55:23Z. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful renewal and reload for `hermes.cti.scogin.dev`; no proxy or certificate cause observed.
- **Configuration/deployment:** checked-out `config/sources.json` contains `max_response_bytes=52428800` for ThreatFox, but the running image/database configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`; this change is not deployed. Compose config validation could not run because the shell lacks the required protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` environment variables; this is an operator-environment validation limitation, not evidence of a production stack failure.

## Diagnosis, action, and rollback

The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. Web, proxy, worker, scheduler, database, disk, certificate, backup, and migration state do not indicate the cause. The working tree contains an undeployed 50 MiB bounded-response configuration change. No service mutation was authorized or performed.

**Rollback:** not applicable. Recovery gate bookkeeping was completed and the lock is absent. Existing failed run/source records and partial successful-source data remain preserved.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review the 50 MiB bound for memory/decompression implications, run focused regression tests, and deploy only through `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness after any authorized deployment.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose environment variables in the maintenance cron environment while retaining the container fallback.
4. Correct future operational queries to the authoritative singular schema and perform encrypted-backup restore verification separately.
5. Add source-specific classification/runbook handling for repeated `oversized_response` failures.
