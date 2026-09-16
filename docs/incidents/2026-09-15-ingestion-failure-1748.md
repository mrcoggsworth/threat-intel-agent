# Production CTI ingestion incident: ThreatFox oversized response (17:48Z)

## Classification

- Recorded: 2026-09-15T17:48:37.552925590Z
- Impact: partial collection degradation. The latest scheduled run failed after 37/38 sources and persisted 13,108 new documents. ThreatFox coverage and full-success freshness remain stale; usable partial-source data remains available. Downstream reports/publications have not advanced since 2026-09-11T22:24:37.163555Z.
- Cause confidence: high for the deployed ThreatFox response-size boundary; low-to-medium uncertainty remains about provider payload growth and the safe remediation path.
- Data integrity: preserved. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The scheduled shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured Compose fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis:

- state: `actionable_failure`
- event_id: `ccc9c862-28fe-42c9-b420-bb5be39fd827`
- observed_at: `2026-09-15T17:46:52.867993+00:00`
- correlation_id: `168d7d1e-5031-4d1e-a890-96bcd2c2402a`
- endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- latest attempt run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, state `actionable_failure`, detail `1 source(s) failed`
- full-success run_id: `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`

## Recovery gate

The shared 1,800-second cooldown and `/runtime` lock were evaluated before any recovery action. The gate recorded a secret-free suppression:

- event_id: `ccc9c862-28fe-42c9-b420-bb5be39fd827`
- correlation_id: `168d7d1e-5031-4d1e-a890-96bcd2c2402a`
- run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- decision: `allowed=false`, reason `recovery cooldown is active`
- read-back: `/runtime/recovery.lock` absent

No recovery was authorized or attempted. The latest audit read-back shows the suppression event recorded at `2026-09-15T17:47:20.386796+00:00`.

## Evidence collected

- Repository/release: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and left untouched.
- Application/image: version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`.
- Containers: web, scheduler, monitor, PostgreSQL, backup, and Caddy are running; CTI restart count 0 and OOM false; worker is exited code 0 by design. Caddy restart count 0. Docker event review showed health-check/diagnostic exec activity and no application restart/start/die evidence.
- Health/readiness: published web port `127.0.0.1:18000` returned `/health/live` HTTP 200 `{"status":"ok"}`, `/health/ready` HTTP 200 with configuration/database `ok`, and `/version` HTTP 200 version `0.1.0`.
- Database/migrations: PostgreSQL `16.14` accepted connections; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence observed. One diagnostic query used an invalid `source_run` column name and was corrected; this is a probe error, not an application failure.
- Ingestion: run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, status `failed`, started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, `cache_state=miss`, classification `oversized_response`, detail `response exceeds 10485760 bytes`. The preceding two runs also failed one source.
- Persistence/downstream: `source_document` 33,797 (latest retrieval `2026-09-15T02:00:54.267448Z`); report 186, report_version 201, publication 201, detection 378, hunt 201, remediation 201, relationship 11. Latest downstream timestamp is `2026-09-11T22:24:37.163555Z`.
- Resources: root filesystem 43% used with 278G available; 62GiB memory with 49GiB available; load average `0.39/0.44/0.47`; host open-file limit 4096. No OOM/resource exhaustion indication.
- Scheduler/monitor: scheduler process remains running; monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`. Monitor evidence was current at observation time.
- Backup: backup container healthy; latest metadata identifies `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore verification was not run.
- Certificate/proxy: Caddy is running without restarts; active project includes Caddy. No certificate/proxy evidence explains ingestion. Certificate trust/lifetime remains a separate follow-up.
- Configuration/deployment: Compose validation was not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation. No update script or deployment was run.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, scheduler, worker, PostgreSQL, disk, memory, migration, backup, and certificate evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was correctly suppressed by the recovery gate.

- Service state: internally serving and healthy; one-source collection freshness degraded; full-success and downstream publication freshness stale.
- Action: diagnosis only; recovery suppression recorded. No stack mutation.
- Rollback: not applicable; no application or data mutation occurred.

## Prevention and follow-up

1. Under explicit maintenance/deployment authorization, validate a bounded or paginated ThreatFox request, or staged response-limit change, against an offline oversized-response fixture; assess decompression/memory impact and retain regression coverage.
2. Run focused tests and deploy only through `./scripts/update-app.sh`; verify source status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema.
5. Perform encrypted-backup restore verification and certificate/proxy trust review separately.
