# Production ingestion incident: actionable failure, recovery suppressed (13:03Z)

- **Recorded:** `2026-09-14T13:03:21.357737Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present. No application, deployment, database, or publication files were changed by this diagnosis.
- **Application/image:** application version `0.1.0` (from the running release evidence); image tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web/scheduler/monitor/backup started `2026-09-12T12:55Z`.
- **Migration:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured Compose fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `ee6e775b-3224-42ca-a0f6-e443323f1c31`
- **Observed at:** `2026-09-14T13:02:49.028634+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `0f3f7e7a-005f-4873-ba2e-886a199188b9`
- **Latest failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, signal state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` with detail `1 source(s) failed`.

## Impact and diagnosis

The latest persisted run started at `2026-09-14T02:00:00.095941+00Z` and completed at `2026-09-14T02:00:06.398193+00Z` with status `failed` but usable partial results: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`; its persisted source-run record has `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The source configuration has `max_response_bytes=10485760` and `consecutive_failure_count=5`.

The primary cause is a deterministic ThreatFox/Abuse.ch provider response-size boundary at the source transport boundary, with deployment/configuration drift also requiring reconciliation against checked-in `config/sources.json`. Cause confidence is **high**. Evidence does not support web, proxy, worker, scheduler, PostgreSQL, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication failure as the primary cause.

Successful-source evidence and partial-run documents remain persisted. Current database counts are 31,678 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediation records, and 11 relationships. No corruption or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running and healthy; restart count is `0`. The reserved worker is exited with code `0` and is not in a restart loop.
- In-container liveness and readiness returned HTTP `200`; readiness reported configuration and database `ok`.
- PostgreSQL accepted connections; database `hermes` is at revision `0015_contradiction_lifecycle`. No pending/failed migration evidence was found.
- Host root filesystem is 43% used with 279G available; host memory available is approximately 51GiB; open-file limit is `4096`. No OOM or restart event was observed.
- Backup metadata is current: `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 recorded in metadata as `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Backup container is healthy.
- Caddy is running in Docker with restart count `0` and logs show successful local certificate renewal. External HTTPS `/health/live` returned `404` with TLS verification failure (`unable to get local issuer certificate`); this is a separate ingress/trust/routing follow-up, not the internal ingestion cause.
- `docker compose config --quiet` could not be run from the cron shell because required `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables were not exported. This is an operator-environment limitation, not evidence of a live container outage.

## Recovery gate and actions

The recovery gate was evaluated after reading actionable evidence, with its configured 1,800-second cooldown and shared lock.

- Gate evaluation for event `7a47f248-3d23-4281-8bdd-0109b60ef39e` recorded `attempted` and was completed as `suppressed` because this request authorizes diagnosis only. No recovery mutation was performed.
- A fresh evaluation for the authoritative event `ee6e775b-3224-42ca-a0f6-e443323f1c31` recorded `suppressed` event `ee6e775b-3224-42ca-a0f6-e443323f1c31` at `2026-09-14T13:03:21.357737Z` because `recovery cooldown is active`.
- Lock read-back: `recovery.lock` absent.
- No ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## State, rollback, and prevention

- **Service state:** internally serving and ready; collection freshness is degraded and full-success freshness is stale.
- **Data-integrity state:** preserved; successful sources, partial-run documents, failed-source evidence, reports, and publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible follow-up:** validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; and deploy only through `./scripts/update-app.sh` after explicit recovery/deployment authorization.
- **Prevention work:** add a deployment check comparing persisted source configuration to checked-in configuration; export `HERMES_MONITOR_EVIDENCE_FILE` in the operator cron environment while retaining the container fallback; verify backup metadata and publication freshness; investigate the external Caddy route/TLS trust chain separately; and fix the CLI asyncpg event-loop cleanup traceback seen in prior diagnostics.
