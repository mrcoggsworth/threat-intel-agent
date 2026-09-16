# Production ingestion incident: ThreatFox bounded-response failure (01:47Z)

## Classification

- **Impact:** ingestion is partially degraded. Run `20c8d81a-48e4-5215-8292-63a72ddac05d` processed 37/38 sources; `threatfox-recent-indicators-abuse-ch` failed. The latest full-success run remains stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`). The latest run is usable only with its explicit partial-coverage limitation.
- **Cause confidence:** high for the immediate cause (the deployed 10 MiB response guard); medium for upstream ThreatFox payload growth.
- **Data integrity:** no recovery, restart, deployment, migration, database reset, volume/data/backup deletion, credential rotation, or evidence deletion was performed. Failed run/source records remain preserved.

## Authoritative monitor evidence

Read first from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`:

- `state=actionable_failure`
- `event_id=91be3fff-f92a-4bfc-991e-4f53170cf010`
- `observed_at=2026-09-15T01:45:43.529176+00:00`
- `correlation_id=8073b6d7-58bd-4894-9c78-091172624232`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Recovery gate

The shared recovery gate was evaluated before any recovery action with its 1,800-second cooldown and lock. It acquired gate event `91be3fff-f92a-4bfc-991e-4f53170cf010` and recorded an attempted event, then this diagnosis-only request completed it as **suppressed** because recovery was not authorized. The associated correlation ID is `8073b6d7-58bd-4894-9c78-091172624232` and run ID is `20c8d81a-48e4-5215-8292-63a72ddac05d`. Read-back verified `/runtime/recovery.lock` is absent.

## Post-diagnosis monitor verification

At `2026-09-15T01:48:43.747722+00`, the latest evidence remained `state=actionable_failure` with event ID `2c9dfd0c-1f52-42f9-b978-3ad5c1200e4f`, correlation ID `8a219661-6a47-4232-98a5-4cbe89fd45a7`, endpoint `http://web:8000/api/v1/ops/run-status`, HTTP status `200`, and run ID `20c8d81a-48e4-5215-8292-63a72ddac05d`. The full-success signal remained `stale_data`; the latest-attempt signal remained `actionable_failure` with `1 source(s) failed`.

## Evidence collected

- **Repository/release:** remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch `main`; HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch is ahead of `origin/main` by 3 commits. Working tree has substantial pre-existing changes, including an uncommitted `config/sources.json` edit and unrelated scratch/incident files. No reset or cleanup was performed.
- **Running application:** CTI web, scheduler, and monitor use image `cti-hermes:local`, image ID `9e8d0a379cc5c4686e4b4069aa478e60d8ba2f8f8fb99561c0e9dde5ed265305`, created `2026-09-12T12:55:03.601753337Z`; application version `/version` is `0.1.0`. Web, scheduler, and monitor started 2026-09-12 12:55Z with restart count 0. PostgreSQL started 2026-09-05 with restart count 0. Backup started 2026-09-12 with restart count 0. Worker exited code 0 at startup by design/reserved status; it is not the ingestion owner.
- **Health/readiness:** published web port `127.0.0.1:18000` returned `/health/live` HTTP 200 `{"status":"ok"}`, `/health/ready` HTTP 200 with configuration/database `ok`, and `/version` HTTP 200. No web or proxy outage was observed.
- **Scheduler/monitor:** scheduler heartbeat was present and updating at `2026-09-15 01:47:10Z`; monitor and scheduler are healthy/up. Monitor logs repeatedly report only stale full-success/latest-attempt failure. No CTI container restart events were observed in the last 12 hours.
- **Database/migrations:** PostgreSQL `pg_isready` reports accepting connections. `alembic_version` is `0015_contradiction_lifecycle`, matching the repository Alembic head; no pending or failed migration was identified. Latest run started `2026-09-14T18:32:12.667740+00`, completed `2026-09-14T18:33:07.628491+00`, status `failed`, total 38, successful 37, failed 1, new documents 12,831, application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`, error summary `1 source(s) failed`. The failed source has `item_count=0`, no HTTP status, `error_classification=oversized_response`, and `response exceeds 10485760 bytes`.
- **Data/publication state:** database contains 39 sources, 32,890 source documents, 552 raw artifacts, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Latest report/publication timestamps are `2026-09-11T22:24:37.163555+00`; no evidence of destructive loss.
- **Resources:** root filesystem 43% used with 279G available; host memory 62Gi total with 52Gi available; swap nearly unused; host fd limit 4096. CTI memory was web 281.7MiB, scheduler 361.5MiB, monitor 29.9MiB, PostgreSQL 257.4MiB, backup 3.3MiB. No disk, memory, file-descriptor, or OOM signal.
- **Logs/events:** PostgreSQL logs contain repeated failed ad-hoc diagnostic queries using plural table names or incorrect columns (for example `ingestion_runs`, `source_key`, `scheduled_at`, and `configuration`). These are operator-query errors, not application transaction failures, but add diagnostic noise. PostgreSQL also shows long checkpoints; no application failure or restart was linked to them.
- **Backups:** encrypted backup artifacts and metadata are present through `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) with `latest.metadata` at `2026-09-14T12:55:23Z`. Restore verification was not run.
- **Certificate/proxy:** Caddy has been up 4 days. Its logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; the inspected certificate is valid through `2026-11-16T14:30:36Z`. No certificate or proxy cause.
- **Configuration/deployment:** the checked-in uncommitted source edit adds `max_response_bytes: 52428800` for ThreatFox, but the running database/source configuration history and failed run still use `10485760` and the prior configuration hash. No `./scripts/update-app.sh` run occurred, so the staged change is not deployed. Compose inspection from the cron shell could not run because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables were not exported; direct Docker inspection was used without exposing secrets.

## Diagnosis and action

This is a source/provider-specific ingestion failure, not a web, proxy, scheduler, database, disk, memory, certificate, or backup outage. ThreatFox's response exceeded the deployed 10 MiB bounded-response limit. The smallest reversible repair is to review and test the existing 50 MiB source-bound change, including memory/decompression behavior, then deploy only under explicit maintenance/deployment authorization via `./scripts/update-app.sh`. No source rerun, restart, or deployment was performed.

## Prevention and follow-up

1. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the recovery cron while retaining the container fallback.
2. Add/retain a bounded ThreatFox fixture/regression test and verify memory/decompression limits before deployment.
3. After explicit authorization, deploy with `./scripts/update-app.sh`; verify the next run, failed-source classification, full-success/usable-run projections, monitor evidence, and report/publication freshness.
4. Correct operational queries to the singular schema and current columns to stop PostgreSQL diagnostic log noise.
5. Run encrypted-backup restore verification separately.
6. Track the exited worker as a separate maintenance item; do not conflate it with this source-specific incident.

**Rollback:** not applicable; no application or data mutation was made. Recovery gate lock is absent and evidence/audit records are preserved.
