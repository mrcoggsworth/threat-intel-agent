# CTI-Hermes actionable ingestion failure diagnostic (15:31Z)

- **Diagnosis time:** 2026-09-15T15:32:00Z
- **Authoritative evidence source:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured container fallback was used.
- **Monitor state:** `actionable_failure`
- **Monitor event:** `e40b0605-5e81-4334-9c25-d17cf908e18f`
- **Monitor observed at:** `2026-09-15T15:30:43.272342+00:00`
- **Monitor correlation:** `0af38466-0af6-4127-8c35-ce03daf8a0d9`
- **Post-check evidence:** event `38c8d98b-399a-40bc-9809-2b1391253d7a`, observed `2026-09-15T15:33:43.487674+00:00`, correlation `35c3602f-cabd-4a76-abad-1bf05909c677`, same actionable state and run; recovery lock absent.
- **Latest attempt run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Latest-attempt signal:** run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, state `actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76` (ahead of `origin/main` by 3)
- Working tree: pre-existing modifications, deletions, and untracked files; this diagnosis added only this incident record.
- Running application image: `cti-hermes:local`
- Running image label digest: `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`
- Persisted application version: `0.1.0`
- Database migration revision: `0015_contradiction_lifecycle`
- Containers started 2026-09-12T12:55Z; PostgreSQL started 2026-09-05T16:36Z. Web, scheduler, monitor, backup, and PostgreSQL restart counts are 0; OOMKilled is false.

## Impact and pipeline state

The latest scheduled run completed 37 of 38 sources and persisted status `failed`; it ingested 13,108 new documents. The failed source is not fresh. The latest five persisted runs are all `failed` with 37 successful and 1 failed source. No usable/full-success run is evidenced in that window; the monitor marks the full-success projection stale. Current projections are: 33,797 source documents (latest retrieval `2026-09-15T02:00:54.267448Z`), 186 reports, 201 report versions, and 201 publications. Report/version/publication freshness is `2026-09-11T22:24:37.163555Z`. Partial ingestion and failed-source evidence remain persisted; no data loss was found.

## Diagnosis and evidence

- Failed source: `threatfox-recent-indicators-abuse-ch` / ThreatFox Recent Indicators (Abuse.ch).
- Latest source-run status: `failed`; `error_classification=oversized_response`; detail `response exceeds 10485760 bytes`; HTTP status unavailable.
- Persisted source configuration: version 2, `max_response_bytes=10485760`, last successful retrieval `2026-09-11T12:06:49.272951Z`, last failure `2026-09-15T02:00:54.421527Z`, seven consecutive failures.
- The checked-out but undeployed `config/sources.json` has a pre-existing `max_response_bytes=52428800` change. It was not deployed or modified by this diagnosis.
- Web and monitor readiness are healthy from the private Docker network: `/health/live` and `/health/ready` returned HTTP 200; readiness checks reported configuration and database `ok`.
- Scheduler heartbeat was current at `2026-09-15T15:32:15Z`. Scheduler and monitor logs show repeated failed freshness checks and `source collection failed`, with no restart loop or sampled traceback.
- PostgreSQL 16.14 accepted connections; database size is 195 MB. No pending/failed migration was observed; `alembic_version` is at `0015_contradiction_lifecycle`.
- Host capacity: root filesystem 43% used with 278G available; 49G memory available; swap use 1.8 MiB; open-file limit 4096. Docker events in the observation window were health-check `exec_*` events, not container restarts.
- Backup container is healthy. Latest metadata points to `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, with a recorded SHA-256. Encrypted restore/checksum verification was not attempted.
- Caddy certificate state: local-authority certificate for `hermes.cti.scogin.dev`, valid `2026-09-15T07:39:23Z` through `2026-09-15T19:39:23Z`; no renewal failure was observed. This is not the ingestion cause.
- Compose validation from the cron environment could not interpolate the production Compose file because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables are not exported in this job. Running containers use the persisted Compose project and are healthy; this is an operational cron/configuration gap, not evidence of a production service crash.

**Cause confidence: high.** This is a recurring provider/source response-size failure at the ThreatFox/Abuse.ch boundary. Web, proxy/edge, worker/scheduler liveness, PostgreSQL, disk, memory, file descriptors, migration, backup, certificate renewal, and persistence integrity are not indicated as primary causes.

## Recovery gate and actions

The shared recovery gate was evaluated before any recovery action with a 1,800-second cooldown and shared lock. The current gate evaluation acquired event `39978919-d81c-4480-9548-19f4f0793819`, correlation `991ef082-253b-46cb-b2d7-557d805113e2`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`; it was completed with outcome `suppressed` because this scheduled request authorizes diagnosis only. Read-back verified `/runtime/recovery.lock` is absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, integrity, rollback, and prevention

- **Service:** web and database healthy; scheduler heartbeat current; collection freshness degraded for one source; full-success and analyst/publication freshness stale.
- **Data integrity:** preserved. Failed-source and partial-ingestion records remain visible; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no application or production-data mutation was made.
- **Prevention:** under explicit maintenance/deployment authorization, validate bounded/paginated ThreatFox retrieval or the existing 50 MiB configuration change, add oversized-response regression coverage, then deploy only with `./scripts/update-app.sh`. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables. Separately verify encrypted-backup restoreability and investigate the internal-versus-host ops-route topology mismatch.
