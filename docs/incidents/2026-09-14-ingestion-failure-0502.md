# Production ingestion incident: diagnosis-only recovery suppression (05:02Z)

- **Recorded:** 2026-09-14T05:02:05.894221Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Application/image:** `0.1.0`, `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Monitor state:** `actionable_failure`
- **Monitor event ID:** `260766f1-b644-42d4-842a-a013ebbdce1a`
- **Observed at:** `2026-09-14T05:00:13.220464+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `160c9ec3-a3f6-41de-8a9c-ba7336549161`
- **Latest failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`

## Impact and cause

The 2026-09-14 02:00Z collection is failed but usable: 37 of 38 sources
succeeded, 1 failed, and 1,564 new documents were persisted. The latest
full-success run is stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
`2026-09-11T12:06:50.050468Z`). Public CTI remains available from persisted
successful-source and partial-run data, but complete source coverage and
full-success freshness are degraded. Reports and publications remain stale;
latest timestamps are `2026-09-11T22:24:37.163555Z` and
`2026-09-11T22:24:37.183379Z` respectively.

The failed source is `threatfox-recent-indicators-abuse-ch`. PostgreSQL records
`status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`,
`cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. Cause confidence is **high**:
this is a deterministic provider/source response-size boundary mismatch, not a
web, proxy, worker, scheduler, database, disk, certificate, backup, migration,
publication, or credential outage. Checked-in `config/sources.json` has
`max_response_bytes=52428800`, while the running image still enforces the
10 MiB boundary. The configuration change is un-deployed; no configuration or
application mutation was made by this job.

## Evidence and operational state

- Latest run started `2026-09-14T02:00:00.095941Z`, completed
  `2026-09-14T02:00:06.398193Z`, status `failed`, 38 total / 37 successful /
  1 failed, application `0.1.0`, configuration hash
  `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Direct PostgreSQL checks: accepting connections; `current_database=hermes`,
  `current_user=hermes`; Alembic revision `0015_contradiction_lifecycle`.
  No pending/failed migration evidence was observed. Read-only counts are
  31,678 source documents, 186 reports, 201 publications.
- Web liveness and readiness returned HTTP 200 at 05:02:59Z. Web, monitor,
  scheduler, PostgreSQL, and backup are running and healthy with restart count
  0. The worker is an intentional one-shot container, exited 0, and is not
  OOM-killed or restart-looping.
- Monitor evidence and scheduler heartbeat continued refreshing. Heartbeat
  mtime was `2026-09-14T05:02:01Z`; monitor logs repeatedly reported only
  `last successful run stale, latest ingestion attempt failed`. No scheduler
  error log was emitted.
- Docker events for the observation window showed diagnostic `exec_*` events
  only; no service restart or OOM event was observed.
- Host root/runtime/backups filesystem is 43% used with 280 GiB available;
  memory available is 52 GiB; shell open-file limit is 4096 (container limit
  1024). No resource exhaustion is indicated.
- Encrypted backup metadata is present, mode 600, updated
  `2026-09-13T12:55:20Z`; newest artifact is
  `hermes-20260913T125518Z.dump.enc`, size 22,110,800 bytes. No backup
  mutation occurred.
- Caddy logs show successful local certificate renewals and reloads. Current
  logged expirations are `2026-09-14T11:39:24Z` for
  `hermes.cti.scogin.dev` and `2026-09-14T13:29:24Z` for
  `matrix.scogin.dev`; certificate state is not the ingestion cause.
- Compose config validation from this shell remains blocked because protected
  `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is an operator
  shell limitation; direct running-container evidence was used. The working
  tree contains pre-existing unrelated changes and deletions; none were
  altered except this incident record.

## Recovery gate and action

The authoritative machine-readable evidence was read from
`/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` (the cron shell
has no exported `HERMES_MONITOR_EVIDENCE_FILE`). The recovery gate evaluated the
required actionable evidence with the configured 1,800-second cooldown and lock.
Cooldown had elapsed, so it recorded attempted event
`286995ca-cbce-465b-bdce-649c9b9e173f` at `2026-09-14T05:01:49.261977+00:00`.
Because this request authorizes diagnosis but not recovery, the event was
completed with `outcome=suppressed` at `2026-09-14T05:02:05.894221+00:00`.
The recovery lock was read back as absent.

No ingestion retry, service restart, deployment via `scripts/update-app.sh`,
migration, credential change, response-limit change, volume/data deletion,
backup deletion, or publication mutation was performed. Failed ThreatFox
evidence and successful partial-run evidence remain persisted; no rollback is
required.

## Prevention and follow-up

Validate provider-side filtering/pagination or an alternate ThreatFox endpoint
against an offline fixture before deploying the checked-in 50 MiB limit. Retain
an oversized-response regression fixture, reconcile the running image with
`config/sources.json`, and deploy only through `./scripts/update-app.sh` after
explicit recovery/deployment authorization. Verify the next run's source
status, response-size handling, monitor evidence, and publication/data
integrity. Reconcile the missing operator `HERMES_SECRET_DIR`/`HERMES_IMAGE`
environment before compose-based maintenance and re-check certificate expiry
using proxy renewal tooling before the certificate boundary.
