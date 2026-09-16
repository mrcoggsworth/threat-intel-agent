# Production ingestion incident: ThreatFox bounded-response failure (04:19Z)

## Classification

- **Recorded:** 2026-09-15T09:19:29Z
- **Impact:** ingestion is partially degraded. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` completed 37/38 sources and persisted 13,108 new documents, but the run is failed; no new full-success run exists and analyst/publication outputs remain stale.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream ThreatFox payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, backup mutation, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured Compose fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=5239bbe4-6431-4869-aa7c-8acb692f8e42`
- `observed_at=2026-09-15T09:15:16.327397+00:00`
- `correlation_id=c1453347-21ad-4bcd-926d-dc40a0386cdc`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

A post-check read at `2026-09-15T09:20:16.695127+00:00` still reported `state=actionable_failure` for the same run, with evidence event `0380b981-ddd4-475d-9a88-ff8c5d94f589` and correlation `3c5430c1-4a05-46c7-aa50-204f21e7d4a9`; the recovery lock remained absent.

## Recovery gate

The recovery gate was evaluated with its 1,800-second cooldown and shared lock. It acquired event `4949bbf9-b0a4-479a-b972-ced03b178cdf` at `2026-09-15T09:16:31.115973+00:00`, correlation `e631c7f5-0537-4ef8-a9de-912d4b8c7969`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Because this scheduled request authorizes diagnosis only, the event was completed with outcome `suppressed` at `2026-09-15T09:16:41.991805+00:00`. Read-back verified the lock is absent. No recovery action was attempted.

## Evidence collected

- **Release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; running application image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, application version `0.1.0`. No deployment or stack update was run. The working tree has substantial pre-existing changes and a checked-out but undeployed `config/sources.json` edit adding `max_response_bytes=52428800` for ThreatFox.
- **Ingestion/database:** latest run started `2026-09-15T02:00:00.049118+00`, completed `2026-09-15T02:00:54.439155+00`, status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has classification `oversized_response`, no HTTP status, item count 0, detail `response exceeds 10485760 bytes`. DB configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`, so the checked-out 50 MiB change is not running.
- **Schema/connectivity:** PostgreSQL is accepting connections; Alembic revision is `0015_contradiction_lifecycle`. No pending/failed migration evidence was observed. A prior obsolete-column diagnostic query failed due operational schema drift; authoritative tables/columns are singular and application persistence remains intact.
- **Freshness:** `source_document` 33,797, latest `2026-09-15T02:00:54Z`; `report` 186, `report_version` 201, `publication` 201, `detection` 378, `hunt` 201, `remediation` 201, latest `2026-09-11T22:24:37Z`; `relationship` 11, latest `2026-09-01T08:03:29Z`.
- **Services:** monitor, web, scheduler, backup, and PostgreSQL are running healthy with restart count 0. Worker and runtime-init are exited code 0 by design. Web `/health/live` and `/health/ready` both returned HTTP 200; readiness reported configuration and database `ok`. Scheduler heartbeat was `2026-09-15T09:19:43Z`.
- **Logs/events:** scheduler/monitor continue to report the failed collection and stale successful run. Docker events during the window showed routine health-check/diagnostic execs only; no application restart/crash event was observed.
- **Resources:** root filesystem 43% used with 278G available; host memory 62GiB total, 51GiB available; file-descriptor limit 4096. No exhaustion indication.
- **Backup/certificate/proxy:** `/backups/latest.metadata` identifies `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; no backup mutation or restore was performed. Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy/TLS cause indicated.

## Diagnosis and prevention

The failure is source/provider-specific: the deployed ThreatFox request is rejected by the 10 MiB bounded transport limit while the upstream payload exceeds it. Web, proxy, worker, scheduler, database, disk, certificate, and backup are not indicated as causes. The smallest reversible follow-up, under explicit maintenance/deployment authorization, is to review the existing bounded 50 MiB change for decompression/memory impact, run focused regression tests, and deploy only with `./scripts/update-app.sh`. Then verify the next failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Separately export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables for maintenance cron, and correct operational diagnostics to the current singular schema.

- **Rollback:** not applicable; no application, service, database, migration, configuration, or publication mutation occurred.
- **Security:** no secrets were read into this record or chat; no credentials were rotated.
