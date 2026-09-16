# Production ingestion incident: actionable partial-run failure (21:33Z)

- **Recorded:** 2026-09-14T21:33:15Z
- **Repository:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree had broad pre-existing modifications/untracked files and was not changed by this diagnosis.
- **Monitor evidence:** read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`.
- **State:** `actionable_failure`
- **Monitor event:** `979504bf-9414-4862-b1f0-e74415d28353`
- **Observed at:** `2026-09-14T21:30:25.403185+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `7d9199f9-444b-4440-a7fe-055b449b4200`
- **Run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Impact and cause

The latest ingestion attempt is failed but usable: 37 of 38 sources succeeded, 1 source failed, and 12,831 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at `2026-09-11T12:06:50.050468Z`; complete-source freshness is stale. Public CTI remains available from the latest usable partial projection, but ThreatFox coverage is incomplete.

The failed source is `threatfox-recent-indicators-abuse-ch`: `failed`, 0 items, no HTTP status, 0 retries, cache `miss`, classification `oversized_response`, detail `response exceeds 10485760 bytes`. This is consistent with the same deterministic provider/source bounded-response failure observed in prior runs, not a web, proxy, scheduler, database, capacity, certificate, backup, or credential outage.

**Cause confidence: high.** The failure is source/provider response-size handling. A blind retry or raising the bound would not be a safe diagnosis-only action.

## Evidence and operational state

- **Application:** `0.1.0`; image tag `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- **Containers:** web, scheduler, monitor, PostgreSQL, and backup healthy; restart count 0; OOM false. Worker is intentionally reserved/exited 0 (`restart=no`), started 2026-09-12T12:55:15Z and exited 2026-09-12T12:55:16Z. No non-health-check container restart/start/die event was observed in the 2-hour window.
- **Health/readiness:** web `/health/live` 200 `{"status":"ok"}`; `/health/ready` 200 with configuration/database `ok`; `/version` 200 with `0.1.0`.
- **Database:** `pg_isready` accepts connections; Alembic revision `0015_contradiction_lifecycle`. Migration pending/failed enumeration was not independently available from the running image; readiness and revision show no observed migration blockage.
- **Persistence:** latest failed run has 38 total, 37 successful, 1 failed, and 12,831 new documents. Current bounded counts: source documents 32,890; reports 186; report versions 201; publications 201; detections 378; hunts 201; remediations 201; relationships 11.
- **Capacity:** root filesystem 43% used with 279G available; host memory 54G available; Docker CTI services are below 1% memory; host open-file limit 4,096. No resource pressure observed.
- **Backups:** backup service healthy; encrypted backup `hermes-20260914T125520Z.dump.enc` exists with mode 600 and metadata/latest pointer at 2026-09-14T12:55:23Z. No backup mutation/deletion occurred.
- **Certificate/proxy:** live TLS certificate for `hermes.cti.scogin.dev` is served by Caddy and valid from 2026-09-14T15:39:23Z through 2026-09-15T03:39:23Z. No proxy error evidence observed.
- **Deployment/config boundary:** CTI containers started 2026-09-12T12:55:15Z–12:55:21Z; Compose labels reference `/opt/cti-hermes/env/production.env`. No deployment, restart, migration, source-limit, credential, or configuration mutation was performed.

## Recovery gate and actions

The recovery gate was evaluated against the authoritative evidence with its 1,800-second cooldown and lock. It acquired event `2ea53b8a-5725-446b-94ce-346737af7555` at `2026-09-14T21:32:59.273371+00:00`, then was completed as `outcome=suppressed` at `2026-09-14T21:33:15.123216+00:00` because this request authorizes diagnosis only. The lock was verified absent. Gate correlation was `b6fd0261-5c8e-491e-8edd-fbd154248dd3`.

No ingestion retry, service restart, `scripts/update-app.sh` deployment, migration, response-limit change, credential change, volume/data/backup deletion, or publication mutation was performed. Evidence and partial-run records remain preserved and auditable.

## Prevention and rollback

Validate ThreatFox provider-side filtering/pagination or an alternate endpoint against an offline fixture; retain an oversized-response regression fixture and bounded transport limit; reconcile the checked-in source configuration with the active image only under explicit deployment authorization. No rollback is required because no application or data mutation occurred. A future approved fix should run focused tests, then `./scripts/update-app.sh`, and verify the next full-success/usable projections, source status, monitor evidence, and publication integrity.
