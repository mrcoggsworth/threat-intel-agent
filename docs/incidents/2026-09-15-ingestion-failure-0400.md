# Production ingestion incident: ThreatFox bounded-response failure (04:00Z)

## Classification

- **Recorded:** 2026-09-15T04:00:55Z
- **Impact:** ingestion remains partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and failed only `threatfox-recent-indicators-abuse-ch`; 13,108 documents were persisted from successful sources. No full-success run has completed since `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`.
- **Cause confidence:** high for the immediate deployed source-boundary cause; low-to-medium for the upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before recovery-gate evaluation:

- `state=actionable_failure`
- `event_id=716e13f4-6293-4f3b-827b-c2b96e12e4ad`
- `observed_at=2026-09-15T04:00:53.356756+00:00`
- `correlation_id=0cc2ecd4-52f6-4d31-8c76-5b99eed96343`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared recovery gate was evaluated with its 1,800-second cooldown and lock before any recovery action. Decision: `allowed=false`, reason `recovery cooldown is active`, for event `716e13f4-6293-4f3b-827b-c2b96e12e4ad`. No recovery was attempted; no lock was acquired or left behind. The audit therefore records this run as suppressed; the prior gate cycle contains the corresponding attempted/completed `outcome=suppressed` records. Diagnosis-only authorization does not permit rerun, restart, or deployment.

## Evidence collected

- **Repository/release:** repository `git@github.com:mrcoggsworth/threat-intel-agent.git`, branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76` (`c925cd5`), three commits ahead of `origin/main`; substantial pre-existing working-tree changes are present. No deployment or stack update was run.
- **Application/image:** running CTI services use `cti-hermes:local`, image `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:54:53Z; application version `0.1.0`. Web, scheduler, monitor, and PostgreSQL are running/healthy with restart count 0. Worker is exited code 0 with message that it is reserved for a later analysis phase; runtime-init is exited code 0 after initialization, both configured one-shot behavior.
- **Health/readiness:** internal web liveness and readiness returned HTTP 200; internal run-status endpoint returned HTTP 404 without the required protected request context. Monitor evidence itself obtained run-status HTTP 200, so this is not treated as a web outage. Scheduler heartbeat was fresh at collection time.
- **Runs/source:** latest run started 2026-09-15T02:00:00.049118Z and completed 2026-09-15T02:00:54.439155Z; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed ThreatFox source has `item_count=0`, no HTTP status, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- **Database/migrations:** PostgreSQL `hermes|hermes` accepted connections; Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration evidence. Authoritative singular tables are present. Repeated plural-table/column errors in PostgreSQL logs are operator diagnostic query errors, not application transaction failures.
- **Downstream:** reports 186, report versions 201, publications 201, detections 378, hunts 201, remediations 201, relationships 11. Latest report/publication timestamp is 2026-09-11T22:24:37.163555Z; downstream publication is stale relative to the failed ingestion.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total with 52GiB available; shell FD limit 4096 and container limits observed at 1024. Container stats showed no resource pressure. No OOM indication.
- **Logs/events:** scheduler logged `source collection failed`; monitor repeatedly logged stale full-success/latest failed attempt. No service restart events were observed in the 24-hour Docker event window. PostgreSQL checkpoint activity was normal; query errors were diagnostic drift.
- **Backup:** latest encrypted artifact `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with `/backups/latest.metadata` and SHA-256 metadata present. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no proxy or certificate cause.
- **Configuration/deployment:** checked-out `config/sources.json` already contains an undeployed `max_response_bytes=52428800` ThreatFox change. Running configuration still enforces 10 MiB (`10485760`). Compose validation could not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production evidence of stack failure.

## Diagnosis, action, and rollback

The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. Web, proxy, worker, scheduler, database, disk, certificate, backup, and migration state do not indicate the cause. No state-changing action was authorized or performed.

**Rollback:** not applicable. Existing failed run/source records and successful-source partial data remain preserved; recovery-gate lock state was verified not acquired.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review the bounded 50 MiB change for memory/decompression implications, run focused regression tests, and deploy only through `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness after authorized deployment.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Correct operational queries to the singular schema and perform encrypted-backup restore verification separately.
5. Add source-specific classification/runbook handling for repeated `oversized_response` failures.
