# Production ingestion incident: actionable failure, recovery suppressed (13:17Z)

- **Recorded:** `2026-09-14T13:17:54Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present. This diagnosis changed only this incident record and recovery-gate audit state; no application, deployment, database, or publication files were changed.
- **Application/image:** application version `0.1.0` from the running release evidence; image tag `cti-hermes:local`; running web image ID `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`; web/scheduler/monitor/backup started `2026-09-12T12:55Z`.
- **Migration revision:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence observed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`. Per the configured Compose fallback, authoritative evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `0bdd92e2-8515-4224-9503-88750f2689c8`
- **Observed at:** `2026-09-14T13:15:49.952950+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `4cba44b9-aed3-4cd4-b537-730fcbcaff40`
- **Latest failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, signal state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` with detail `1 source(s) failed`.

## Impact and diagnosis

The persisted latest run is a usable partial result but not a full success: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`; its persisted source-run evidence records `error_classification=oversized_response` and `error_detail=response exceeds 10485760 bytes`, with `item_count=0`, no HTTP status, `retry_count=0`, and `cache_state=miss`. The configured response limit is `10485760` bytes and the source has `consecutive_failure_count=5`.

Primary cause is a deterministic ThreatFox/Abuse.ch provider response-size boundary at the source transport boundary. Configuration/deployment drift against checked-in `config/sources.json` remains a follow-up. Cause confidence: **high**. Evidence does not support web, proxy, scheduler, PostgreSQL, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication failure as the primary ingestion cause.

Collection freshness is degraded and full-success freshness is stale. Successful-source documents and partial-run evidence remain usable; no data corruption or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running; web/scheduler/monitor/backup/postgres restart count is `0` and health is `healthy`. The reserved worker is exited with code `0` and is not in a restart loop; its Compose health is reported unhealthy because it is stopped by design.
- Web readiness read-back: `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`. PostgreSQL accepted connections: `/var/run/postgresql:5432 - accepting connections`.
- Docker events during the observation window showed health-check/exec activity and the gate evaluation, with no service restart event.
- Host root filesystem is 43% used with 279G available; memory available is approximately 51GiB; open-file limit is `4096`. No OOM or resource exhaustion evidence was observed.
- Backup metadata is current: `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 recorded as `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; backup container is healthy.
- Caddy is running with restart count `0`; external HTTPS health check returned HTTP `404` with TLS verification result `20` when checked with the configured local trust mismatch. This is a separate ingress/certificate trust follow-up, not the internal ingestion cause.
- Compose config validation was not run because the cron environment lacks required `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not live outage evidence.

## Recovery gate and actions

The recovery gate was evaluated against the current authoritative evidence with the configured 1,800-second cooldown and shared lock:

- **Gate result:** `allowed=false`
- **Gate event:** `0bdd92e2-8515-4224-9503-88750f2689c8`
- **Gate reason:** `recovery cooldown is active`
- **Gate recorded at:** `2026-09-14T13:16:28.068041+00:00`
- **Lock read-back:** `recovery.lock` absent

No ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed. The only state changes were the required non-secret recovery-gate suppression audit and this incident record.

## State, rollback, and prevention

- **Service state:** internally live and ready; ingestion freshness degraded; full-success freshness stale.
- **Data-integrity state:** preserved; failed-source evidence, successful-source results, partial-run documents, and existing reports/publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible authorized follow-up:** validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile running source configuration with checked-in `config/sources.json`; then deploy only through `./scripts/update-app.sh` after explicit recovery/deployment authorization.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; add a deployment check for persisted-vs-checked-in source configuration; verify backup/publication freshness; investigate external Caddy route/TLS trust separately; and address the known CLI asyncpg event-loop cleanup traceback.
