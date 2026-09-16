# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T06:01:01.874098+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `424b0e91-757e-4e65-a36d-078b83aa05e5`
- **Correlation ID:** `1b217de4-7d1e-41fc-a1db-815eee43ae32`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data` signal)
- **Diagnosis time:** 2026-09-15T06:01:53+00:00
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present; this record was added without modifying those changes.
- **Application/image:** running containers use `cti-hermes:local`, created 2026-09-12T12:55:03Z; the image ID was not changed by this diagnosis.

## Impact

The 2026-09-15T02:00Z scheduled collection failed after 37 of 38 sources. The successful source results and failed source record remain persisted, but the ThreatFox/Abuse.ch source is not fresh. Database evidence shows 28 ingestion runs, with the latest run completed at 2026-09-15T02:00:54.439155+00 and reporting 38 total, 37 successful, 1 failed, `1 source(s) failed`. There are 33,797 source documents (latest retrieved 2026-09-15T02:00:54.267448+00), 186 reports, 201 report versions, and 201 publications; report/report-version/publication freshness is 2026-09-11T22:24:37.163555+00.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; classification `oversized_response`; detail `response exceeds 10485760 bytes`; HTTP status was unavailable.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running healthy with restart count 0 and OOM false. The scheduler heartbeat was present and current at 2026-09-15T06:02:11Z. Scheduler logs contain the source-collection failure; monitor logs repeatedly report stale successful data and failed latest attempt.
- PostgreSQL accepts connections (`pg_isready`), database size is 195 MB, and Alembic reports revision `0015_contradiction_lifecycle`. The failed run and source-run record are present, preserving failure evidence. A direct `alembic current` in the web container could not connect to localhost PostgreSQL, while the database container itself was accepting connections; this is a container-local endpoint/configuration limitation, not evidence of database unavailability to the deployed services.
- Host capacity is not limiting: root filesystem is 43% used with 279G available, 52 GiB available memory, and open-file limit 4096.
- Latest backup metadata: `/backups/hermes-20260914T125520Z.dump.enc`, completed 2026-09-14T12:55:23Z, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; backup container is healthy. No restore was attempted.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no certificate renewal error was observed. Certificate trust distribution remains a separate ingress concern and was not changed.
- Compose inspection was partially blocked because this cron environment does not export the protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables. Direct container inspection was used instead; no secrets were read or printed.

**Cause confidence: high.** This is a recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary, not a web, proxy, worker, scheduler liveness, PostgreSQL availability, disk, memory, migration, backup, or certificate-renewal failure.

## Recovery gate and actions

The authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis. The shared recovery gate was evaluated with its 1,800-second cooldown and lock. It returned `allowed=false`, reason `recovery cooldown is active`, and recorded suppressed event `424b0e91-757e-4e65-a36d-078b83aa05e5` at 2026-09-15T06:01:36.853779+00. Read-back verified `/runtime/recovery.lock` is absent.

No restart, retry, deployment, migration, credential change, or destructive recovery was performed. No application or production data was mutated.

## Service, integrity, rollback, and prevention

- **Service state:** web/monitor/scheduler/database/backup containers healthy; internal liveness/readiness checks are operating; collection freshness is degraded for one source; full-success and analyst/publication freshness remain stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded; no volumes, backups, or migration history were changed.
- **Rollback:** not applicable; no deployment or repair was made.
- **Prevention:** deploy the pre-existing bounded ThreatFox response-size configuration only through the normal `./scripts/update-app.sh` workflow after validation, or implement a paginated request; retain `oversized_response` classification and add a mocked oversized-response regression test. Do not retry until the recovery gate permits it. Separately correct cron environment propagation for protected Compose variables and investigate the direct web API route mismatch without treating it as ingestion recovery authorization.
