# Production ingestion incident: actionable failure, diagnosis-only recovery suppression (14:46Z)

- **Recorded:** `2026-09-14T14:46:59Z`
- **Repository/release:** branch `main`; HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`. Working tree contained pre-existing modifications, deletions, and untracked files; no unrelated changes were normalized.
- **Application/image:** running CTI services use `cti-hermes:local`; container image ID and application version were not re-derived in this pass. Prior verified runtime evidence identifies application version `0.1.0`; the running web image did not expose `HERMES_VERSION`.
- **Migration:** PostgreSQL is at Alembic revision `0015_contradiction_lifecycle`; the database is reachable and no pending/failed migration evidence was observed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. The configured Compose fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `27050730-1ade-4d49-b210-aeef8f4e7fb0`
- **Observed at:** `2026-09-14T14:44:56.328578+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `ea07715e-b9a9-4fd8-b00b-f5f3df40d9b3`
- **Run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed`; latest signal detail `1 source(s) failed`.
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`.

## Impact and diagnosis

The latest persisted ingestion run is usable partial output: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`; the source-run record reports `failed`, `oversized_response`, `response exceeds 10485760 bytes`, item count `0`, no HTTP status, and retry count `0`. The same run remains persisted and its failed-source provenance is intact.

Cause confidence is **high**: a deterministic ThreatFox provider response-size failure at the transport boundary. The evidence does not indicate a web, scheduler, PostgreSQL, disk, memory, file-descriptor, certificate, backup, credential, migration, or publication failure as the primary cause. A previously verified source-configuration drift remains the controlled follow-up: checked-in ThreatFox configuration specifies a larger response bound than the running persisted configuration. This must be reconciled through the normal application update path, not an in-place database edit.

Collection freshness is degraded and full-success freshness is stale. Existing successful-source documents and prior reports/publications remain usable; no corruption or unauthorized publication mutation was observed.

## Service and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running with restart count `0`; web, scheduler, monitor, PostgreSQL, and backup health are healthy. The reserved worker is exited with code `0` by design and is not in a restart loop.
- Web read-back: `/health/live` returned HTTP `200` with `{"status":"ok"}`; `/health/ready` returned HTTP `200` with database and configuration checks `ok`.
- PostgreSQL read-back: `pg_isready` accepted connections; PostgreSQL `16.14`; Alembic revision `0015_contradiction_lifecycle`.
- Recent monitor logs repeatedly report only stale full-success/latest-failed ingestion. Recent web logs show successful health/readiness checks. No CTI container restart events were observed in the bounded Docker event query.
- Host resources: root filesystem `43%` used with `279G` available; `51GiB` memory available; open-file limit `4096`; no OOM or resource-exhaustion evidence.
- Database output counts: `source_document` 31,678, latest retrieval `2026-09-14 02:00:05.858334+00`; `report` 186, latest `2026-09-11 22:24:37.163555+00`; `publication` 201, latest `2026-09-11 22:24:37.183379+00`.
- Backup metadata is present and fresh: `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, `22,608,400` bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`.
- Caddy is running as container `caddy`, image `caddy:latest`, version `v2.11.4`, restart count `0`. Certificate file stat was not available at the checked path in that container; external ingress/TLS remains a separate follow-up.
- Compose validation could not be run from this cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is an operator-environment limitation, not live outage evidence.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable monitor evidence, with the configured 1,800-second cooldown and lock. It acquired the gate and recorded:

- **Gate event:** `ba9164df-d3ce-476d-8ab0-410e535e960b`
- **Attempt:** `2026-09-14T14:46:17.577596+00`
- **Completion:** `2026-09-14T14:46:59.615495+00`, outcome `suppressed`
- **Lock read-back:** absent

This request authorizes diagnosis only, so no ingestion retry, service restart, deployment, migration, response-limit mutation, credential change, volume/data deletion, backup deletion, or publication mutation was performed. The recovery audit and this incident record are the only state changes.

## Service, data, rollback, and prevention state

- **Service state:** internally live and ready; ingestion freshness degraded; full-success freshness stale.
- **Data-integrity state:** preserved; partial-run documents and failed-source evidence remain intact.
- **Rollback:** not applicable; no application or data mutation occurred.
- **Smallest reversible follow-up:** validate a provider-supported filtered/paginated ThreatFox request or alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile persisted source configuration with checked-in `config/sources.json`; deploy only through `./scripts/update-app.sh` when explicitly authorized.
- **Prevention:** export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback; add a persisted-vs-checked-in source-configuration deployment check; continue separate Caddy route/TLS investigation; address known operational query/schema drift and CLI asyncpg event-loop cleanup traceback.
