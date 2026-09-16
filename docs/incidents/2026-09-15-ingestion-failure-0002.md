# Production ingestion incident: ThreatFox bounded-response failure (00:02Z)

## Classification

- **Impact:** ingestion remains partially degraded. The latest scheduled run `20c8d81a-48e4-5215-8292-63a72ddac05d` processed 37/38 sources and failed only `threatfox-recent-indicators-abuse-ch`.
- **Monitor state:** `actionable_failure`; recovery was not authorized by this diagnosis-only request.
- **Cause confidence:** high for the immediate cause (deterministic ThreatFox response-size guard); low-to-medium for the upstream reason the payload grew beyond the deployed 10 MiB bound.
- **Data integrity:** no database reset, volume deletion, migration, credential rotation, or evidence deletion performed. The failed source/run records are preserved. Existing partial run data is valid under the repository's failed-run semantics.

## Authoritative monitor evidence

Read before any model work from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`). The latest post-check evidence was:

- `state=actionable_failure`
- `event_id=c3de54fd-3d6d-4bfd-86cf-e2c6375d2db0`
- `observed_at=2026-09-15T00:02:36.170334+00:00`
- `correlation_id=afb6d844-b48f-442d-8509-9799b5fcff67`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Recovery gate

The 30-minute recovery gate and shared lock were evaluated against the authoritative evidence. It acquired the event at `2026-09-15T00:01:33.678994+00` with event ID `8b01aa44-bf9f-4cb9-9f98-25b2808c11b2`, correlation `d76c9ac5-abb7-485e-a1d2-a161149d7a21`, and run `20c8d81a-48e4-5215-8292-63a72ddac05d`. Because this job is diagnosis-only, no recovery action was attempted; the gate was completed with outcome `suppressed`. Read-back verified `recovery.lock` absent. The audit contains the corresponding `attempted` and `completed outcome=suppressed` records.

## Evidence collected

- **Application/deployment:** all CTI containers use `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`; application version reported by the web image is `0.1.0`. Running containers started 2026-09-12 12:55Z; no restarts observed (`restart=0`). Checked-out HEAD is `c925cd5`; repository is `main`, ahead of `origin/main` by 3 commits, with substantial pre-existing working-tree changes. No deployment/config update was run.
- **Database/migrations:** PostgreSQL is accepting connections; database/user are `hermes|hermes`. Alembic revision is `0015_contradiction_lifecycle`. No pending or failed migration was observed from the recorded revision and healthy DB state. The schema uses singular tables (`ingestion_run`, `source_run`); earlier ad-hoc plural-table queries in PostgreSQL logs are operator-query errors, not application failures.
- **Runs/source:** latest run at `2026-09-14T18:32:12.667740+00` failed at `2026-09-14T18:33:07.628491+00`, total 38, successful 37, failed 1, 12,831 new documents. `threatfox-recent-indicators-abuse-ch` has `status=failed`, no HTTP status, `item_count=0`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. Prior full-success run was `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` at 2026-09-11 12:06Z.
- **Services/health:** monitor, web, scheduler, PostgreSQL, and backup containers are healthy/up with zero restarts. `/health/live` and `/health/ready` returned 200/OK from the published web port. The run-status endpoint returned 404 from the unauthenticated host path; monitor evidence reached the internal endpoint with HTTP 200, so this is not treated as a service outage.
- **Logs/events:** monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`. No Docker restart events were observed in the checked window. Scheduler process is running but emitted no useful log output. PostgreSQL logs contain repeated failed ad-hoc diagnostic queries for nonexistent plural tables/columns; no application transaction or constraint failure was identified.
- **Resources:** root filesystem 43% used (279G available), memory 62Gi total/52Gi available, load average 0.54/0.46/0.37, and low container FD counts (monitor 3, web 18, scheduler 7, PostgreSQL 10). No resource exhaustion indication.
- **Backups:** encrypted backup volume contains daily artifacts through `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) plus metadata and `latest.metadata`; no backup failure was observed in the backup container log. Restore verification was not run during diagnosis.
- **Certificate/proxy:** Caddy logs show successful renewal and reload for `hermes.cti.scogin.dev`; external TLS presented a Caddy local certificate valid 2026-09-14 23:39Z through 2026-09-15 11:39Z. No proxy/certificate cause.

## Diagnosis and action

The service stack, database, readiness, resources, backup artifacts, and TLS are healthy. The failure is source/provider-specific: the deployed image enforces a 10 MiB response maximum, while the ThreatFox response exceeded it. The working tree already contains an un-deployed `config/sources.json` change raising ThreatFox's configured maximum to 50 MiB, but it was not applied because this request authorizes diagnosis only and no deployment was performed. No restart, rerun, or source-provider mutation was performed.

## Prevention / follow-up

1. Review and test the bounded ThreatFox response-size change, including memory and decompression limits, before deployment through `./scripts/update-app.sh`.
2. Correct future diagnostic queries to the authoritative singular schema names and avoid noisy PostgreSQL log errors.
3. Add a source-specific monitor classification/runbook link for repeated `oversized_response` failures so the incident is not mistaken for a web/database outage.
4. Run encrypted-backup restore verification separately; this incident only verified artifact presence and metadata freshness.

**Rollback:** not applicable; no application or data mutation was made. Gate audit state was read back and its lock is absent.
