# CTI-Hermes production ingestion failure diagnostic (20:47Z)

## Monitor evidence and gate

- **Diagnosis time:** `2026-09-15T20:48:17Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the configured container fallback was used.
- **Monitor state:** `actionable_failure`
- **Event ID:** `22470b97-d382-4629-99ca-3102134021c0`
- **Observed at:** `2026-09-15T20:46:05.649238+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `7b0769a3-3ccc-4a63-b204-0bcd025d37fe`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.

The shared recovery gate was evaluated after reading the actionable evidence with the configured 1,800-second cooldown and `/runtime` lock. It returned `allowed=false`, reason `recovery cooldown is active`, and recorded suppressed event `22470b97-d382-4629-99ca-3102134021c0` at `2026-09-15T20:47:03.928644Z`. Read-back verified `/runtime/recovery.lock` is absent; the preceding attempt/suppressed event was `59916f7e-a86b-41dd-84d0-b424a55faaf5` at `2026-09-15T20:32:44.134573Z`.

No retry, restart, deployment, migration, credential change, or destructive recovery was performed because this scheduled request authorizes diagnosis only.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch is ahead of `origin/main` by 3 commits.
- Working tree has pre-existing modifications and untracked files; this diagnostic added this incident record only.
- Running image: mutable `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53-05:00`.
- Application version: `0.1.0`.
- Database migration revision: `0015_contradiction_lifecycle`, matching local head.
- Last deployment/config evidence: application containers started `2026-09-12T12:55:15Z`; `/opt/cti-hermes/env/production.env` mtime `2026-09-10 18:42:11 -0500`. Compose validation was not run because protected `HERMES_SECRET_DIR` and immutable `HERMES_IMAGE` are not exported in this cron shell.

## Impact and cause

The latest persisted run is terminal `failed`: 37/38 sources succeeded and one failed. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), with `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, and zero items. The source has `last_successful_retrieval=2026-09-11T12:06:49.272951Z`, `last_failure=2026-09-15T02:00:54.421527Z`, `consecutive_failure_count=7`, deployed `max_response_bytes=10485760`, and configuration version `2`.

The checked-out but undeployed `config/sources.json` change raises that limit to `52428800` (50 MiB). This is strong evidence of a deterministic provider response-size/configuration mismatch. The latest completed full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` from `2026-09-11T02:00Z`; the latest five runs are failed. Cause confidence is **high**. Remaining uncertainty is whether the staged 50 MiB limit is safe or whether bounded/paginated ThreatFox retrieval is preferable.

**Operational impact:** partial ingestion remains available for 37 sources, but ThreatFox coverage is stale/unavailable; full-success freshness remains stale. Reports/publications have not advanced since `2026-09-11T22:24:37Z`.

## Service, integrity, and recovery evidence

- Web, scheduler, monitor, backup, and PostgreSQL are running and healthy; restart counts are 0 and `OOMKilled=false` for inspected CTI application/database containers. The worker is intentionally not a persistent running service (`restart: no`).
- Web `/health/live` and `/health/ready` returned HTTP `200`; readiness reported configuration and database `ok`. Scheduler heartbeat was fresh at `2026-09-15T20:48:17Z`.
- PostgreSQL 16.14 is accepting connections; database size is 195 MB, 8 sessions, and 0 waiting locks. Persistence counts are 33,797 source documents, 186 reports, 201 report versions, and 201 publications. Failed-source and partial-ingestion records remain preserved.
- Host capacity is healthy: root filesystem 43% used with 278 GB available, 48 GiB memory available, negligible swap use, and open-file limit 4096.
- Latest encrypted backup metadata identifies `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore verification was not attempted.
- Certificate revalidation for `matrix-1.taild27e3c.ts.net:9444` succeeded: Let's Encrypt `YE1`, valid through `2026-11-16T14:30:36Z`.
- Docker events in the observation window were health-check/diagnostic `exec_*` events; no service restart/crash event was observed. Scheduler logs report `source collection failed`; monitor logs consistently report the two evidence failures.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. No volumes, backups, migration history, failed evidence, partial source data, or public CTI conclusions were altered.
- **Rollback:** not applicable; no production mutation occurred. A future compatible deployment should roll back by reverting the focused source-limit change and rerunning `./scripts/update-app.sh` if bounded-ingestion or health verification fails.
- **Prevention/follow-up:** under explicit maintenance authorization, validate bounded or paginated ThreatFox retrieval or the staged 50 MiB limit with an offline oversized-response fixture and regression coverage; deploy only through `./scripts/update-app.sh`; then verify source persistence, full-success/usable-run status, monitor evidence, and publication freshness. Reconcile cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`; correct the container migration command's database endpoint; and separately verify backup restoreability and the internal-versus-host operations-route mismatch.
