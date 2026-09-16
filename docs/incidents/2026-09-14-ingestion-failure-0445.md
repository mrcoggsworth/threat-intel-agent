# Production ingestion failure diagnostic (2026-09-14 04:45Z)

- **Observed at:** `2026-09-14T04:45:12.171080+00:00`
- **Monitor state:** `actionable_failure`
- **Event ID:** `b453d150-5bca-44f0-a987-ba1a6bf46f9b`
- **Correlation ID:** `427f55ad-1723-4e74-8d7f-c81aa2084347`
- **Latest attempt run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **Diagnosis time:** `2026-09-14T04:45Z` (host clock)

## Impact

The latest scheduled collection is failed but partially usable: 37 of 38 sources succeeded and persisted 1,564 new documents. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468+00`, so full-success freshness is stale. Reports and publications are also stale (186 reports and 201 publications; latest `2026-09-11T22:24:37.163555+00`). Successful evidence and the failed source record remain preserved.

## Cause and evidence

**Cause confidence: high.** This is a source/provider boundary failure, not a web, proxy, worker, scheduler, PostgreSQL, disk, memory, certificate, backup, or migration outage.

- Run `3848465e-e2a0-572a-b522-4c768d790284`: status `failed`, scheduled `2026-09-14T02:00:00Z`, completed `2026-09-14T02:00:06.398193+00`, 38 total / 37 successful / 1 failed, error summary `1 source(s) failed`.
- Failed source `threatfox-recent-indicators-abuse-ch`: `failed`, HTTP status absent, item count 0, cache `miss`, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- The same source-level failure pattern is present in prior failed runs; no evidence indicates database loss or corruption.

## Runtime and platform state

- Application version `0.1.0`; image tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created `2026-09-12T12:54:53.392614948Z`.
- Repository `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; last commit `feat(analyst): harden Hermes profiles with lock cleanup, pre-flight validation CLI, and sequence allocation`.
- `production.env` last observed mtime `2026-09-10 18:42:11 -0500`; no newer deployment/config change identified.
- Web, scheduler, monitor, backup, and PostgreSQL containers are running and healthy with restart count 0. PostgreSQL started `2026-09-05T16:36:57Z`; application containers started `2026-09-12T12:55:15Z` (monitor `12:55:20Z`). Worker is intentionally exited with code 0, 40 hours ago; no restart loop.
- Internal `/health/live` and `/health/ready` returned HTTP 200, with readiness reporting configuration and database OK. The host-published `127.0.0.1:18000` port returned HTTP 200 for live/readiness/version but HTTP 404 for the ops routes; the monitor's internal ops endpoint remains HTTP 200. This is a routing/projection follow-up, not the ingestion cause.
- Scheduler heartbeat exists at `/runtime/scheduler.heartbeat`, is fresh (mtime `2026-09-14T04:47:01Z`). Scheduler logs show repeated `source collection failed`; monitor logs show the expected stale-full-success/latest-attempt-failed state. No container lifecycle restart events were observed; Docker events were health/exec probes only.
- Host disk: 43% used, 280G available. Memory: 62Gi total, 52Gi available. Open-file limit: 4096. No OOM or resource exhaustion evidence.
- PostgreSQL `pg_isready`: accepting connections. Alembic revision: `0015_contradiction_lifecycle`, matching the repository migration head; no pending/failed migration evidence. An Alembic CLI check from the web container was not usable because it attempted localhost PostgreSQL, while direct PostgreSQL connectivity and schema queries succeeded.
- Latest backup metadata in the backup container: `hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes, SHA-256 recorded in protected metadata. Backup container healthy.
- Caddy certificate `hermes.crt`: Let's Encrypt issuer, valid `2026-08-18` through `2026-11-16`; no expiry risk. External trust/routing remains a separate follow-up.

## Recovery gate and actions

The required recovery gate was evaluated after reading current actionable evidence, with the 1,800-second cooldown and shared lock:

- `allowed: false`
- `reason: recovery cooldown is active`
- gate event ID `b453d150-5bca-44f0-a987-ba1a6bf46f9b`
- gate correlation ID `427f55ad-1723-4e74-8d7f-c81aa2084347`

The suppression was appended to `/runtime/recovery-events.jsonl` and read back. The recovery lock was verified absent. No restart, retry, deployment, migration, credential change, database mutation, or destructive recovery was performed because this request authorizes diagnosis only.

## Service, integrity, rollback, and prevention

- **Service state:** internally serving and ready; collection freshness degraded and publication freshness stale.
- **Data integrity:** preserved; 37 successful source results, failed source metadata, and failed ingestion run remain persisted. No destructive operation occurred.
- **Rollback:** not applicable; no application/configuration change was made.
- **Prevention:** bound or paginate the ThreatFox request below the 10 MiB transport limit while preserving `oversized_response`; add a mocked oversized-response regression test; retry only after the recovery gate permits it. Separately investigate the host-published ops-route mismatch, correct the Alembic CLI database-target check, and validate external Caddy routing/trust.
