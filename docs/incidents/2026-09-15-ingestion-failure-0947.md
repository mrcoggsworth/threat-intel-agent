# CTI-Hermes production ingestion failure diagnostic (09:47Z)

## Classification

- Recorded: 2026-09-15T09:47:23Z
- Impact: partial collection degradation. Latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox freshness, full-success freshness, analyst freshness, and publication freshness remain stale.
- Cause confidence: high for the deployed ThreatFox response-size boundary; low-to-medium for upstream payload growth.
- Data integrity: preserved. Failed-source and successful-source records remain persisted. No ingestion retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis:

- state: `actionable_failure`
- event_id: `1ef2b4b2-4e20-484a-aa6e-63ba5dc1b02b`
- observed_at: `2026-09-15T09:46:18.607345+00:00`
- correlation_id: `675549ad-f852-450a-894d-832cb7274d01`
- endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- latest attempt run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, state `actionable_failure`, detail `1 source(s) failed`
- full-success run_id: `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`

## Recovery gate

The shared 1,800-second cooldown and lock were evaluated before any recovery action. The gate acquired the monitor event at `2026-09-15T09:46:47.664478+00Z`; because this scheduled request authorizes diagnosis only, it was completed with outcome `suppressed` at `2026-09-15T09:47:03.991190+00Z`. Read-back verified the attempted and completed audit records and `/runtime/recovery.lock` absent. No recovery was attempted.

## Evidence collected

- Repository/release: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree changes, deletions, and untracked files were observed and not modified except for this incident record.
- Application/image: version `0.1.0`; running application image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; Hermes services started 2026-09-12; PostgreSQL started 2026-09-05.
- Containers/restarts: web, scheduler, monitor, PostgreSQL, backup, and proxy are up; Hermes containers healthy; restart count 0 and OOM false. No relevant non-health-check restart/start/die event was observed in the two-hour window. Scheduler heartbeat was fresh at `2026-09-15T09:47:13Z`; monitor evidence refreshed at `2026-09-15T09:47:18Z`.
- Health/readiness: `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration and database `ok`; `/version` HTTP 200 with version `0.1.0`.
- Database/migrations: PostgreSQL accepted connections; Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence was observed. The older plural-table operational probes are schema-drifted; authoritative singular tables queried successfully.
- Ingestion: run status `failed`, started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- Downstream: persisted totals are report 186, report_version 201, publication 201, detection 378, hunt 201, remediation 201, relationship 11. Latest report and publication timestamp is `2026-09-11T22:24:37.163555Z`.
- Resources: root filesystem 43% used with 278G available; host memory 51GiB available; load average not elevated in collected host snapshot; open-file limit 4096. No disk, memory, or descriptor exhaustion indication.
- Backup: backup container healthy; latest metadata identifies `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Restore verification was not run.
- Certificate/proxy: Caddy is up without a restart; its local certificate storage is present. No proxy or certificate failure was indicated by local health checks. Tailnet certificate expiry was not independently verified because the configured host certificate path is absent on this checkout host.
- Configuration/deployment: checked-in `config/sources.json` declares ThreatFox `max_response_bytes=52428800`, while the running failure proves the deployed boundary remains 10 MiB. Compose config validation was not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production failure evidence.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, scheduler, worker, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was not attempted.

- Service state: web/scheduler/monitor/database/backup/proxy healthy; one-source collection freshness degraded; full-success and downstream publication freshness stale.
- Action: diagnosis only; recovery gate bookkeeping completed as suppressed. No stack mutation.
- Rollback: not applicable; no application or data mutation was made.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review ThreatFox provider-side filtering/pagination or the bounded 50 MiB configuration, including decompression and memory impact; retain oversized-response regression coverage.
2. Run focused tests, then deploy only through `./scripts/update-app.sh`; verify ThreatFox status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema to eliminate misleading PostgreSQL errors.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
