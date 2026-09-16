# CTI-Hermes ingestion failure diagnostic — 2026-09-14 21:03Z

## Status and impact

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. The working tree has pre-existing unrelated modifications, deletions, and untracked files; this diagnostic did not normalize them.
- **Application/image:** `0.1.0`, `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`. CTI containers have been running since 2026-09-12T12:55Z; no deployment or restart was performed.
- **Impact:** ingestion freshness is degraded. The latest run is a usable partial run (37/38 sources succeeded, 12,831 new documents) but is terminal `failed`; the latest full-success run is stale. Reports (186), report versions (201), and publications (201) are stale with latest timestamp `2026-09-11 22:24:37.163555+00`.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before diagnosis.

- **State:** `actionable_failure`
- **Event ID:** `24e96d92-ac1a-4603-820c-6703e1b00716`
- **Observed at:** `2026-09-14T21:00:23.209206+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `312c4682-dde1-414d-818f-1e1feb8c4c5a`
- **Run ID:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed`; detail `1 source(s) failed`.
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`.

## Diagnosis and evidence

**Cause confidence: high.** PostgreSQL is accepting connections and records the latest run as `failed`: 38 total sources, 37 successful, 1 failed. The failed source is:

- `threatfox-recent-indicators-abuse-ch`: `status=failed`, `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`
- `error_classification=oversized_response`
- `error_detail=response exceeds 10485760 bytes`

The persisted run configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`. A pre-existing uncommitted change in checked-in `config/sources.json` raises this source's limit to `52428800` bytes, but it is not deployed. Retrying the unchanged request would reproduce the failure and was not performed.

No primary evidence indicates a web, proxy, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, credential, provider-authentication, or publication outage. PostgreSQL and Alembic both report revision `0015_contradiction_lifecycle`; `uv run alembic heads` matches it, with no pending migration evidence.

## Operational evidence

- Web, scheduler, monitor, PostgreSQL, backup, and Caddy are running; CTI service restart counts are `0`; no CTI container is OOM-killed.
- `cti-hermes-worker-1` is exited with code `0`, restart count `0`, health `unhealthy`; this reserved worker is not involved in the persisted ingestion failure.
- Web checks: `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration/database `ok`; `/version` HTTP 200 reports `0.1.0`.
- Scheduler heartbeat read back at `2026-09-14T21:02:38Z`; monitor evidence is current. Scheduler/web logs show no application exception or restart; monitor repeatedly reports the same actionable failure.
- Host resources: root filesystem 43% used with 279G available; 54GiB memory available; swap 1.5MiB/8GiB; open-file limit 4096; root inode use 6%.
- Backup metadata is present and healthy: `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`.
- Caddy is up; no certificate error or renewal failure was observed in the bounded log check.
- Compose validation could not run because this cron shell lacks protected `HERMES_SECRET_DIR` and required `HERMES_IMAGE`; no secret values were read or changed.

## Recovery gate and actions

The shared recovery gate was evaluated after authoritative actionable evidence was read, with the configured 1,800-second cooldown and lock:

- Gate decision: **allowed**, event `3935c4b4-fb72-4138-ac62-564546e8475e`, gate correlation `d986b5f2-7724-4887-98d4-facb9dca7ea3`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`.
- Attempt recorded at `2026-09-14T21:02:07.842689+00`.
- Completion recorded at `2026-09-14T21:03:29.709152+00`, outcome `failed`; lock read-back is absent.

No ingestion retry, restart, deployment, migration, configuration mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Diagnosis-only handling was required because applying the uncommitted provider/configuration change or retrying the unchanged request was not authorized and was not safe.

## Data integrity, rollback, and prevention

Failed ThreatFox evidence, successful-source evidence, and the usable partial-run record remain persisted and auditable. Risk is limited to incomplete source coverage and stale downstream outputs; no database corruption or publication mutation was found. No rollback is required because no application or data mutation occurred.

Smallest reversible authorized follow-up: validate ThreatFox filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression test; reconcile persisted source configuration with checked-in `config/sources.json`; deploy only through `./scripts/update-app.sh`; and verify the next run, source status, monitor evidence, and publication/data integrity. Export `HERMES_MONITOR_EVIDENCE_FILE` plus protected Compose variables in the recovery cron environment while retaining the container fallback. Investigate the internal-vs-monitor ops-route mismatch and operational query/schema drift separately.
