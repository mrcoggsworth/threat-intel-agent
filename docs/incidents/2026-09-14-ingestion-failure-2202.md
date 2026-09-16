# Production ingestion incident: actionable partial-run failure, recovery suppressed (22:02Z)

- **Recorded:** `2026-09-14T22:02:56Z`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files present; this diagnosis added only this incident record.
- **Monitor evidence source:** the cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

## Authoritative monitor evidence

- **State:** `actionable_failure`
- **Event ID:** `7617883f-2579-471f-a3bf-f818fdcb241f`
- **Observed at:** `2026-09-14T22:00:27.536578+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `6b2b6647-87c6-4e6b-ad9d-de0ef09e9fe2`
- **Latest failed run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).

## Diagnosis and impact

The latest ingestion attempt is **failed but usable**: 38 sources were attempted, 37 succeeded, 1 failed, and 12,831 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z` with 38/38 sources and 23,841 new documents; full-success freshness is stale.

The failed source is `threatfox-recent-indicators-abuse-ch`: `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The active image/configuration still uses the 10 MiB response boundary while checked-in `config/sources.json` contains the previously prepared 50 MiB value. This is a deterministic source/provider response-size boundary mismatch.

Public CTI remains available from persisted successful-source and partial-run data. Bounded current counts are: 32,890 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. No evidence of corruption, loss, unauthorized publication mutation, or database integrity damage was observed. ThreatFox coverage and complete-source freshness remain degraded.

**Cause confidence: high.** The evidence points to the ThreatFox provider/source response-size handling, not a web, proxy, worker, scheduler, database, disk, certificate, backup, or credential outage.

## Service and operational evidence

- **Application/image:** application `/version` returned HTTP 200 and `0.1.0`; image `cti-hermes:local`, ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- **Containers:** web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart count 0 and OOM false. Worker is intentionally absent/reserved as a one-shot service. Containers have been up since 2026-09-12 (PostgreSQL since 2026-09-05); no service restart-loop evidence.
- **Health/readiness:** web `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration/database `ok`; `/version` HTTP 200 `{"name":"hermes-cti","version":"0.1.0"}`. Unauthenticated access to the private run-status route returned HTTP 404; monitor's authenticated evidence check returned HTTP 200.
- **Scheduler/monitor:** scheduler heartbeat was current at `2026-09-14T22:02:08Z`; monitor logged the same stale-success/latest-failed condition at one-minute intervals through `22:01:27Z`. No scheduler exception was observed.
- **Database:** `pg_isready -U hermes -d hermes` reported accepting connections; `current_database=hermes`, `current_user=hermes`; Alembic database revision is `0015_contradiction_lifecycle`, matching the image head reported by `alembic heads`. An independent `alembic current` command from the web container could not connect because its default localhost target is not the PostgreSQL service; readiness and the recorded revision show no observed migration blockage.
- **Docker events/restarts:** the two-hour event query showed only health checks and diagnostic `exec_*` events; no container restart, start, die, or OOM event for CTI services.
- **Capacity:** root filesystem 43% used with 279 GiB available; host memory approximately 54 GiB available; host open-file limit 4,096. No resource exhaustion indicated.
- **Backups:** encrypted backup `hermes-20260914T125520Z.dump.enc` exists, 22,608,400 bytes, mode 600; metadata/latest pointer was updated at `2026-09-14T12:55:23Z`. No backup mutation or deletion occurred.
- **Certificate/proxy:** Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate or proxy cause indicated.
- **Last deployment/config boundary:** running CTI containers started 2026-09-12T12:55:15Z–12:55:21Z. Checked-in `config/sources.json` was modified 2026-09-12 19:24:50 -0500 and contains the 50 MiB ThreatFox limit, but no deployment was performed during this diagnosis.

## Recovery gate and actions

The recovery gate was evaluated **before any recovery action** with the configured 1,800-second cooldown and lock:

- **Gate event ID:** `9d29d389-c79b-409d-b34d-52a3c4052b2c`
- **Gate correlation ID:** `f3422dbd-d2fd-49d3-843d-9eb0be3414e3`
- **Gate result:** `suppressed`, reason `recovery cooldown is active`
- **Recorded at:** `2026-09-14T22:02:46.557436+00:00`
- **Lock read-back:** absent (`lock_absent=0`)

No ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data/backup deletion, or publication mutation was performed. Failed ThreatFox evidence, successful partial-run evidence, and gate audit records remain preserved.

## Prevention and rollback

Under explicit recovery/deployment authorization, validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the active image with `config/sources.json`; then run focused tests and `./scripts/update-app.sh`. Verify the next failed-source status, response-size behavior, full-success/usable run status, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback. No rollback is required because no application or data mutation occurred.
