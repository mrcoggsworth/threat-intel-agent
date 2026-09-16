# Production ingestion incident: actionable failure, no safe recovery (14:04Z)

- **Recorded:** `2026-09-14T14:04:04Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; working tree had pre-existing modifications/deletions/untracked files and was not normalized.
- **Application/image:** running application version `0.1.0`; image tag `cti-hermes:local`; running CTI image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web/scheduler/monitor/backup started 2026-09-12 12:55Z.
- **Migration:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence was observed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was used: `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `b579bd15-80ad-45b1-bdae-1a61d01ca23e` (initial gate evidence); post-check event `825fca7b-478d-470a-8b55-d59c58a41a36`
- **Observed at:** `2026-09-14T14:00:53.157023+00:00`; post-check `2026-09-14T14:03:53.372701+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `cb544198-1d5a-4f26-9b7c-d8d2c759ac9e`; post-check `543ef313-9cf2-4c18-8ed9-0f85001f9211`
- **Run ID:** failed/latest `3848465e-e2a0-572a-b522-4c768d790284`; full-success `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed`, detail `1 source(s) failed`.

## Impact and diagnosis

The latest persisted run is usable partial output, not a full success: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`. Its source-run evidence is `status=failed`, `error_classification=oversized_response`, `error_detail=response exceeds 10485760 bytes`, `item_count=0`, no HTTP status, and `retry_count=0`. The source has five consecutive failures and its last successful retrieval was `2026-09-11 12:06:49+00`.

Cause confidence is **high**: deterministic provider response-size failure at the ThreatFox transport boundary. A configuration drift is also confirmed: the checked-in source configuration sets ThreatFox `max_response_bytes=52428800`, while the running persisted source configuration is `10485760`; this requires controlled reconciliation/deployment, not an in-place database edit. Evidence does not support web, proxy, scheduler, PostgreSQL, disk, memory, file-descriptor, certificate, backup, migration, credential, or publication failure as the primary cause.

Collection freshness is degraded and full-success freshness is stale. Successful-source documents, failed-source evidence, partial-run documents, and existing reports/publications remain usable; no data corruption or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL are running and healthy with restart count `0`. The reserved worker is exited with code `0` by design; it is not in a restart loop and is reported unhealthy because it is stopped.
- Web readiness read-back: `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`. PostgreSQL: `/var/run/postgresql:5432 - accepting connections`.
- Scheduler and monitor logs repeatedly show only the stale-success/latest-failed monitor condition; web logs show successful health/readiness/run-status responses. Docker event output showed health-check/exec activity and no CTI service restart event; the large event stream was not treated as proof of a restart.
- Host resources: root filesystem 43% used with 279G available; approximately 51GiB memory available; open-file limit `4096`; no OOM/resource exhaustion evidence.
- Backup state: backup container healthy; latest backup `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14 12:55:23Z`, 22,608,400 bytes, with recorded SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`.
- Certificate/proxy state: Caddy running, restart count `0`, version `v2.11.4`; prior external HTTPS check returned HTTP `404` with TLS verification result `20` under the configured local trust mismatch. This remains a separate ingress/certificate follow-up.
- Compose validation could not be run from this cron shell because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is an operator-environment limitation, not live outage evidence.

## Recovery gate and actions

The recovery gate was evaluated before any recovery attempt with the configured 1,800-second cooldown and lock. It acquired the actionable evidence and recorded:

- **Gate event:** `b579bd15-80ad-45b1-bdae-1a61d01ca23e`
- **Attempt:** `2026-09-14T14:01:33.781181+00`
- **Completion:** `2026-09-14T14:04:04.799335+00`, outcome `failed`
- **Lock read-back:** absent

No ingestion retry, restart, deployment, migration, response-limit mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. The gate audit and this incident record are the only state changes.

## State, rollback, and prevention

- **Service state:** internally live and ready; ingestion freshness degraded; full-success freshness stale.
- **Data-integrity state:** preserved; partial results and failed-source provenance remain intact.
- **Rollback:** not applicable; no application or data mutation occurred.
- **Smallest reversible follow-up:** validate a provider-supported filtered/paginated ThreatFox request or alternate endpoint using an offline fixture; retain the oversized-response regression fixture; reconcile persisted source configuration with checked-in `config/sources.json`; deploy only through `./scripts/update-app.sh` when explicitly authorized.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining fallback; add a persisted-vs-checked-in source configuration deployment check; continue separate Caddy route/TLS trust investigation; address known operational query/schema drift and CLI asyncpg event-loop cleanup traceback.
