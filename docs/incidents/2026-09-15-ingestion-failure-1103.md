# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T11:01:24.038010+00:00
- **Monitor state:** `actionable_failure`
- **Event ID:** `d8612965-37fc-4fb4-af7d-e16a0f914b91`
- **Correlation ID:** `8fae9fab-9543-406c-b807-2bf7946f75b8`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (`stale_data` signal)
- **Diagnosis time:** 2026-09-15T11:03:15Z
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** 59 pre-existing modified/deleted/untracked paths; this incident file is the only intentional addition from this diagnosis.
- **Application/image:** CTI containers use `cti-hermes:local`, started 2026-09-12T12:55Z; application version persisted by the latest run is `0.1.0`.

## Impact

The latest scheduled collection completed 37 of 38 sources and is persisted as `failed` because one source failed. The ThreatFox/Abuse.ch source is not fresh. The latest run persisted 13,108 new documents and retained the failed-source record. Database projections contain 33,797 source documents (latest retrieval 2026-09-15T02:00:54.267448Z), 186 reports, 201 report versions, and 201 publications. Report/version/publication freshness remains 2026-09-11T22:24:37Z. There are 2 usable runs and 26 failed runs in the database; no evidence of data loss was found.

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; `error_classification=oversized_response`; detail `response exceeds 10485760 bytes`; HTTP status unavailable. Persisted source configuration still has `max_response_bytes=10485760`, configuration version 2, seven consecutive failures, and last successful retrieval 2026-09-11T12:06:49.272951Z.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running healthy with restart count 0 and OOM false. Web `/health/live` and `/health/ready` returned HTTP 200; readiness reported configuration and database `ok`. The direct host port request to `/api/v1/ops/run-status` returned HTTP 404, while the monitor's internal route returned HTTP 200; this route mismatch is an operational/API-surface follow-up, not evidence of database or web unavailability.
- Scheduler heartbeat was present and current at 2026-09-15T11:03:13Z. Monitor logs continuously report stale full-success data and a failed latest ingestion attempt. No scheduler error traceback or restart loop was observed in the sampled logs.
- PostgreSQL accepted connections (`pg_isready`); database size is 195 MB; Alembic database revision is `0015_contradiction_lifecycle`. No pending or failed migration was observed from the available revision evidence. A direct `alembic current` check from a container-local localhost context remains unsuitable because PostgreSQL is a separate service.
- Host capacity is not limiting: root filesystem 43% used with 278G available, 51G memory available, swap in use 1.5G, and host open-file limit 4096. Container memory use was low and no OOM state was reported.
- Latest backup artifact is `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with metadata present and backup container healthy. No restore was attempted. Encrypted-backup contents/checksum were not revalidated during this diagnosis.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no renewal error was observed. Two unrelated client-disconnect warnings were present.
- The checked-out but undeployed `config/sources.json` contains a pre-existing ThreatFox `max_response_bytes=52428800` change. It was not deployed or modified by this diagnosis.

**Cause confidence: high.** This is a recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary, not a web, proxy, worker/scheduler liveness, PostgreSQL availability, disk, memory, migration, backup, or certificate-renewal failure.

## Recovery gate and actions

The authoritative monitor evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The shared gate was evaluated with its 1,800-second cooldown and lock. It returned `allowed=true` (`actionable monitor evidence acquired`) at 2026-09-15T11:02:12.345996Z, recorded an `attempted` event, and was immediately completed with outcome `suppressed` because this request authorized diagnosis only. Read-back verified `/runtime/recovery.lock` is absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, integrity, rollback, and prevention

- **Service state:** web readiness and database connectivity healthy; scheduler heartbeat current; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Data integrity:** preserved. Partial ingestion and failed-source evidence remain recorded; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no application or production-data mutation was made.
- **Prevention:** validate the bounded/paginated ThreatFox request or the existing 50 MiB response-limit change, add oversized-response regression coverage, and deploy only through `./scripts/update-app.sh` when explicitly authorized. Reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables. Investigate the internal-versus-host `/api/v1/ops/run-status` route mismatch. Separately perform encrypted-backup restore verification.
