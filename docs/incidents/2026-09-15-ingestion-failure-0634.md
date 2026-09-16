# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T06:31:04.038698+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `fba94f34-c0db-4d85-bd18-623654edfff0`
- **Correlation ID:** `04e76ad6-6cd5-4441-902a-f14da6d0aa38`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data`)
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files; this incident record was added without modifying those changes.
- **Application/version/image:** API reports `hermes-cti` `0.1.0`; running image `cti-hermes:local`, containers started 2026-09-12T12:55Z; no restart or image change occurred during diagnosis.
- **Migration revision:** `0015_contradiction_lifecycle`

## Impact

The 2026-09-15T02:00Z scheduled collection failed after 37 of 38 sources. The 37 successful source results and the failed-source record remain persisted; the ThreatFox/Abuse.ch source is not fresh. The latest run completed at `2026-09-15T02:00:54.439155+00` with 38 total sources, 37 successful, 1 failed, and 13,108 new documents. Full-success freshness and the usable full-success projection remain stale. Reports, report versions, and publications were last created at `2026-09-11T22:24:37.163555+00`.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; classification `oversized_response`; detail `response exceeds 10485760 bytes`; no HTTP status was recorded.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running healthy with restart count 0; PostgreSQL accepts connections. The scheduler heartbeat was current at collection time. Monitor logs repeatedly report `last successful run stale, latest ingestion attempt failed`.
- Host capacity is not limiting: root filesystem 43% used with 279G available, 52 GiB available memory, and open-file limit 4096.
- Latest backup metadata: `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; backup container is healthy. No restore was attempted.
- Caddy logs show successful local certificate renewal and reload for `matrix.scogin.dev`; no certificate renewal error was observed. Certificate trust distribution remains a separate ingress concern.
- Compose config validation was blocked in this cron shell because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables are not exported. Direct container inspection and health checks were used; no secrets were read or printed.
- Several historical diagnostic SQL probes referenced obsolete table/column names (`ingestion_runs`, `s.id`, `display_name`), producing PostgreSQL errors. The deployed schema is intact (`ingestion_run`, `source_run`, `source_id`); this is operational query/schema drift, not evidence of database unavailability or migration failure.

**Cause confidence: high.** This is a recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary, not a web, proxy, scheduler liveness, PostgreSQL availability, disk, memory, migration, backup, certificate-renewal, or container restart failure.

## Recovery gate and actions

The authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis. The 1,800-second cooldown and shared lock were evaluated. Cooldown had elapsed since the prior attempt at `2026-09-15T05:31:38.934542+00`, the gate lock was acquired, and the following secret-free bookkeeping was recorded:

- attempted event `fba94f34-c0db-4d85-bd18-623654edfff0` at `2026-09-15T06:34:12.944724067Z`
- completed outcome `suppressed` at `2026-09-15T06:34:12.945869536Z`, reason `diagnosis-only request; recovery not authorized`
- read-back verified `/runtime/recovery.lock` absent and both audit records present

No restart, retry, deployment, migration, credential change, source-limit change, or destructive recovery was performed.

## Service, integrity, rollback, and prevention

- **Service state:** web/scheduler/monitor/database/backup healthy; liveness/readiness checks are operating; collection freshness is degraded for one source; full-success and analyst/publication freshness remain stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded; no volumes, backups, or migration history were changed.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible follow-up:** validate a bounded/paginated ThreatFox request or the pre-existing bounded response-size configuration with mocked oversized-response regression coverage, then deploy only through `./scripts/update-app.sh` under explicit recovery/deployment authorization. Verify the next failed-source status, full-success/usable-run projections, monitor evidence, and publication freshness.
- Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, protected Compose variables, and the operational SQL schema drift. Do not treat these follow-ups as ingestion recovery authorization.
