# Production ingestion incident: ThreatFox bounded-response failure (17:01Z)

## Classification

- **Impact:** ingestion is partially degraded. Latest scheduled run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed 1 of 38 sources; 37 sources completed and 13,108 documents were new. The latest full-success run remains stale.
- **Cause confidence:** high for the immediate cause (ThreatFox response-size guard); low-to-medium for why the upstream payload exceeded the deployed bound.
- **Data integrity:** no database reset, volume/data deletion, migration, credential change, deployment, restart, retry, or evidence deletion was performed. Failed run/source records and successful-source partial data are preserved.

## Authoritative monitor evidence

Read first from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`:

- `state=actionable_failure`
- `event_id=73eb87b3-17d0-4263-bacb-5c748b0e9c27`
- `observed_at=2026-09-15T17:00:49.658631+00:00`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- `correlation_id=a7603796-3360-4b86-9888-f5793a9cf95d`
- latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`

## Recovery gate

The shared 1,800-second cooldown and lock were evaluated before any recovery action. The gate returned `allowed=false` with reason `recovery cooldown is active`, event `c0aef11d-5d66-4fcb-97cb-3eb077cd11ec`, correlation `305604d9-609f-4bb2-8a8d-cfe36e38bd56`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, recorded at `2026-09-15T17:01:56.183052+00:00`. The suppression was read back from `/runtime/recovery-events.jsonl`; no recovery lock was acquired. No recovery action was attempted.

## Evidence collected

- **Repository/release:** branch `main`, HEAD `c925cd5` (`feat(analyst): harden Hermes profiles with lock cleanup, pre-flight validation CLI, and sequence allocation`), three commits ahead of `origin/main`. The working tree contains substantial pre-existing changes and untracked files; this incident file is the only intended new incident record from this diagnosis.
- **Application/image:** running CTI services use `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`; package version could not be reported by the container metadata query, while the image/application release evidence remains the image ID and checked-out HEAD. Containers started 2026-09-12 12:55Z and have restart count 0.
- **Configuration/deployment:** checked-in working-tree change adds `max_response_bytes: 52428800` for ThreatFox, but it is not in the running image. No `./scripts/update-app.sh` or configuration deployment was run.
- **Runs/source:** latest run started `2026-09-15 02:00:00.049118+00`, completed `2026-09-15 02:00:54.439155+00`, status `failed`, totals `38/37/1`, new documents `13,108`, error summary `1 source(s) failed`. `threatfox-recent-indicators-abuse-ch` is `failed`, HTTP status absent, item count 0, `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11 12:06:50Z`. Per repository semantics, the latest failed run is still the latest usable run because it has 37 successful sources.
- **Web/proxy/health:** host liveness returned HTTP 200 `{"status":"ok"}`; readiness returned HTTP 200 with configuration and database `ok`. Caddy logs show successful certificate renewal and reload for `hermes.cti.scogin.dev`; no proxy or certificate cause identified.
- **Database/migrations:** PostgreSQL reported accepting connections. Alembic revision is `0015_contradiction_lifecycle`; no pending/failed migration evidence was found. No application transaction or constraint failure was observed.
- **Scheduler/monitor:** scheduler heartbeat was current at `2026-09-15 17:01:46.155515Z`; monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`. No container restart events were observed; Docker events were only exec probes from this diagnosis.
- **Resources:** root filesystem 43% used with 278G available; memory 62Gi total, 49Gi available; file-descriptor limit 4096. No resource exhaustion indication.
- **Backups:** encrypted backup artifacts are present through `hermes-20260915T125523Z.dump.enc` (24,823,024 bytes) and metadata/latest metadata at `2026-09-15 12:55:26Z`. Restore verification was not run during diagnosis.

## Diagnosis and action

This is a source/provider-specific ingestion failure, not a web, proxy, worker, scheduler, database, disk, certificate, or backup outage. The deployed ThreatFox request is bounded at 10 MiB and the provider response exceeded that limit. The working tree contains an un-deployed 50 MiB bound change. Retrying the unchanged request is not justified while the recovery cooldown is active and could add provider load.

**Action:** recorded the required non-secret recovery-gate suppression and this incident record. No service or data mutation was made.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, test the ThreatFox bounded-response change with memory/decompression safeguards and an oversized-response regression fixture, then deploy only through `./scripts/update-app.sh`.
2. Verify the next run's failed-source status, latest full-success/latest-usable projections, monitor evidence, and report/publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in maintenance cron while retaining the container fallback.
4. Run encrypted-backup restore verification separately.
5. Add source-specific classification/runbook guidance for repeated `oversized_response` failures.

**Rollback:** not applicable; no application, service, database, migration, configuration, or publication mutation occurred. Recovery-gate suppression was read back and no lock was acquired.
