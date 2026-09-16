# Production ingestion incident: ThreatFox oversized response, recovery suppressed (08:47Z)

- **Recorded:** `2026-09-14T08:47Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications, deletions, and untracked files were present; no application source, deployment, database, or publication files were changed by this diagnosis.
- **Application/image:** version `0.1.0`; running tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created `2026-09-12T07:54:53.392614948-05:00`.
- **Migration:** PostgreSQL reports Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence was found.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container-mounted fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `e1fcf719-ce71-4145-b4f7-c1f5db1f2ff6`
- **Observed at:** `2026-09-14T08:45:30.554182+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `b521f1f6-47bd-479c-89f5-45e5ee0e3736`
- **Failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).

## Diagnosis and impact

The latest scheduled run began at `2026-09-14T02:00:00.095941+00Z`, completed at `2026-09-14T02:00:06.398193+00Z`, and is failed but usable: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch` with `item_count=0`, no HTTP status, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The persisted source configuration remains `max_response_bytes=10485760`; the checked-in `config/sources.json` has a newer 50 MiB value, so the running image/configuration is drifted.

Persisted data remains available from successful sources and the partial run: 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334+00Z`), 186 reports (latest update `2026-09-11T22:24:37.163555+00Z`), 201 publications (latest publication `2026-09-11T22:24:37.183379+00Z`), 11 relationships, 378 detections, 201 hunts, and 201 remediation records. Complete source coverage and full-success freshness are degraded; no corruption, data loss, or unauthorized publication mutation was observed.

**Cause confidence: high.** The evidence supports a deterministic ThreatFox provider/source response-size boundary mismatch. It does not support web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage as the primary cause.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy with restart count `0`; CTI application containers started `2026-09-12T12:55Z`. The reserved worker exited `0` after startup and is not in a restart loop.
- In-container web liveness/readiness returned HTTP `200` with `{"status":"ok"}` and `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`. The guessed host port `127.0.0.1:8000` is not published; no outage is inferred from that host-local probe. The internal monitor endpoint returned HTTP `200` in the authoritative evidence.
- Scheduler heartbeat was current at `2026-09-14T08:47:03Z`; monitor logs consistently reported the same stale/full-success and latest-attempt failure. No scheduler exception was present in the sampled window.
- No CTI restart or OOM event was observed. Root filesystem is 504 GiB total / 204 GiB used / 279 GiB available (43%); memory has about 51 GiB available; host open-file limit is 4096.
- PostgreSQL 16.14 accepts connections; database is `hermes`; database size is 182 MB.
- Backup volume has encrypted artifacts through `hermes-20260913T125518Z.dump.enc`; `/backups/latest.metadata` exists, is 198 bytes, and was read back with SHA-256 `2fcd395805f4b234812650959585ac2013eb0f8025166e205d4883e74209a656`. The latest visible backup is from `2026-09-13T12:55:20Z`, so freshness follow-up is required but no backup mutation occurred.
- Caddy logs show successful local certificate renewal/reload for `hermes.cti.scogin.dev`; no certificate failure was indicated.
- Git commands reported a pre-existing malformed/non-monotonic `.git/objects/pack/._pack-...idx` auxiliary index warning; no reset or repair was performed.

## Recovery gate and actions

The recovery gate was evaluated **after** reading the actionable evidence, using the configured 1,800-second cooldown and shared lock.

- **Gate evaluation:** allowed; event `e1fcf719-ce71-4145-b4f7-c1f5db1f2ff6`, correlation `b521f1f6-47bd-479c-89f5-45e5ee0e3736`, run `3848465e-e2a0-572a-b522-4c768d790284`.
- **Gate audit:** `attempted` at `2026-09-14T08:46:02.313473+00Z`, then `completed` with outcome `suppressed` at `2026-09-14T08:46:37.932198+00Z` because this request authorizes diagnosis only and does not authorize recovery.
- **Lock read-back:** absent after completion.
- **No recovery mutation:** no ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. Successful-source results, partial-run documents, failed ThreatFox evidence, and existing publications remain intact.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible approved follow-up:** validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; deploy only through `./scripts/update-app.sh`; then verify source failure status, response-size handling, monitor evidence, and publication/data integrity.
- **Prevention work:** reconcile the missing operator `HERMES_MONITOR_EVIDENCE_FILE` export while retaining the container fallback; verify backup freshness/metadata publication; and investigate the internal-vs-monitor ops-route topology separately.
