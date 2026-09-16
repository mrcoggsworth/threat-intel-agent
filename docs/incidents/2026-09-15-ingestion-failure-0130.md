# Production ingestion incident: ThreatFox bounded-response failure (01:30Z)

## Classification

- **Impact:** ingestion is partially degraded. Run `20c8d81a-48e4-5215-8292-63a72ddac05d` processed 37/38 sources; `threatfox-recent-indicators-abuse-ch` failed. The latest full-success run remains stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`).
- **Cause confidence:** high for the immediate cause (the deployed 10 MiB response guard); medium for the upstream payload growth cause.
- **Data integrity:** no recovery, restart, deployment, migration, database reset, volume/data/backup deletion, credential rotation, or evidence deletion was performed. Failed run/source records remain preserved.

## Authoritative monitor evidence

Read before model work from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`:

- `state=actionable_failure`
- `event_id=4d272492-6da2-407c-9880-a1677864f076`
- `observed_at=2026-09-15T01:30:42.448238+00:00`
- `correlation_id=0ff15abc-93bd-4753-a79a-657febfdbab6`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Recovery gate

The shared recovery gate was evaluated at approximately `2026-09-15T01:32:31Z` with its 1,800-second cooldown and lock. It recorded a **suppressed** decision:

- gate event ID `89528e24-2655-4ad4-8ad6-d4b84865442c`
- gate correlation ID `629a8da4-783f-4c51-af52-0401457930db`
- run `20c8d81a-48e4-5215-8292-63a72ddac05d`
- reason `recovery cooldown is active`

Read-back verified `/runtime/recovery.lock` is absent. The latest audit record is the corresponding suppressed event. No recovery action was authorized or attempted.

## Evidence collected

- **Repository/release:** remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch `main`; HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree has substantial pre-existing changes, including an uncommitted source configuration edit. No reset or cleanup was performed.
- **Running application:** CTI services use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, application version `0.1.0`, created 2026-09-12T12:54:53Z. Web, monitor, and scheduler started 2026-09-12T12:55Z with restart count 0. The worker is exited/unhealthy since startup and restart count 0; it is not implicated in the scheduler ingestion attempt observed here.
- **Health/readiness:** web `/health/live` and `/health/ready` returned HTTP 200 with `{"status":"ok"}` and database/configuration checks OK. Published host port is `127.0.0.1:18000`; no external service outage was observed. The monitor evidence provides full-success freshness and latest-attempt status, but no separate usable-run projection; the latest attempt is not usable because it failed one source.
- **Scheduler/monitor:** scheduler heartbeat was present and updated at 2026-09-15 01:33:09Z. Monitor and scheduler containers are healthy/up; monitor logs repeatedly report only the stale-success/latest-attempt failure pair.
- **Database/migrations:** PostgreSQL is healthy and accepting connections. The latest run is `failed`, started `2026-09-14T18:32:12.667740+00`, completed `2026-09-14T18:33:07.628491+00`, total 38, successful 37, failed 1, new documents 12,831, error summary `1 source(s) failed`, application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`. The failed source has `item_count=0`, no HTTP status, `error_classification=oversized_response`, and `response exceeds 10485760 bytes`. Database revision is `0015_contradiction_lifecycle`. No migration failure or pending revision was identified; an in-container Alembic check could not connect to localhost because the database is on the Compose network, so the authoritative `alembic_version` query was used.
- **Resources:** root filesystem 43% used with 279G available; memory 62Gi total/52Gi available; load 0.35/0.35/0.36; host file-descriptor limit 4096. CTI container memory was approximately monitor 30MiB, web 282MiB, scheduler 362MiB, PostgreSQL 257MiB, backup 3MiB. No resource-exhaustion signal.
- **Logs/events:** no container restart events were observed in the 01:00Z–01:35Z window. PostgreSQL contains two failed ad-hoc diagnostic queries using incorrect columns/joins; these are operator-query errors, not application transaction failures. Compose CLI inspection was not reproducible from the cron shell because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables were not exported; direct Docker inspection was used without exposing secret values.
- **Backups:** encrypted backup artifacts and metadata are present through `hermes-20260914T125520Z.dump.enc` (22,608,400 bytes) and `latest.metadata` at 2026-09-14T12:55:23Z. Restore verification was not run.
- **Certificate/proxy:** Caddy is running with restart count 0. Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; the live certificate issuer is the Caddy Local Authority, valid 2026-09-14 23:39:23Z through 2026-09-15 11:39:23Z. No proxy/certificate cause.
- **Configuration/deployment:** checked-in `config/sources.json` currently contains `max_response_bytes: 52428800` for ThreatFox, while the running ingestion record has the prior configuration hash and enforces 10 MiB. No `./scripts/update-app.sh` run occurred; the checked-in change is not deployed.

## Diagnosis and action

This is a source/provider-specific ingestion failure, not a web, proxy, scheduler, database, disk, memory, certificate, or backup outage. The deployed ThreatFox request returned more than the 10 MiB bounded-response limit. The smallest reversible repair is to review and test the existing 50 MiB source-bound change, including memory/decompression behavior, and deploy only under explicit deployment authorization via `./scripts/update-app.sh`. Because this run is diagnosis-only and the gate cooldown is active, no source rerun, restart, or deployment was performed.

## Prevention and follow-up

1. Resolve the missing protected environment export in the recovery cron while retaining the container fallback for monitor evidence.
2. Add a bounded ThreatFox fixture/regression test and verify memory/decompression limits before deployment.
3. After explicit authorization, deploy with `./scripts/update-app.sh`; verify the next run, failed-source classification, full-success/usable-run status, monitor evidence, and report/publication freshness.
4. Correct operational queries to the singular schema and current column names to avoid PostgreSQL log noise.
5. Run encrypted-backup restore verification separately.
6. Track the exited worker as a separate maintenance item; do not conflate it with this source-specific incident.

**Rollback:** not applicable; no application or data mutation was made. Recovery gate lock is absent and evidence/audit records are preserved.
