# Production ingestion incident: actionable failure, recovery cooldown suppression (08:32Z)

- **Recorded:** `2026-09-14T08:32:50Z`
- **Repository/release:** branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** pre-existing modifications/deletions and untracked files were present before this record; no application source, deployment, configuration, database, or publication files were changed.
- **Application:** version `0.1.0`; running image tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; container image created `2026-09-12T07:54:53-05:00`.
- **Migration:** persisted Alembic revision `0015_contradiction_lifecycle`; no pending or failed migration evidence observed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container-mounted fallback was used: `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event ID:** `d0c5de21-8d37-4a1c-ad5c-0affad0862ac`
- **Observed at:** `2026-09-14T08:30:29.478505+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `9f30dd83-3089-4680-8d35-dfd23bccae4d`
- **Latest failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Signals:** `last successful run stale`; `latest ingestion attempt failed` (`1 source(s) failed`).

## Diagnosis and impact

The latest run started `2026-09-14T02:00:00.095941+00Z`, completed `2026-09-14T02:00:06.398193+00Z`, and is `failed` but usable: 38 sources, 37 successful, 1 failed, and 1,564 new documents. The failed source is `threatfox-recent-indicators-abuse-ch`: `status=failed`, `item_count=0`, `http_status=NULL`, `retry_count=0`, `cache_state=miss`, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The running database/source configuration remains at a 10 MiB response limit while checked-in `config/sources.json` contains the newer 50 MiB limit, indicating running-image/configuration drift.

Read-only database counts: 31,678 source documents (latest retrieval `2026-09-14T02:00:05.858334+00Z`), 186 reports (latest update `2026-09-11T22:24:37.183379+00Z`), 201 publications (latest publication `2026-09-11T22:24:37.183379+00Z`), 11 relationships, 378 detections, 201 hunts, and 201 remediation records. Public CTI from successful sources and the partial run remains available; complete source coverage and full-success freshness are degraded. No evidence of corruption, data loss, or unauthorized publication mutation was found.

**Cause confidence: high.** The evidence supports a deterministic ThreatFox provider/source response-size boundary mismatch, not a web, proxy, worker, scheduler, database, disk, memory, file-descriptor, certificate, backup, migration, or credential outage.

## Service and operational evidence

- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy with restart count `0`; services started around `2026-09-12T12:55Z`. Worker is a reserved one-shot container, exited `0` at startup, and is not a restart loop.
- Web liveness/readiness and monitor/scheduler requests returned HTTP `200`; scheduler heartbeat was `2026-09-14T08:31:33Z`. Monitor logs repeatedly report the same stale/full-success and latest-attempt failure; scheduler logs show no exception.
- No CTI container restart or OOM event was observed in the two-hour event window. Host root filesystem is 504 GiB total / 204 GiB used / 279 GiB available (43%); memory is 62 GiB total with about 51 GiB available; open-file limit is 4096. No resource exhaustion indicated.
- PostgreSQL 16.14 is accepting connections (`pg_isready`), with `current_database=hermes` and `current_user=hermes`; database size is 182 MB.
- Backup volume contains encrypted artifacts through `hermes-20260913T125518Z.dump.enc`; `/backups/latest.metadata` was populated and read back with artifact size 22,110,800 bytes and SHA-256 recorded in the metadata. No backup mutation occurred.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate failure indicated.
- `docker compose ... ps/config` validation from this cron shell was blocked by missing protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables. This is an operator-shell limitation, not evidence of a production outage.

## Recovery gate and actions

The recovery gate was evaluated after reading the actionable evidence with the configured 1,800-second cooldown and shared lock:

- **Gate result:** `allowed=false`; reason `recovery cooldown is active`
- **Gate decision identifiers:** event `d0c5de21-8d37-4a1c-ad5c-0affad0862ac`, correlation `9f30dd83-3089-4680-8d35-dfd23bccae4d`, run `3848465e-e2a0-572a-b522-4c768d790284`
- **Recovery state:** last attempt `2026-09-14T08:01:41.367026+00Z`; lock read-back `absent`
- **Recorded event:** suppressed by `scripts/recovery_gate.py`; no attempted recovery was authorized after the suppression.

No ingestion retry, service restart, `./scripts/update-app.sh` deployment, migration, credential change, response-limit change, volume/data deletion, backup deletion, or publication mutation was performed.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. Successful-source results, failed ThreatFox evidence, and partial-run documents remain persisted; public publications were not mutated.
- **Rollback:** not applicable; no application or data mutation was made.
- **Smallest reversible follow-up after a future permitted gate:** validate provider-side filtering/pagination or an alternate ThreatFox endpoint against an offline fixture; retain an oversized-response regression fixture; reconcile the running image with `config/sources.json`; deploy only with `./scripts/update-app.sh`; then verify source failure status, response-size handling, monitor evidence, and publication/data integrity.
- **Prevention:** reconcile the missing operator `HERMES_MONITOR_EVIDENCE_FILE` export while retaining the container fallback, verify backup metadata freshness in the next check, and investigate the internal-vs-monitor ops-route topology mismatch separately.
