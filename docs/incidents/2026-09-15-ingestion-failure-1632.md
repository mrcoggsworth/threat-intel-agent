# Production ingestion incident: actionable partial-ingestion failure (16:32Z)

- **Diagnosis time:** 2026-09-15T16:31:57Z
- **Authoritative monitor evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`)
- **State:** `actionable_failure`
- **Event:** `cb18fac7-e9d8-4653-82ae-b48f53f30d1a`
- **Observed at:** `2026-09-15T16:33:47.830786+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `fbcb6ab9-aa12-4271-aee3-a569d660e1af`
- **Latest attempt run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, `stale_data`

## Repository and release

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; ahead of `origin/main` by 3
- Working tree: pre-existing modifications, deletions, and untracked files; no application code or deployment files were changed by this diagnosis except this incident record.
- Running image: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9`; application version `0.1.0` from persisted run metadata.
- Compose project environment file label: `/opt/cti-hermes/env/production.env`; active web config hash label: `38246532e1e6c2be7d9940a580146c11ca04e718be5bde65efb7ec28cd471c8f`.
- Migration revision: `0015_contradiction_lifecycle`; no pending/failed migration was observed from `alembic_version`.

## Evidence and impact

The latest scheduled run persisted `failed` after 37/38 sources succeeded and 13,108 new documents were written. The failed source remains stale. The latest five ingestion runs are failed with one source failure each. Current counts are 33,797 source documents, 186 reports, 201 report versions, and 201 publications. The monitor reports stale full-success freshness and an actionable latest-attempt failure. Partial-ingestion and failed-source records remain visible; no data-loss or persistence-integrity failure was observed.

Failed source: `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators (Abuse.ch)). Persisted source-run error is `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, with no HTTP status. Persisted source configuration is version 2 with `max_response_bytes=10485760`, last success `2026-09-11T12:06:49.272951Z`, last failure `2026-09-15T02:00:54.421527Z`, and seven consecutive failures. Checked-out `config/sources.json` has an undeployed 50 MiB limit change; it was not applied by this diagnosis.

## Service and platform checks

- Web, scheduler, monitor, backup, and PostgreSQL containers were healthy; all had restart count 0 and `OOMKilled=false`.
- Scheduler heartbeat was current: `/runtime/scheduler.heartbeat` contained `2026-09-15T16:32:15Z`.
- Web liveness/readiness/run-status checks returned HTTP 200 in container logs; monitor repeatedly reported the ingestion failure, not a liveness crash.
- PostgreSQL accepted connections; database size was 195 MB; PostgreSQL 16.14.
- Host capacity: root filesystem 43% used with 278G available; 49 GiB memory available; swap 1.8 MiB used; open-file limit 4096.
- Docker events in the observation window were health-check/exec events; no CTI service restart was observed.
- Latest backup metadata reports `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, with SHA-256 recorded in protected metadata; backup container healthy. Restore verification was not attempted.
- Caddy has the local certificate mounted for `hermes.cti.scogin.dev`; certificate expiry was not independently decoded in this run. No proxy/TLS symptom correlated with the ingestion failure.
- `docker compose config` from the cron environment could not interpolate protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator cron-export gap, not evidence of a running-stack crash.

## Gate and actions

The 1,800-second recovery gate was evaluated before any recovery action using the authoritative monitor evidence. Gate result: **suppressed**, event `9e68064f-4e2a-40bc-afdc-65d2d42e3d92`, reason `recovery cooldown is active`; the prior gate attempt was `cb2d9135-5a34-486e-bc72-7348b274cb5b` at `2026-09-15T16:02:14.707522+00`. No retry, restart, deployment, migration, credential change, database mutation, or destructive recovery was performed because the cooldown was active and this request authorizes diagnosis only.

## Diagnosis, rollback, and prevention

**Cause confidence: high.** The failure is source/provider-specific at the ThreatFox response-size boundary. No primary web, proxy, scheduler, database, disk, memory, file-descriptor, migration, backup, certificate, or credential cause was observed.

- Operational impact: ThreatFox freshness is stale and each scheduled run remains failed, while 37/38-source partial ingestion continues and persisted evidence remains available.
- Data-integrity state: no loss or constraint/integrity failure observed; failed evidence is preserved.
- Rollback: not applicable; no production application or data mutation occurred.
- Under explicit maintenance/deployment authorization, validate bounded/paginated ThreatFox retrieval or the checked-out 50 MiB configuration change, retain/add oversized-response regression coverage, then deploy only with `./scripts/update-app.sh`. Verify the next run, failed-source status, monitor evidence, full-success/usable status, and publication integrity.
- Reconcile cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, protected Compose variables, and operational query/schema drift. Separately verify encrypted-backup restoreability and independently decode certificate expiry.
