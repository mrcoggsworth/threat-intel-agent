# CTI-Hermes actionable ingestion failure diagnostic (17:33Z)

- **Diagnosis time:** 2026-09-15T17:33:34Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` (cron did not export `HERMES_MONITOR_EVIDENCE_FILE`)
- **Monitor state:** `actionable_failure`
- **Monitor event:** `f7bc65c7-29c7-4e19-bc74-33ed2d38cc48`
- **Observed at:** `2026-09-15T17:30:51.749667+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `68a4624f-e65b-451f-a4ee-0adb50d56b58`
- **Latest failed run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success projection:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, state `stale_data`
- **Post-check evidence:** event `e75d1882-6c09-4e5f-8227-25f818d79a5b`, observed `2026-09-15T17:34:52.026766+00:00`, correlation `3ee7f40e-0570-4d69-858e-890ec8f93988`, same actionable state and run; recovery lock absent.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76` (ahead of `origin/main` by 3)
- Working tree: pre-existing modifications, deletions, and untracked files; no unrelated files were changed by this diagnosis.
- Running image: `cti-hermes:local`, image label digest `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`
- Persisted application version: `0.1.0`
- Migration revision: `0015_contradiction_lifecycle`
- Last checked-in configuration change: pre-existing un-deployed `config/sources.json` change raising ThreatFox `max_response_bytes` from 10 MiB to 50 MiB.

## Impact and evidence

The latest scheduled run persisted `failed`, completing 37/38 sources and ingesting 13,108 new documents. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), with `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, HTTP status unavailable, and zero items. The source has seven consecutive failures; last successful retrieval was 2026-09-11T12:06:49.272951Z.

The latest five persisted ingestion runs are all failed with 37 successful and 1 failed source. There is no evidenced usable/full-success run in the monitor projection. Persisted projections remain: 33,797 source documents (latest retrieval 2026-09-15T02:00:54.267448Z), 186 reports, 201 report versions, and 201 publications. Report/version/publication latest timestamp is 2026-09-11T22:24:37.163555Z. Partial-ingestion and failed-source records remain visible; no data loss or persistence-integrity failure was found.

## Operational diagnosis

- Web, scheduler, monitor, PostgreSQL, and backup containers are running healthy with zero restarts and `OOMKilled=false`; all were started 2026-09-12T12:55Z except PostgreSQL, started 2026-09-05T16:36Z.
- Scheduler heartbeat was fresh at 2026-09-15T17:34:16Z. Monitor remained healthy but repeatedly reported the same stale-success/latest-failure condition. Docker event inspection showed health-check `exec_*` events only, not service restarts.
- PostgreSQL 16.14 is accepting connections; database size is 195 MB; no pending/failed migration was observed; `alembic_version` is `0015_contradiction_lifecycle`.
- Host capacity is healthy: root filesystem 43% used with 278G available, 49G memory available, negligible swap use, and open-file limit 4096.
- Backup container is healthy; latest metadata identifies `hermes-20260915T125523Z.dump.enc`, completed 2026-09-15T12:55:26Z, 24,823,024 bytes. Encrypted restore/checksum verification was not attempted.
- Caddy certificate for `hermes.cti.scogin.dev` is valid through 2026-09-16T03:39:23Z; certificate/edge state is not the ingestion cause. No separate `cti-hermes-proxy-1` container exists.
- `docker compose config` could not interpolate from this cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is a maintenance-job configuration gap, not evidence of a running service outage.

**Cause confidence: high.** The failure is isolated to the ThreatFox provider/source response-size boundary. Web, proxy/edge, scheduler liveness, worker state, database, disk, memory, file descriptors, migrations, backup, certificates, and persistence integrity are not indicated as primary causes.

## Recovery gate and actions

The shared gate was evaluated with a 1,800-second cooldown and lock before any recovery action. It recorded attempted event `2e360a06-922f-40b5-ac17-4909b6d6f0b4` with correlation `df428dc7-b1fd-4c9f-8e43-13250c25ae19` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, then recorded completion outcome `suppressed`. Read-back verified the recovery lock was absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, data integrity, rollback, and prevention

- **Impact:** one source remains stale; collection is partial; full-success and report/publication freshness are stale. Web/readiness and database service remain healthy.
- **Data integrity:** preserved. Failed evidence and partial-ingestion records remain persisted and visible; no volumes, backups, migration history, or public CTI conclusions were changed.
- **Rollback:** not applicable; no application or production-data mutation occurred.
- **Prevention:** under explicit maintenance/deployment authorization, validate bounded/paginated ThreatFox retrieval or the existing 50 MiB configuration change, add mocked oversized-response regression coverage, and deploy only through `./scripts/update-app.sh`. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`; separately verify encrypted-backup restoreability and investigate the internal-versus-host ops-route topology mismatch.
