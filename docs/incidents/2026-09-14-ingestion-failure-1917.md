# CTI-Hermes ingestion failure diagnostic — 2026-09-14 19:17Z

## Status and impact

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree had pre-existing broad modifications, deletions, and untracked files; none were normalized or changed.
- **Application:** `0.1.0`, image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- **Impact:** ingestion freshness is degraded. Latest persisted run is usable partial output: 38 sources, 37 successful, 1 failed, and 12,831 new documents. The latest full-success run remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` and is stale. Reports/publications are unchanged and stale relative to ingestion.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured Compose fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before further diagnosis.

- **State:** `actionable_failure`
- **Event ID:** `0c2cc1ef-0100-43ca-acad-069ad2554648`
- **Observed at:** `2026-09-14T19:15:15.644359+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `dad71796-cdf1-4e51-9eef-445bb1f67717`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed`; failed-source detail `1 source(s) failed`.
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`.

## Diagnosis and evidence

**Cause confidence: high.** PostgreSQL records the latest run as `failed`, with 37/38 sources successful. The sole failed source is `threatfox-recent-indicators-abuse-ch`: `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The persisted source row reports a 10 MiB response limit and six consecutive failures. Checked-in `config/sources.json` contains a 50 MiB value in the existing uncommitted configuration changes, confirming configuration/runtime drift; it was not deployed or edited by this diagnostic.

No evidence indicates a web, proxy, scheduler, database connectivity, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication outage as the primary cause. The failure is a deterministic bounded-transport/provider response-size issue.

## Service and operational evidence

- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy with restart count `0`; none is OOM-killed. The reserved worker is exited with code `0` and has restart count `0`.
- Web read-back: `/health/live` HTTP `200`, `{"status":"ok"}`; `/health/ready` HTTP `200`, configuration/database checks `ok`; `/version` reports `0.1.0`.
- PostgreSQL accepts connections. Alembic revision is `0015_contradiction_lifecycle`; no pending or failed migration was indicated by the live revision. No database initialization or schema/data operation occurred.
- Scheduler heartbeat was updated at `2026-09-14T19:16:37Z`; monitor evidence was refreshed at `2026-09-14T19:16Z`. Recent Docker event query showed no CTI restart events.
- Host resources: root filesystem `43%` used with `279G` available; `54GiB` memory available; swap use negligible; open-file limit `4096`.
- Persistence read-back: `source_document` count `32,890`, latest retrieval `2026-09-14T18:33:07.527224+00`; `report` count `186`, latest `2026-09-11T22:24:37.163555+00`; `publication` count `201`, latest `2026-09-11T22:24:37.183379+00`.
- Backup state: `/backups/latest.metadata` points to `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, `22,608,400` bytes, with recorded SHA-256. Backup container is healthy; no restore or backup mutation occurred.
- Certificate state: Caddy logs show successful renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no TLS failure was observed. Caddy is the standalone `caddy` container.
- Compose validation was not run because the cron environment lacks protected `HERMES_SECRET_DIR` and required `HERMES_IMAGE`; no secret values were read or changed.

## Recovery gate and actions

The recovery gate was evaluated in the monitor container with the configured 1,800-second cooldown and shared lock after reading the actionable evidence:

- **Gate event:** `219e1009-478b-4f20-a5b3-a2c3a8b24afb`
- **Gate correlation:** `ca3036d7-a16f-4f90-9aa8-270381ccc01d`
- **Gate run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Decision:** allowed; actionable evidence acquired
- **Attempt recorded:** `2026-09-14T19:16:18.704937+00`
- **Completion recorded:** `2026-09-14T19:17:14.250244+00`, outcome `failed` (no safe diagnosis-only recovery)
- **Lock read-back:** absent

No ingestion retry, service restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. This was diagnosis only; retrying the unchanged oversized request would not be a safe corrective action.

## Data integrity, rollback, and prevention

Failed ThreatFox evidence, successful-source evidence, and the usable partial-run record remain persisted and auditable. Risk is limited to incomplete source coverage, stale full-success freshness, and stale downstream reports/publications; no database corruption or publication mutation was found. No rollback is required because no application or data mutation occurred.

Smallest reversible follow-up after explicit maintenance/deployment authorization: validate provider-supported filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression test; reconcile persisted source configuration with checked-in `config/sources.json`; then deploy only through `./scripts/update-app.sh` and verify the next run, source status, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the recovery cron environment while retaining the container fallback. Investigate the internal-vs-public ops-route mismatch and known operational query/schema drift separately.
