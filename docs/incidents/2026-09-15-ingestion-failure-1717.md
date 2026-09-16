# Production ingestion incident: actionable partial-ingestion failure (17:17Z)

- **Diagnosis time:** 2026-09-15T17:17:19Z
- **Authoritative monitor evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was used)
- **State:** `actionable_failure`
- **Event:** `81d76c00-b2b6-40b8-bf6a-9fbae6838a18`
- **Observed at:** `2026-09-15T17:15:50.725657+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `602494e0-9308-4e09-8e38-bbfb0dc9386f`
- **Latest attempt run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, `stale_data`

## Repository and release

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; local branch ahead of `origin/main` by 3.
- Working tree: pre-existing modifications, deletions, and untracked files; not modified except for this incident record.
- Running image: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; application version `0.1.0`.
- Containers: web, scheduler, monitor, backup, and PostgreSQL running healthy; restart count 0 for each inspected CTI service; no restart/OOM evidence. CTI services started 2026-09-12T12:55Z; PostgreSQL started 2026-09-05T16:36Z.
- Migration revision: `0015_contradiction_lifecycle`; no pending/failed migration was observed from the database revision table.

## Impact and data integrity

The latest scheduled run persisted `failed`: 37/38 sources succeeded and 13,108 new documents were written. The failed source remains stale. The latest five persisted runs are failed with one source failure each. Current counts are 33,797 source documents, 186 reports, 201 report versions, and 201 publications; database size is 195 MB. Partial-ingestion and failed-source records remain visible. No data-loss or persistence-integrity failure was found.

## Diagnosis and evidence

- Failed source: `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators (Abuse.ch)).
- Persisted source-run error: `error_classification=oversized_response`, `response exceeds 10485760 bytes`; HTTP status unavailable.
- Source configuration is version 2 with `max_response_bytes=10485760`, last successful retrieval `2026-09-11T12:06:49.272951Z`, last failure `2026-09-15T02:00:54.421527Z`, and seven consecutive failures.
- The checked-out `config/sources.json` contains a pre-existing 50 MiB limit change, but it is undeployed and was not changed by this diagnosis.
- Web private-network `/health/live` and `/health/ready` returned HTTP 200 with database readiness `ok`. The monitor evidence endpoint returned HTTP 200. Host-local port 8000 is not published, so a host-local health probe failed as expected. Scheduler heartbeat file was current.
- Monitor logs repeatedly report `last successful run stale, latest ingestion attempt failed`; web logs show successful health/readiness and ops polling. No scheduler crash, proxy failure, or container restart was observed.
- PostgreSQL accepted connections; schema revision is `0015_contradiction_lifecycle`; database size is 195 MB.
- Host capacity was adequate: root filesystem 43% used with 278G available, 49G memory available, swap 1.8 MiB, and open-file limit 4096. Recent Docker events contained no service restart events.
- Latest backup: `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 recorded in backup metadata as `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`; backup container healthy. Restore verification was not attempted.
- Caddy logs show successful renewal of the local-authority certificate for `hermes.cti.scogin.dev`; certificate state is not the ingestion cause.
- Compose validation from this cron environment could not interpolate protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator cron-export gap, not evidence of a running-stack crash.

**Cause confidence: high.** The failure is source/provider-specific at the ThreatFox response-size boundary. No primary web, proxy, worker/scheduler liveness, database, disk, memory, file-descriptor, migration, backup, certificate, or credential cause was observed.

## Recovery gate and actions

The configured 1,800-second recovery gate and shared lock were evaluated before any recovery action. Gate event `53192268-3f09-4de2-b080-8d65bb7e1b82` was recorded as `suppressed` because `recovery cooldown is active`; correlation `8cdf12fa-d73c-4bcf-b9f5-b5ecd086d8b7`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Read-back verified `/runtime/recovery.lock` absent. No retry, restart, deployment, migration, credential change, database mutation, or destructive recovery was performed because this scheduled request authorizes diagnosis only. The gate audit is recorded in `/runtime/recovery-events.jsonl`.

## Rollback and prevention

- Rollback: not applicable; no production application or data mutation occurred.
- Under explicit maintenance/deployment authorization, validate bounded/paginated ThreatFox retrieval or the existing 50 MiB configuration change, including decompression/memory impact, retain an oversized-response regression fixture, and deploy only with `./scripts/update-app.sh`.
- Reconcile cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, protected Compose variables, and operational query/schema drift. Separately validate encrypted-backup restoreability and investigate the internal-versus-host ops-route topology mismatch.
