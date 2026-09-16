# Production ingestion incident: actionable partial-ingestion failure (14:46Z)

## Summary

- **Diagnosis time:** `2026-09-15T14:46:03Z` UTC; evidence rechecked at `2026-09-15T14:45:40.078885+00:00`.
- **Monitor state:** `actionable_failure`.
- **Monitor event:** `874bbedc-74bd-4396-89dd-e846d4d3856b`.
- **Correlation:** `4322a9c8-e9c2-4ab3-9346-16b80eb8c2c7`.
- **Latest failed run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`.
- **Full-success signal run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`.
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200 for both monitor signals.
- **Impact:** the latest collection is terminal `failed`, with 37/38 sources successful and 13,108 new documents. Successful-source data remains persisted and usable; ThreatFox coverage is unavailable. Full-success freshness is `stale_data`; reports, report versions, publications, detections, hunts, and remediation have not advanced since `2026-09-11T22:24:37Z`.

## Evidence and diagnosis

- PostgreSQL confirms the latest run started at `2026-09-15T02:00:00.049118+00`, completed at `02:00:54.439155+00`, has `total_sources=38`, `successful_sources=37`, `failed_sources=1`, `new_documents=13108`, `status=failed`, application version `0.1.0`, configuration hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`, and error summary `1 source(s) failed`.
- The failed source is **ThreatFox Recent Indicators (Abuse.ch)**: `status=failed`, no HTTP status, `item_count=0`, `retry_count=0`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.
- Persisted source configuration is `max_response_bytes=10485760`, `configuration_version=2`, `last_successful_retrieval=2026-09-11T12:06:49.272951+00`, `last_failure=2026-09-15T02:00:54.421527+00`, and `consecutive_failure_count=7`.
- Database state: PostgreSQL `16.14`, migration revision `0015_contradiction_lifecycle`, `source_document=33797` (latest retrieval `2026-09-15T02:00:54.267448+00`), `report=186`, `report_version=201`, `publication=201`, `detection=378`, `hunt=201`, `remediation=201`, and `relationship=11`.
- Running application image is `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, image digest `cti-hermes@sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`, created `2026-09-12T07:54:53.392614948-05:00`. Running containers report restart count 0.
- Web and readiness checks returned HTTP 200 locally. Direct host requests to the two `/api/v1/ops/*` paths returned 404, so those private operational routes were not independently verified from the host topology.
- Scheduler heartbeat was current at `2026-09-15T14:47:45Z`; monitor evidence was refreshing. Web, scheduler, monitor, PostgreSQL, and backup containers were healthy. Worker is intentionally exited 0 with `restart: no`; it is not implicated.
- Host resources were not exhausted: root filesystem 43% used with approximately 291 GB free, inode use 6%, approximately 53 GB memory available, and `ulimit -n=4096`.
- Backup state is present and current: `/backups/latest.metadata` is non-empty, modified `2026-09-15T12:55:26Z`; encrypted backup `hermes-20260915T125523Z.dump.enc` is present. Restore verification was not performed.
- Certificate state: expected host paths `/var/lib/cti-hermes/tls/fullchain.pem` and `privkey.pem` are unavailable to this job. Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev`; no CTI upstream/TLS outage was observed.
- Compose validation from this cron environment was blocked because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables were not exported. This prevented only an independent config render; running containers were inspected without exposing secrets.

## Recovery gate and actions

The authoritative evidence was read before any model work from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`, because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron environment. The evidence included event ID, observed timestamp, endpoint/status, correlation ID, and run ID and was actionable.

The shared recovery gate was evaluated with a 1,800-second cooldown and `/runtime` lock. It recorded suppressed event `dd2d9bde-2e21-4dbb-acd2-3d193bbcc7db` at `2026-09-15T14:46:42.910900+00`, correlation `6b8edc36-e131-4c88-b135-99b91656f17f`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`; reason was `recovery cooldown is active`. Read-back verified `/runtime/recovery.lock` absent and the audit record present.

No ingestion retry, service restart, deployment, migration, source-limit change, credential change, publication mutation, volume deletion, or data deletion was performed. The only state change was required non-secret recovery-gate audit bookkeeping and this incident record.

## State and follow-up

- **Cause confidence:** high that this is a deterministic ThreatFox provider-response-size/configuration mismatch; provider payload growth and safety of the staged 50 MiB limit remain unverified.
- **Service state:** web/readiness/database/monitor/scheduler/backup healthy; ingestion freshness and ThreatFox coverage degraded; full-success freshness stale; analyst/publication projections stale.
- **Data-integrity state:** no persistence-integrity error or data loss observed. Failed source/run records remain explicit, and successful-source data remains available.
- **Rollback:** not applicable; no production mutation occurred. Under explicit recovery/deployment authorization, validate a bounded/paginated ThreatFox request or the staged limit with an offline oversized-response fixture, then deploy only through `./scripts/update-app.sh`; revert the focused source-limit change and rerun the update if checks fail.
- **Prevention:** add/retain oversized-response regression coverage, assess decompression/memory bounds, export monitor and protected Compose variables in maintenance cron, verify private ops-route topology, independently verify certificate paths, and perform encrypted-backup restore verification.
