# Production ingestion incident: ThreatFox bounded-response failure (09:32Z)

## Classification

- **Recorded:** 2026-09-15T09:32Z
- **Impact:** ingestion is partially degraded. Latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` completed 37/38 sources and persisted 13,108 new documents, but is `failed`; full-success freshness is stale and analyst/report/publication outputs remain stale. The partial successful-source data remains available; no new full-success or publication run was produced.
- **Cause confidence:** high for the immediate source-boundary cause; low-to-medium for upstream ThreatFox payload growth.
- **Data integrity:** preserved. No retry, restart, deployment, migration, credential, database, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured container fallback was read first from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`.

- **State:** `actionable_failure`
- **Event:** `4afdd1da-353d-4cef-bc20-f6b40b1a0b4f`
- **Observed:** `2026-09-15T09:32:17.583061+00:00`
- **Correlation:** `449c9b1f-90c0-49a2-86a6-e43b5b48484f`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Full-success signal:** `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- **Latest-attempt signal:** `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared 1,800-second cooldown and `/runtime` lock were evaluated before any recovery action. The gate recorded a secret-free suppressed event for monitor event `6b180453-f365-45f7-85db-91bc382ce3e5`, correlation `6ac8e95e-36e9-4cdb-a63d-884dec8bc763`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` at `2026-09-15T09:31:32.189272+00`; reason `recovery cooldown is active`. Audit read-back verified the event and `/runtime/recovery.lock` is absent. This diagnosis-only request did not authorize recovery.

## Evidence collected

- **Release/deployment:** repository branch `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, running tag `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, application version `0.1.0`. Application containers started 2026-09-12T12:55Z with restart count 0. No update script or stack mutation was run. Working tree contains substantial pre-existing changes; checked-out `config/sources.json` adds `max_response_bytes=52428800` for ThreatFox, but the running source row remains 10 MiB. Git also reports a pre-existing non-monotonic auxiliary pack-index warning.
- **Ingestion/database:** latest run started `2026-09-15T02:00:00.049118+00` and completed `2026-09-15T02:00:54.439155+00`; status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. Persisted source state has `max_response_bytes=10485760`, last successful retrieval `2026-09-11T12:06:49.272951+00`, last failure `2026-09-15T02:00:54.421527+00`, and 7 consecutive failures. Configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- **Persistence/freshness:** PostgreSQL `/var/run/postgresql:5432` accepted connections; web readiness returned `200` with configuration/database `ok`. Alembic database revision is `0015_contradiction_lifecycle`, matching the image migration head; direct in-container Alembic current check could not connect because its CLI URL resolves to localhost, so migration CLI configuration drift remains a follow-up. Counts/latest created timestamps: `source_document` 33,797 / 2026-09-15T02:00:54Z; `report` 186, `report_version` 201, `publication` 201, `detection` 378, `hunt` 201, `remediation` 201 (all latest 2026-09-11T22:24:37Z); `relationship` 11 / 2026-09-01T08:03:29Z.
- **Services/readiness/restarts:** web, monitor, scheduler, backup, and PostgreSQL are running healthy with restart count 0. Worker is exited code 0 by design; runtime-init is exited code 0. Scheduler heartbeat was `2026-09-15T09:32:43Z`. Web live/readiness returned HTTP 200. Monitor and scheduler logs report the failed collection/stale success, not a crash loop.
- **Resources:** root filesystem is 43% used with 278G available; host memory is 62GiB total with 51GiB available; shell file-descriptor limit is 4096. No disk, memory, or descriptor exhaustion indication.
- **Backup/certificate/proxy:** latest backup metadata identifies `/backups/hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; no backup mutation or restore occurred. Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no proxy/TLS cause indicated.
- **Compose/configuration:** production Compose validation from the cron shell was blocked by missing protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables. This is maintenance-environment configuration drift, not evidence of an application outage; running containers remained healthy.

## Diagnosis and prevention

The failure is source/provider-specific: the deployed ThreatFox request exceeds the 10 MiB bounded transport limit. Web, proxy, worker, scheduler liveness, PostgreSQL, disk, memory, file descriptors, backup, certificates, and persistence integrity are not indicated as the primary cause. The smallest reversible follow-up, under explicit maintenance/deployment authorization, is to review the existing bounded 50 MiB change for decompression/memory impact, add or verify mocked oversized-response regression coverage, and deploy only through `./scripts/update-app.sh`. Verify the next run's ThreatFox status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Separately export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables for maintenance cron and correct the migration CLI database target.

- **Action:** diagnosis and gate bookkeeping only; recovery suppressed by cooldown. No service restart, retry, deployment, migration, or data mutation.
- **Rollback:** not applicable; no application or production data state changed. Gate lock is absent and failed/source records remain preserved.
- **Security:** no secrets were read into this record or chat; no credentials were changed.
