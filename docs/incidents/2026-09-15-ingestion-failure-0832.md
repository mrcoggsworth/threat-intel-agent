# CTI-Hermes production ingestion failure diagnostic (08:32Z)

## Classification

- **Observed:** 2026-09-15T08:31:13.113039Z; diagnostic completed 2026-09-15T08:33:56Z.
- **Impact:** partial ingestion degradation. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox is stale; full-success and analyst/publication freshness remain stale.
- **Cause confidence:** high for the deployed ThreatFox response-size boundary; low-to-medium for upstream payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before diagnosis:

- `state=actionable_failure`
- `event_id=26d34b97-086c-449e-9a82-378aca935e5d`
- `observed_at=2026-09-15T08:31:13.113039+00:00`
- `correlation_id=d5b406bb-978b-4848-b3bd-56466ac5203e`
- endpoint `http://web:8000/api/v1/ops/run-status`, status `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared 1,800-second cooldown and lock were evaluated before any recovery action. The gate recorded attempted event `7ea893f8-1dc8-4a28-8304-23f51027adce` at `2026-09-15T08:32:38.090379+00Z`, with correlation `4bf8aeb2-b5b4-412d-ac68-b78d84cb5d53`. Because this scheduled request authorizes diagnosis only, it was completed with outcome `suppressed` at `2026-09-15T08:32:52.485244+00Z`. Read-back verified both audit records and `/runtime/recovery.lock` absent. No recovery action was attempted.

## Evidence collected

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and not modified.
- **Application/image:** application version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; web/scheduler/monitor/backup started 2026-09-12; PostgreSQL started 2026-09-05.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, backup, and Caddy are running; Hermes services report healthy; restart count 0 and OOM false. Worker is intentionally exited code 0 with `restart: no`; runtime-init is an old exited initialization container and not the ingestion owner. No relevant CTI-Hermes restart events were found.
- **Health/readiness:** authenticated internal run-status HTTP 200; web liveness/readiness requests HTTP 200; scheduler heartbeat was current (`2026-09-15T08:33:12Z`-class runtime heartbeat). No web, proxy, or scheduler liveness failure was observed.
- **Ingestion/database:** PostgreSQL read-only connectivity succeeded; PostgreSQL 16.14; Alembic revision `0015_contradiction_lifecycle`; no application migration failure or pending-migration evidence. Latest run is `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`.
- **Run projections:** latest attempt is failed; latest full-success is completed run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` from 2026-09-11. No newer full-success projection was present. The authenticated run-status projection exposed `latest_attempt`, `latest_full_success`, and `latest_usable`.
- **Downstream:** report 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11. Latest report/publication timestamp `2026-09-11T22:24:37.163555+00Z`.
- **Resources:** `/` is 43% used with 278G available; host has 51GiB available memory; open-file limit 4096. No disk, memory, or file-descriptor exhaustion indication.
- **Backups:** backup container is healthy; latest metadata identifies `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Restore verification was not run.
- **Proxy/certificate:** certificate subject `matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt YE1, validity 2026-08-18 through 2026-11-16. No certificate expiry or proxy cause indicated.
- **Configuration/deployment:** checked-out `config/sources.json` contains ThreatFox `max_response_bytes=52428800`, while the running failure proves the deployed boundary remains 10 MiB. Compose config validation could not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production failure evidence.
- **Operational log noise:** PostgreSQL logs contain repeated failed ad-hoc diagnostic queries using nonexistent plural table names or wrong column names. These are schema-drifted operator probes, not application transaction failures; the authoritative singular-schema queries succeeded.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, worker, scheduler, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would reproduce the deterministic failure and was not attempted.

- **Service state:** web/scheduler/monitor/database/backup/proxy healthy; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Action:** diagnosis only; recovery gate attempted/completed with `outcome=suppressed`. No stack mutation.
- **Rollback:** not applicable; no application or data mutation occurred. Partial successful-source data and failed source records remain preserved.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review ThreatFox pagination/filtering or the bounded 50 MiB configuration, including decompression and memory impact; add or verify oversized-response regression coverage.
2. Run focused tests, then deploy only through `./scripts/update-app.sh`; verify the next run, ThreatFox status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in maintenance cron while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema to eliminate misleading PostgreSQL error noise.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
