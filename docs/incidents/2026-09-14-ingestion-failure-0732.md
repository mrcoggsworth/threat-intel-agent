# Production ingestion incident: actionable failure, recovery suppressed (07:32Z)

- **Recorded:** `2026-09-14T07:32:31Z`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications/deletions and untracked incident/evidence files present; not modified except this incident record
- **Application/image:** version `0.1.0`, image `cti-hermes:local`, image ID/digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created `2026-09-12T07:54:53-05:00`
- **Migration revision:** `0015_contradiction_lifecycle`; no pending/failed migration evidence observed

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative machine-readable evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`, the configured Compose mount.

- **Monitor state:** `actionable_failure`
- **Event ID:** `5128c1bf-c20b-45b5-ab6c-a83534319b75`
- **Observed at:** `2026-09-14T07:30:24.007504+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `2a7f0c61-4ae6-4e3a-8a35-abac51a8a2ef`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`)

## Diagnosis and impact

The `2026-09-14 02:00Z` run is failed but usable: 38 sources total, 37 successful, 1 failed, and 1,564 new documents persisted. The failed source is `threatfox-recent-indicators-abuse-ch` with `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The persisted source configuration limit is 10 MiB; the checked-in configuration has the previously identified larger limit, so the running image/configuration is not reconciled.

Persisted public CTI remains available from successful-source and partial-run data, but complete source coverage and full-success freshness are degraded. Read-only counts: 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334Z`), 186 reports (latest update `2026-09-11T22:24:37.183379Z`), and 201 publications (latest publication `2026-09-11T22:24:37.183379Z`). No evidence indicates corruption, data loss, or unauthorized publication mutation.

**Cause confidence: high.** Deterministic ThreatFox provider/source response-size boundary mismatch. Evidence does not support web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage as the primary cause.

## Service and operational evidence

- Web liveness/readiness: HTTP `200` / `200` from inside `cti-hermes-web-1`.
- The configured ops route returned HTTP `404` when checked at `/api/v1/ops/run-status` from the web container; the monitor's internal request nevertheless recorded HTTP `200`. This route/topology mismatch is a separate follow-up concern, not the ingestion failure cause.
- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy; restart count `0`; stack services have been up approximately 43 hours. Worker is a reserved one-shot service, exited `0`, with no restart loop.
- Monitor logs repeatedly report `last successful run stale, latest ingestion attempt failed`; scheduler logs showed no scheduler exception.
- No CTI container restart/OOM event was observed in the two-hour Docker event window; health checks and exec probes were recorded only.
- Root filesystem: 504 GiB total, 203 GiB used, 280 GiB available (43%). Memory: 62 GiB total, approximately 52 GiB available. Host open-file limit: 4096. No resource exhaustion indicated.
- PostgreSQL: `pg_isready` accepting connections; `current_database=hermes`, `current_user=hermes`.
- Backup: encrypted artifacts present, including `hermes-20260913T125518Z.dump.enc` (22,110,800 bytes, latest observed artifact); no backup mutation occurred.
- Certificate/proxy: Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate failure indicated.
- Compose validation from this cron shell was blocked by absent protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables; this was read-only and not treated as a service failure.

## Recovery gate and actions

The recovery gate was evaluated after reading the current authoritative evidence, with the 1,800-second cooldown and shared lock:

- **Gate event:** `5128c1bf-c20b-45b5-ab6c-a83534319b75`
- **Gate result:** evidence acquired and `attempted` event recorded at `2026-09-14T07:31:08.626456+00:00`
- **Completion:** `completed` with outcome `suppressed` at `2026-09-14T07:32:31.586269+00:00`, reason `diagnosis-only request; recovery not authorized`
- **Lock read-back:** absent

No ingestion retry, service restart, deployment via `./scripts/update-app.sh`, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed. The gate audit was read back successfully, preserving the failed-source evidence and partial-run state.

## Data-integrity, rollback, and prevention

- **Data integrity:** preserved; failed ThreatFox evidence and successful partial-run evidence remain persisted. No destructive recovery or public publication change occurred.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest approved follow-up:** validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; then deploy only under explicit recovery/deployment authorization using `./scripts/update-app.sh`.
- Verify the next run's failed-source status, bounded-response handling, monitor evidence, and publication/data integrity. Reconcile the missing operator `HERMES_MONITOR_EVIDENCE_FILE` export while retaining the container-mounted fallback. Investigate the internal-vs-monitor ops-route mismatch separately.
