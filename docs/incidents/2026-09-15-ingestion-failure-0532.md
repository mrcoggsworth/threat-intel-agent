# Production ingestion incident: ThreatFox bounded-response failure (05:32Z)

## Classification

- **Recorded:** 2026-09-15T05:32Z
- **Impact:** ingestion is partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and persisted 13,108 new documents, but failed ThreatFox. Successful-source data remains usable; the latest full-success projection remains stale at run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`. Reports and publications have not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the deployed source-boundary mismatch; medium for the upstream response growth that exposed it.
- **Data integrity:** preserved. No ingestion retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

Read before further diagnosis from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell:

- `state=actionable_failure`
- `event_id=baaf4eb6-67fe-4718-ae6d-56b88fea147c`
- `observed_at=2026-09-15T05:30:59.690211+00:00`
- `correlation_id=81c0aa3b-858b-4377-8a84-81bd9a937744`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared gate was evaluated against the authoritative evidence at 2026-09-15T05:31:38.934542Z with the configured 1,800-second cooldown and `/runtime` lock. It acquired event `baaf4eb6-67fe-4718-ae6d-56b88fea147c`, then completed it with `outcome=suppressed` because this scheduled request authorizes diagnosis only; no recovery action was attempted. Read-back verified `/runtime/recovery.lock` is absent. The audit contains the attempted and completed records without secrets.

## Evidence collected

- **Repository/release:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; origin is `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree contains substantial pre-existing changes and deletions, so none were modified or reset.
- **Application/image:** `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:55:03Z; application version `0.1.0`.
- **Containers/restarts:** web, scheduler, monitor, PostgreSQL, and backup are running and healthy with restart count 0. Worker is not present in the active container listing; no worker action was taken. Runtime-init is an old completed one-shot container. No OOM indication was observed.
- **Health/readiness:** web live and ready checks returned HTTP 200 from inside the web container. Scheduler heartbeat mtime was 2026-09-15T05:32:11Z; monitor evidence mtime was 2026-09-15T05:31:59Z. PostgreSQL health checks report accepting connections.
- **Logs/events:** scheduler reports `source collection failed`; monitor repeatedly reports stale full-success plus failed latest attempt. Web logs show successful health/readiness and scheduler-heartbeat requests. No service restart event was observed in the sampled 24-hour container events; the event stream was dominated by health-check execs.
- **Runs/source:** latest run started 2026-09-15T02:00:00.049118Z and completed 2026-09-15T02:00:54.439155Z; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- **Database/migrations:** PostgreSQL read-only connectivity succeeded; Alembic revision is `0015_contradiction_lifecycle`. There are 28 ingestion runs: 2 completed and 26 failed. The current run has 37 completed source runs and 1 failed source run. Counts: 33,797 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Repeated recent database errors are malformed operator diagnostic queries against the authoritative singular schema, not application transaction failures.
- **Resources:** root filesystem is 43% used with 279G available; host memory has 52GiB available of 62GiB; shell FD limit is 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backup:** `/backups/latest.metadata` is present, 198 bytes, mtime 2026-09-14T12:55:23Z; latest artifact is `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes. Backup is present; encrypted restore verification was not run.
- **Certificate/proxy:** recent Caddy logs show successful local certificate renewal and reload for `matrix.scogin.dev` and `hermes.cti.scogin.dev`; no certificate or TLS error was observed. Expiry was not independently decoded.
- **Configuration/deployment:** checked-out `config/sources.json` adds `max_response_bytes: 52428800` for ThreatFox, while the running image/database behavior still rejects responses over 10 MiB. The change is undeployed. Compose config validation was not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not evidence of a production stack failure.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response at the 10 MiB bounded transport limit. Web, proxy, scheduler liveness, database connectivity, migrations, storage, memory, certificates, and backups do not indicate the primary cause. The smallest reversible next step is an explicitly authorized review of the existing 50 MiB bound, focused oversized-response regression tests, and deployment only through `./scripts/update-app.sh`. No recovery or deployment authorization was present, so no mutation was made.

## Rollback/recovery state

Rollback is not applicable. The recovery gate is unlocked, failed run/source records remain preserved, successful-source data remains available, and no production application or data state changed.

## Prevention/follow-up

1. Under explicit maintenance/deployment authorization, assess decompression/memory implications of the 50 MiB bound, run focused regression tests, and deploy only with `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness after any authorized deployment.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Use the authoritative singular schema in future operational queries and separately perform encrypted-backup restore verification.
5. Add source-specific handling and alert context for repeated `oversized_response` failures.
