# Production ingestion incident: actionable partial-ingestion failure (14:32Z)

## Summary

- **Observed:** `2026-09-15T14:32:39.152079+00:00` (monitor refresh); diagnosis at approximately `2026-09-15T14:33Z`.
- **Monitor state:** `actionable_failure`.
- **Monitor event:** `124e9d43-2669-4d72-99f2-b7dcd607452f`.
- **Correlation:** `feeba722-b54c-44c1-ac99-66be51401160`.
- **Latest failed run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`.
- **Full-success signal run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`.
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200 for both monitor signals.
- **Impact:** the latest collection is terminal `failed` with 37/38 source results and 13,108 new documents. Successful-source data remains persisted and usable; ThreatFox coverage is unavailable. Full-success freshness remains stale and publications have not advanced since `2026-09-11T22:24:37.183379+00:00`.

## Evidence and diagnosis

- PostgreSQL `ingestion_run` confirms the latest run started at `2026-09-15T02:00:00.049118+00`, completed at `02:00:54.439155+00`, has `total_sources=38`, `successful_sources=37`, `failed_sources=1`, `new_documents=13108`, `status=failed`, application version `0.1.0`, and error summary `1 source(s) failed`.
- The failed `source_run` is **ThreatFox Recent Indicators (Abuse.ch)**: `status=failed`, `item_count=0`, no HTTP status, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.
- The persisted source configuration is `max_response_bytes=10485760`, `configuration_version=2`, `last_successful_retrieval=2026-09-11T12:06:49.272951+00`, `last_failure=2026-09-15T02:00:54.421527+00`, and `consecutive_failure_count=7`.
- The checked-out but undeployed working-tree change in `config/sources.json` adds a 50 MiB limit. The running application remains `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T12:55:03.601753337Z`, with local image digest `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291` reported by prior incident evidence. This is high-confidence evidence of a deterministic provider-response-size/configuration mismatch, not a web, proxy, scheduler, worker, database, disk, memory, migration, or persistence outage.

### Required service and platform checks

- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy with restart count 0. Web liveness/readiness returned HTTP 200; direct PostgreSQL `pg_isready` accepted connections; direct web checks returned 200/200.
- Worker is exited 0 by design (`restart: no`), with no crash evidence; it is not the cause of this scheduled source failure.
- Scheduler heartbeat was current (`2026-09-15T14:33:15Z` during collection). Monitor evidence continued refreshing and monitor logs consistently reported only the stale full-success/latest-failed-run condition.
- Database is PostgreSQL 16.14, 16 active connections at sampling, and 195 MB. Migration head is `0015_contradiction_lifecycle`; database connectivity is healthy.
- Root filesystem is 43% used with approximately 279 GB available; host memory has approximately 49 GiB available; host `ulimit -n` is 4096. No resource exhaustion was found.
- Docker events in the observation window contained health-check/exec activity and the diagnostic gate bookkeeping only; no CTI service restart or crash event was observed.
- Backup container is healthy. The latest encrypted backup is `hermes-20260915T125523Z.dump.enc`, completed at `2026-09-15T12:55:26Z`, with metadata present and SHA-256 recorded in the protected metadata. Restore verification was not performed.
- Certificate state could not be independently read from the expected host path `/var/lib/cti-hermes/tls/fullchain.pem`; Caddy is running with no restart evidence and no TLS/upstream error was present in the sampled logs. Certificate verification remains a separate operational follow-up.
- Compose inspection from this cron environment was blocked by missing protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` environment variables. This is an operator-environment/configuration issue, not evidence of production service failure; no stack mutation was attempted.
- Repository identity: `origin=git@github.com:mrcoggsworth/threat-intel-agent.git`, branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`. The working tree contains pre-existing unrelated profile/document/config changes, including the staged-but-undeployed 50 MiB ThreatFox limit; they were not modified.

## Recovery gate and actions

The authoritative evidence was read first from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because the cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`. The evidence contained the event ID, observed timestamp, endpoint/status, correlation ID, and run ID and was actionable.

The shared recovery gate was then evaluated with a 1,800-second cooldown and `/runtime` lock. It acquired attempted event `644b2647-9707-4f8a-8cfb-35bb3ec58359` at `2026-09-15T14:31:50.592907+00:00`, correlation `aaeed9f2-5b76-4041-b838-7f458364c256`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Because this scheduled request authorizes diagnosis only, it was completed with outcome `suppressed`; read-back verified the audit completion record and `/runtime/recovery.lock` absent.

No ingestion retry, service restart, deployment, migration, source-limit change, credential change, publication mutation, volume deletion, or data deletion was performed. Failed source/run records and successful-source data remain preserved.

## State and follow-up

- **Cause confidence:** high for the ThreatFox response-size enforcement mismatch; provider payload growth and safety of the staged 50 MiB limit remain unverified.
- **Service state:** web/readiness/database/monitor/scheduler/backup healthy; ingestion freshness and ThreatFox coverage degraded; full-success freshness stale.
- **Data-integrity state:** no persistence-integrity error or data loss observed. Partial successful-source data is available; the failed source is explicitly preserved as failed.
- **Rollback:** not applicable; this run made no production mutation. Any future compatible deployment must use `./scripts/update-app.sh`; revert the focused source-limit change and rerun the update if bounded-ingestion or health checks fail.
- **Prevention:** validate a bounded/paginated ThreatFox request or the staged 50 MiB limit against an offline oversized-response fixture, assess decompression/memory behavior, and add regression coverage before authorized deployment. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and protected Compose variables; separately verify certificate state, backup restore integrity, and internal-vs-localhost ops-route topology.
