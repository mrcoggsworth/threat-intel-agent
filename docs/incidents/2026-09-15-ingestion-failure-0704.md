# CTI-Hermes production ingestion failure diagnostic (07:04Z)

## Classification

- **Observed:** 2026-09-15T07:03:06Z; diagnostic completed 2026-09-15T07:04:12Z.
- **Impact:** partial ingestion degradation. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` processed 37/38 sources and persisted 13,108 new documents; ThreatFox is stale. Full-success and downstream analyst/publication freshness remain stale.
- **Cause confidence:** high for the deployed source/provider response-size boundary; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation. Evidence at 2026-09-15T07:01:06.204673Z recorded:

- `state=actionable_failure`
- `event_id=67800dc1-1523-4f7e-853c-08c2bd18252d`
- `correlation_id=af20547a-7a88-4667-bd48-d98faf3dbbf9`
- endpoint `http://web:8000/api/v1/ops/run-status`, HTTP 200
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`

The monitor remained actionable at 2026-09-15T07:03:06.349552Z with event `ccdb9041-028c-495a-bbc1-38dd8b638ef0`, endpoint/status unchanged, and the same run ID.

## Recovery gate

The 1,800-second cooldown and `/runtime` lock were evaluated before any recovery action. The gate acquired event `67800dc1-1523-4f7e-853c-08c2bd18252d` at 2026-09-15T07:01:28.439786Z. This diagnosis-only request suppressed recovery. The audit was completed with outcome `suppressed` at 2026-09-15T07:04:12.349729Z, and read-back verified `/runtime/recovery.lock` absent. The monitor refreshed during the bookkeeping window; its refreshed event was also recorded as a suppressed completion without secrets.

## Evidence collected

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; three commits ahead of `origin/main`. Broad pre-existing working-tree changes were not altered.
- **Application/image:** API application version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web/scheduler/monitor started 2026-09-12T12:55Z. Restart count is 0 for web, scheduler, monitor, PostgreSQL, and backup; worker is intentionally exited with code 0 (`restart: no`).
- **Health/readiness:** web liveness HTTP 200; readiness `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`. Web, scheduler, monitor, PostgreSQL, and backup are healthy/running.
- **Ingestion:** latest failed run started 2026-09-15T02:00:00.049118Z and completed 2026-09-15T02:00:54.439155Z; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. The persisted checked-out source configuration allows 52,428,800 bytes, but that change is not deployed.
- **Database/migrations:** PostgreSQL read-only connectivity succeeded. Alembic revision is `0015_contradiction_lifecycle`; no application migration failure or pending-migration evidence was observed. The authoritative schema is singular (`ingestion_run`, `source_run`).
- **Downstream:** prior evidence records reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11; latest report/publication timestamp 2026-09-11T22:24:37Z.
- **Resources:** `/` is 43% used with 279G available; host has 52GiB available memory; open-file limit 4096. No resource exhaustion indication.
- **Backups:** prior verified metadata records `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with metadata present. Backup container is healthy. No restore was attempted.
- **Proxy/certificate:** caddy is running; prior diagnostic evidence recorded successful certificate renewal/reload. No proxy or certificate cause is indicated.
- **Logs/events:** scheduler logs only report `source collection failed`; no service restart was observed. Docker event output contains routine health-check/exec events and no CTI-Hermes restart event in the inspected window.
- **Validation limitation:** Compose config validation was not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not evidence of a production stack failure.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, scheduler liveness, PostgreSQL, disk, memory, file descriptors, migrations, backup, and certificate state do not indicate the cause. The 52 MiB bounded-response configuration is present in the working tree but is undeployed. No service mutation was authorized or performed.

- **Service state:** healthy web/scheduler/monitor/database/backup; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Rollback:** not applicable; no application or data mutation occurred. Gate lock is absent.
- **Smallest reversible follow-up:** review bounded/paginated ThreatFox handling and memory/decompression impact, add/verify mocked oversized-response regression coverage, then deploy only through `./scripts/update-app.sh` under explicit deployment authorization. Verify the next run, source status, full-success/usable-run projections, monitor evidence, and publication freshness.

## Prevention

1. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in maintenance cron while retaining the container fallback.
2. Reconcile operational SQL probes with the deployed singular schema.
3. Add source-specific runbook handling and regression coverage for repeated `oversized_response` failures.
4. Perform encrypted-backup restore verification separately; it was not part of this diagnosis.
