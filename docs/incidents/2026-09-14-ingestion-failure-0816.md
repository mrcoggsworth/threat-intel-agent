# Production ingestion incident: actionable failure, recovery cooldown suppression (08:16Z)

- **Recorded:** `2026-09-14T08:16:39Z`
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications/deletions and untracked files present; this incident record is the only file written by this diagnosis
- **Application/image:** version `0.1.0`, tag `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53-05:00`
- **Migration revision:** `0015_contradiction_lifecycle`; no pending/failed migration evidence observed from the database revision/readiness checks

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`, the configured Compose mount. The monitor refreshed while diagnosis was running; the latest recorded evidence was:

- **Monitor state:** `actionable_failure`
- **Event ID:** `cd8a15de-a33b-42b1-a66d-9bcfc5a25aee`
- **Observed at:** `2026-09-14T08:16:28.443056+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `31d118a3-2789-4584-831b-ad8f801bc8e6`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`)

## Diagnosis and impact

The `2026-09-14 02:00Z` ingestion run is failed but usable: 38 sources total, 37 successful, 1 failed, and 1,564 new documents persisted. The failed source is `threatfox-recent-indicators-abuse-ch` with `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The database source configuration still records `max_response_bytes=10485760`; checked-in `config/sources.json` adds a 50 MiB limit, so the running image/configuration is not reconciled.

Persisted public CTI remains available from successful-source and partial-run data, but complete source coverage and full-success freshness are degraded. Read-only database counts: 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334+00`), 186 reports (latest update `2026-09-11T22:24:37.163555+00`), and 201 publications (latest publication `2026-09-11T22:24:37.183379+00`). No evidence indicates corruption, data loss, or unauthorized publication mutation.

**Cause confidence: high.** Deterministic ThreatFox provider/source response-size boundary mismatch. Evidence does not support web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage as the primary cause.

## Service and operational evidence

- Web liveness/readiness returned HTTP `200` / `200`; monitor and scheduler requests succeeded. The scheduler heartbeat was `2026-09-14T08:16:33Z`.
- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy with restart count `0`; stack services have been up approximately 43 hours. Worker is a reserved one-shot service, exited `0`, with no restart loop.
- Monitor logs repeatedly report `last successful run stale, latest ingestion attempt failed`; scheduler logs show no scheduler exception.
- No CTI container restart or OOM event was observed in the two-hour event window.
- Root filesystem: 504 GiB total, 203 GiB used, 279 GiB available (43%). Memory: 62 GiB total, about 52 GiB available. Host open-file limit: 4096. No resource exhaustion indicated.
- PostgreSQL: `pg_isready` accepting connections; `current_database=hermes`, `current_user=hermes`; Alembic revision is `0015_contradiction_lifecycle`.
- Backup volume contains encrypted artifacts through `hermes-20260913T125518Z.dump.enc` plus metadata; no backup mutation occurred. `latest.metadata` was not populated in the read-only probe, so the latest artifact metadata path needs follow-up verification.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate failure indicated.
- Compose validation from this cron shell remains blocked by absent protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables; this was read-only and not treated as a service failure.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable evidence, with the 1,800-second cooldown and shared lock:

- **Gate event:** `cd8a15de-a33b-42b1-a66d-9bcfc5a25aee`
- **Gate result:** suppressed; `recovery cooldown is active`
- **Gate recorded at:** `2026-09-14T08:16:38.504576+00`
- **Lock read-back:** absent

No ingestion retry, service restart, deployment via `./scripts/update-app.sh`, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed. The gate audit was read back successfully and failed-source/partial-run evidence remains preserved.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved; 37 successful-source results, the failed ThreatFox evidence, and the partial-run documents remain persisted. No public publication mutation occurred.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible follow-up under explicit recovery authorization:** validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; then deploy using `./scripts/update-app.sh` and verify the next run's failed-source status, bounded-response handling, monitor evidence, and publication/data integrity.
- Reconcile the missing operator `HERMES_MONITOR_EVIDENCE_FILE` export while retaining the container-mounted fallback. Verify `latest.metadata` backup publication and investigate the internal-vs-monitor ops-route topology mismatch separately.
