# CTI-Hermes ingestion failure diagnostic — 2026-09-14 20:32Z

## Status and impact

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree contains pre-existing broad modifications, deletions, and untracked files; this diagnostic did not normalize or alter them.
- **Application:** `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- **Impact:** ingestion freshness remains degraded. Latest persisted attempt is a usable partial run with 38 sources: 37 successful and 1 failed. The latest full-success run is stale; reports and publications remain stale relative to ingestion. No evidence of database corruption or publication mutation was found.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; per the configured Compose fallback, evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before further diagnosis.

- **State:** `actionable_failure`
- **Event ID:** `07339c79-a98d-406f-86e2-d53732976642`
- **Observed at:** `2026-09-14T20:31:21.023000+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `cdb1e56d-83a5-45ab-ab5d-414b65b43e2c`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed`; detail `1 source(s) failed`.
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`.

## Diagnosis and evidence

**Cause confidence: high.** PostgreSQL records the latest run as `failed`, with 37/38 source runs completed and the sole failed source `threatfox-recent-indicators-abuse-ch`:

- `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`

The persisted source configuration has a 10 MiB response limit. The checked-in but pre-existing uncommitted `config/sources.json` change adds `max_response_bytes: 52428800` for this source; it has not been deployed. Retrying the unchanged request would reproduce the failure and was not performed.

No primary evidence indicates a web, proxy, scheduler, database connectivity, disk, memory, file-descriptor, certificate, backup, migration, credential, provider authentication, or publication outage. PostgreSQL revision is `0015_contradiction_lifecycle`. The scheduler heartbeat is current, and the monitor is current.

## Service and operational evidence

- Web, scheduler, monitor, PostgreSQL, and backup are running and healthy; restart count is `0`; none is OOM-killed.
- Reserved worker is exited with code `0`, restart count `0`, and health `unhealthy`; it is not involved in the persisted ingestion failure.
- Internal web checks: `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration/database `ok`; `/version` HTTP 200 reports `0.1.0`. The direct `/api/v1/ops/run-status` probe from the web container returned 404, while the monitor's authoritative internal probe returned HTTP 200; route topology/schema drift is a separate operational follow-up, not the ingestion cause.
- Latest ingestion run: `20c8d81a-48e4-5215-8292-63a72ddac05d`, started `2026-09-14 18:32:12.667740+00`, completed `2026-09-14 18:33:07.628491+00`, status `failed`.
- Latest full-success run: `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest source-document count `32,890`, latest retrieval `2026-09-14 18:33:07.527224+00`.
- Reports: `186`, latest `2026-09-11 22:24:37.163555+00`; publications: `201`, latest `2026-09-11 22:24:37.163555+00`.
- Host resources: root filesystem `43%` used with `279G` available; `54GiB` memory available; swap use `1.5GiB/8GiB`; open-file limit `4096`; root inode use `6%`.
- Recent Docker events show no CTI service restart events. PostgreSQL logs contain only failed ad-hoc diagnostic queries using incorrect relation/column names; no application persistence error was observed.
- Backup state: `/backups/latest.metadata` points to `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, `22,608,400` bytes, SHA-256 recorded as `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Backup container is healthy; no restore or backup mutation occurred.
- Certificate state: Caddy logs show successful renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no TLS failure was observed.
- Compose config validation could not run because the cron environment lacks protected `HERMES_SECRET_DIR` and required `HERMES_IMAGE`; no secret values were read or changed.

## Recovery gate and actions

The recovery gate was evaluated after reading actionable evidence with the configured 1,800-second cooldown and shared lock:

- **Gate event/correlation/run:** `07339c79-a98d-406f-86e2-d53732976642` / `cdb1e56d-83a5-45ab-ab5d-414b65b43e2c` / `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Decision:** allowed; actionable evidence acquired
- **Attempt recorded:** `2026-09-14T20:31:35.978403+00`
- **Completion recorded:** `2026-09-14T20:33:04.302098+00`, outcome `failed` (no safe diagnosis-only recovery)
- **Lock read-back:** absent after completion

No ingestion retry, service restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. This was diagnosis only, because recovery authorization did not include changing the provider request/configuration and a retry of the unchanged request was unsafe.

## Data integrity, rollback, and prevention

Failed ThreatFox evidence, successful-source evidence, and the usable partial-run record remain persisted and auditable. Risk is limited to incomplete source coverage, stale full-success freshness, and stale downstream reports/publications. No rollback is required because no application or data mutation occurred.

Smallest reversible follow-up after explicit maintenance/deployment authorization: validate bounded ThreatFox filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression test; reconcile persisted source configuration with checked-in `config/sources.json`; then deploy only through `./scripts/update-app.sh` and verify the next run, source status, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the recovery cron environment while retaining the container fallback. Investigate the internal-vs-monitor ops-route mismatch and incorrect operational query/schema assumptions separately.
