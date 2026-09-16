# Production ingestion incident: ThreatFox bounded-response failure (05:17Z)

## Classification

- **Recorded:** 2026-09-15T05:17Z
- **Impact:** ingestion is partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and persisted 13,108 new documents, but failed ThreatFox. Successful-source data remains usable; no full-success run has completed since `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, and reports/publications have not advanced since 2026-09-11T22:24:37Z.
- **Cause confidence:** high for the immediate deployed source-boundary mismatch; low-to-medium for upstream response growth.
- **Data integrity:** preserved. No ingestion retry, service restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read before diagnosis from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`:

- `state=actionable_failure`
- `event_id=73483217-5e84-4679-bcfc-01430a929618`
- `observed_at=2026-09-15T05:15:58.680559+00:00`
- `correlation_id=d883bbb1-3bdb-4f35-af28-141d98547daf`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared recovery gate was consulted with the 1,800-second cooldown and lock. The current event was **suppressed** because the cooldown was active; no recovery action was authorized by this diagnosis-only request. The gate lock was absent after evaluation (`/runtime/recovery.lock` does not exist). The audit recorded the suppression without secrets. Existing gate history shows prior attempted events for the same run were completed with `outcome=suppressed`.

## Evidence collected

- **Repository/release:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; substantial pre-existing working-tree changes remain unexplained and were not modified.
- **Application/image:** `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T12:54:53Z; application package version `0.1.0`.
- **Container state:** web, scheduler, monitor, PostgreSQL, and backup are running and healthy with zero restarts. Worker is exited code 0 by design (`restart: no`). Runtime-init is an old completed one-shot container. No OOM indication. Scheduler heartbeat mtime was 2026-09-15T05:16:41Z; monitor evidence mtime was 2026-09-15T05:16:58Z.
- **Health/readiness:** host-local `/health/live` and `/health/ready` both returned HTTP 200. Web logs show repeated successful health/readiness and scheduler-heartbeat requests.
- **Restart/events:** no service restart was performed. No relevant Docker events appeared in the sampled event window. Scheduler logs show `source collection failed`; monitor logs repeatedly report only stale full-success and failed latest attempt.
- **Runs/source:** latest run started 2026-09-15T02:00:00.049118Z and completed 2026-09-15T02:00:54.439155Z; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- **Database/migrations:** PostgreSQL accepted read-only connectivity queries. Alembic revision is `0015_contradiction_lifecycle`; no pending/failed migration evidence was observed. Authoritative singular tables were queried successfully. Repeated database errors in recent logs are malformed operator diagnostic queries against nonexistent plural tables/columns, not application transaction failures.
- **Downstream:** reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp is 2026-09-11T22:24:37Z; relationship latest is 2026-09-01T08:03:29Z.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total with 52GiB available; shell FD limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backup:** latest artifact `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with `latest.metadata` mtime 2026-09-14T12:55:23Z. Backup is present and monitor-healthy; encrypted restore verification was not run.
- **Certificate/proxy:** no Caddy certificate, renewal, reload, or TLS error was found in the sampled recent Caddy logs. Certificate expiry was not independently decoded by this read-only check.
- **Configuration/deployment:** checked-out `config/sources.json` contains a bounded ThreatFox response change to 50 MiB, while the running image/database behavior still enforces 10 MiB. The change is undeployed. Compose config validation could not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not evidence of a production stack failure. No deployment or stack update was run.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. Web, proxy, scheduler, worker, database, disk, certificate, backup, and migration state do not indicate the primary cause. The smallest reversible next step is an explicitly authorized review of the existing bounded 50 MiB configuration change, focused regression tests, and deployment only through `./scripts/update-app.sh`. No such authorization exists in this request, so no mutation was made.

## Rollback/recovery state

Rollback is not applicable. The recovery gate remains unlocked, the failed run/source records remain preserved, partial successful-source data remains available, and no production state was changed.

## Prevention/follow-up

1. Under explicit maintenance/deployment authorization, assess memory/decompression implications of the 50 MiB bound, run focused oversized-response regression tests, and deploy only through `./scripts/update-app.sh`.
2. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness after any authorized deployment.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` plus protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Use the authoritative singular schema in future operational queries and perform encrypted-backup restore verification separately.
5. Add source-specific handling and alert context for repeated `oversized_response` failures.
