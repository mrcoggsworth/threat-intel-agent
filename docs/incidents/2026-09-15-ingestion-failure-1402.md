# Production CTI ingestion incident: ThreatFox oversized response (14:02Z)

## Classification

- Recorded: 2026-09-15T14:02:37Z
- Impact: partial collection degradation. The latest run failed after 37/38 sources and persisted 13,108 new documents. ThreatFox coverage and full-success freshness remain stale; usable partial-source data remains available. Reports, report versions, publications, detections, hunts, and remediation have not advanced since 2026-09-11T22:24:37.163555Z.
- Cause confidence: high for a deployed ThreatFox response-size boundary mismatch; low-to-medium uncertainty remains about provider payload growth and whether the staged configuration is safe to deploy.
- Data integrity: preserved. Failed-source and successful-source records remain persisted. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`. The configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis:

- state: `actionable_failure`
- event_id: `719000c0-d686-4b9e-a1cd-3c140aef5b8a`
- observed_at: `2026-09-15T14:00:36.864311+00:00`
- correlation_id: `a062b476-5278-416f-b05f-8831db7f033d`
- endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- latest attempt run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, state `actionable_failure`, detail `1 source(s) failed`
- full-success run_id: `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`

The authenticated private run-status projection returned HTTP 200: latest attempt status `failed` (37/38 sources), latest full-success status `completed` (38/38, scheduled 2026-09-11T02:00:00Z), and latest usable status `failed` for run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` with limitations `1 source(s) failed` and `source coverage is partial`.

Post-diagnosis monitor read-back at `2026-09-15T14:02:37.012485+00:00` remained `actionable_failure`, event_id `faa4668e-b550-4f2c-8a64-b3f1fa5541b2`, correlation_id `160b1cf4-a5ef-4d05-a961-2f2298d12590`, with the same latest and full-success run IDs.

## Recovery gate

The shared 1,800-second cooldown and `/runtime` lock were evaluated before any recovery action. The gate recorded a secret-free suppressed event:

- gate event_id: `8caaaa14-6aa1-4fe5-ad33-af04085a0243`
- gate correlation_id: `c6e1ce33-8ac0-4c25-9d45-44fb96fd4bcd`
- run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- decision: `allowed=false`, reason `recovery cooldown is active`
- recorded_at: `2026-09-15T14:01:41.230389+00:00`
- read-back: `/runtime/recovery.lock` absent; the prior gate state remains recorded; no recovery was attempted.

## Evidence collected

- Repository/release: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree modifications, deletions, and untracked files were observed and left untouched except for this incident record.
- Application: `/version` returned HTTP 200, version `0.1.0`. Running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created 2026-09-12T07:54:53-05:00.
- Containers: web, scheduler, monitor, PostgreSQL, and backup are running and healthy with restart count 0 and OOM false. Worker is exited 0 by design (`restart: "no"`). The monitor, web, scheduler, and backup started 2026-09-12; PostgreSQL started 2026-09-05. No production container restart/start/die event was observed in the two-hour window; observed Docker events were health-check/diagnostic execs only. No proxy container exists in the active Compose project listing.
- Health/readiness: web `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration and database `ok`; `/version` HTTP 200.
- Database/migrations: PostgreSQL 16.14 accepted connections; Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence was found. Earlier plural-table probes logged expected schema-drift errors (`ingestion_runs`, `source_status`) and one diagnostic used a nonexistent column; authoritative singular tables queried successfully. These are diagnostic probe issues, not production database failure evidence.
- Ingestion: run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, status `failed`, started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. The latest three runs all remain terminal `failed` with one failed source.
- Persistence/downstream: `source_document` 33,797 (latest retrieval `2026-09-15T02:00:54.267448Z`); report 186, report_version 201, publication 201, detection 378, hunt 201, remediation 201, relationship 11. Latest downstream timestamp is `2026-09-11T22:24:37.163555Z`.
- Resources: root filesystem 43% used, 279G available; 62GiB memory with 49GiB available; load average 0.43/0.46/0.43; open-file limit 4096. Docker reports no resource exhaustion indication.
- Backup: backup container healthy; `/backups/latest.metadata` identifies `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore verification was not run.
- Certificate/proxy: `hermes.cti.scogin.dev:443` presented a Caddy Local Authority ECC Intermediate certificate, valid 2026-09-15T07:39:23Z through 19:39:23Z. No proxy/certificate failure explains ingestion; trust and short certificate lifetime remain separate operational follow-up. The active Compose project has no proxy container.
- Configuration/deployment: Compose validation could not run because the cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation. Running image remains the older local image while the checked-out tree contains broad pre-existing changes. No deployment or update script was run.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, scheduler, worker, PostgreSQL, disk, memory, migration, backup, and certificate evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was correctly suppressed by the recovery gate.

- Service state: web/scheduler/monitor/database/backup healthy; one-source collection freshness degraded; full-success and downstream publication freshness stale.
- Action: diagnosis only; recovery gate suppression recorded. No stack mutation.
- Rollback: not applicable; no application or data mutation occurred.

## Prevention and follow-up

1. Under explicit maintenance/deployment authorization, validate a bounded or paginated ThreatFox request, or the staged larger response limit, against an offline oversized-response fixture; assess decompression/memory impact and retain regression coverage.
2. Run focused tests and deploy only through `./scripts/update-app.sh`; verify persisted source configuration, failed-source classification, full-success/usable-run status, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the maintenance cron environment while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema to eliminate misleading errors.
5. Investigate the absent active proxy container, certificate trust/lifetime, and perform encrypted-backup restore verification separately.
