# Production ingestion incident: ThreatFox bounded-response failure (01:17Z)

## Classification

- **Recorded:** 2026-09-15T01:17Z
- **Impact:** ingestion is partially degraded. Latest scheduled run `20c8d81a-48e4-5215-8292-63a72ddac05d` failed after processing 37/38 sources and produced 12,831 new documents; successful source data remains usable, but no new full-success run or downstream publication freshness is established.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential change, evidence deletion, volume deletion, or backup mutation was performed.

## Authoritative monitor evidence

Read first from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`:

- `state=actionable_failure`
- `event_id=7083779e-d9bb-4e4b-ac90-88f8ab0d378f`
- `observed_at=2026-09-15T01:15:41.378877+00:00`
- `correlation_id=b8c48505-da6d-4b3e-bfe8-21ef4a03925d`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `20c8d81a-48e4-5215-8292-63a72ddac05d`, detail `1 source(s) failed`

## Recovery gate

The 30-minute cooldown and shared lock were evaluated against that evidence. The gate returned `allowed=false`, reason `recovery cooldown is active`, and recorded suppressed event `7083779e-d9bb-4e4b-ac90-88f8ab0d378f` at `2026-09-15T01:16:39.590394+00`. Read-back verified `/runtime/recovery.lock` is absent. No recovery action was authorized or attempted.

## Evidence collected

- **Release/deployment:** repository `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; running tag `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`. Application containers started 2026-09-12 with restart count 0. Working tree contains substantial pre-existing changes; no deployment/config update was run.
- **Runs/source:** latest run started `2026-09-14T18:32:12.667740+00` and failed `2026-09-14T18:33:07.628491+00`; database totals are 38 total, 37 successful, 1 failed, 12,831 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Last full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`.
- **Database/migrations:** PostgreSQL accepted `pg_isready`; Alembic revision `0015_contradiction_lifecycle`; authoritative schema is singular (`ingestion_run`, `source_run`). No migration execution or pending/failed migration evidence was observed.
- **Services:** monitor, web, scheduler, PostgreSQL, and backup are running and healthy with zero restarts. Worker is exited code 0 by design (`restart: no`) and is reserved for a later analysis phase. Scheduler heartbeat is fresh at 2026-09-15T01:16:39Z. Internal health/readiness/run-status checks returned HTTP 200.
- **Resources:** root filesystem 43% used with 279G available; host memory 62GiB total and 52GiB available; shell FD limit 4096. No resource exhaustion indication.
- **Backup:** latest metadata identifies encrypted artifact `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, with recorded SHA-256; restore verification was not run.
- **Certificate/proxy:** Caddy successfully renewed and reloaded the local certificate for `hermes.cti.scogin.dev`; no proxy or certificate failure observed.
- **Logs:** monitor continuously reports stale full-success and failed latest attempt. Scheduler has no useful output. PostgreSQL contains repeated failed operator diagnostic queries using plural/non-authoritative table names or wrong column names; these are query/schema-drift errors, not application transaction failures.
- **Compose validation:** host-side `docker compose ... ps` could not interpolate because the cron shell lacks production `HERMES_SECRET_DIR` and `HERMES_IMAGE`; direct Docker inspection verified the running stack instead. This is an operational evidence/configuration gap, not proof of a running-stack outage.

## Diagnosis and follow-up

The failure is source/provider-specific: the deployed implementation rejects a ThreatFox response larger than 10 MiB. The checked-out but undeployed `config/sources.json` contains the bounded 50 MiB adjustment noted by the preceding incident. Web, proxy, scheduler, worker, database, disk, certificate, and backup services are not indicated as causes.

Under explicit maintenance/deployment authorization, review the ThreatFox limit change and memory/decompression implications, run focused regression tests, then deploy only with `./scripts/update-app.sh`. Verify failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Export `HERMES_MONITOR_EVIDENCE_FILE`, provide the protected Compose environment to maintenance jobs, and use singular schema names in operational diagnostics.

**Rollback:** not applicable; no application or data mutation was performed. Recovery gate audit read-back succeeded and lock is absent.
