# CTI-Hermes production ingestion failure diagnostic (07:47Z)

## Classification

- **Observed:** 2026-09-15T07:46:09.393776Z; diagnostic completed 2026-09-15T07:47:21Z.
- **Impact:** partial ingestion degradation. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox is stale; full-success and analyst/publication freshness remain stale.
- **Cause confidence:** high for the deployed ThreatFox response-size boundary; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No ingestion retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

`HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell. Per the deployed Compose configuration, evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before gate evaluation:

- `state=actionable_failure`
- `event_id=6a8c13ae-e184-4394-af1d-13157acac748`
- `observed_at=2026-09-15T07:46:09.393776+00:00`
- `correlation_id=c73a59a9-b9bf-4cfd-9604-be7dd5cab8fa`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

The monitor refreshed after gate evaluation. Post-check evidence remained `actionable_failure` at `2026-09-15T07:47:09.466831+00`, event `20368b30-b119-4ef8-aa71-11b06db6809c`, correlation `e324b0c2-9b82-4802-8d72-e0386637fef4`, same endpoint/status, and same run ID.

## Recovery gate

The shared 1,800-second cooldown and lock were evaluated before any recovery action. The gate acquired event `6a8c13ae-e184-4394-af1d-13157acac748` at `2026-09-15T07:46:37.497135+00Z`. This scheduled request authorizes diagnosis only, so it was completed with outcome `suppressed` at `2026-09-15T07:47:04.851291+00Z`. Audit read-back verified the event in `/runtime/recovery-events.jsonl` and `/runtime/recovery.lock` absent. No recovery action was attempted.

## Evidence collected

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and not modified.
- **Application/image:** application version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web/scheduler/monitor/backup started 2026-09-12; PostgreSQL started 2026-09-05.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, backup, and Caddy are running; web, scheduler, monitor, PostgreSQL, and backup report healthy; restart count 0. Worker is intentionally exited code 0 with `restart: no`; runtime-init is an old exited initialization container and not the ingestion owner. No relevant container events were found in the inspected window.
- **Health/readiness:** monitor observed internal run-status HTTP 200. Web logs show repeated successful `/health/live`, `/health/ready`, and `/api/v1/ops/run-status` requests. Scheduler heartbeat was present at `2026-09-15T07:47:12Z`. An attempted in-container curl probe was unavailable because curl is not installed; this does not contradict the successful internal health requests.
- **Ingestion/database:** PostgreSQL read-only connectivity succeeded. PostgreSQL 16.14; Alembic revision `0015_contradiction_lifecycle`; no pending/failed migration evidence. Latest run is `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- **Downstream:** report 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp `2026-09-11T22:24:37.163555+00Z`; latest relationship `2026-09-01T08:03:29.014597+00Z`.
- **Resources:** `/` is 43% used with 279G available; host has 52GiB available memory; open-file limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backups:** backup container healthy; `/backups/latest.metadata` identifies `hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes. Restore verification was not run.
- **Proxy/certificate:** Caddy is running and logs show successful local renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy or certificate cause indicated.
- **Configuration/deployment:** checked-out `config/sources.json` contains ThreatFox `max_response_bytes=52428800`, while the running failure proves the deployed boundary remains 10 MiB. Compose config validation could not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production failure evidence.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, worker, scheduler, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would reproduce the deterministic failure and was not attempted.

- **Service state:** web, scheduler, monitor, database, backup, and proxy healthy; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Action:** diagnosis only; recovery suppressed/completed by gate. No stack mutation.
- **Rollback:** not applicable; no application or data mutation occurred. Partial successful-source data and failed source records remain preserved.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review ThreatFox pagination/filtering or the bounded 50 MiB configuration, including decompression and memory impact; add or verify oversized-response regression coverage.
2. Run relevant tests, then deploy only through `./scripts/update-app.sh`; verify the next run, ThreatFox source status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in maintenance cron while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema; several legacy probes emitted harmless `relation does not exist`/column errors in PostgreSQL logs during diagnosis.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
