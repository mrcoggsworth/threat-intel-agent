# CTI-Hermes production ingestion failure diagnostic (18:03Z)

- **Diagnosis time:** 2026-09-15T18:03:19Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **Monitor state:** `actionable_failure`
- **Event ID:** `1de3e449-46ba-40da-8f28-5ca8f89ed812`
- **Observed at:** `2026-09-15T18:01:53.925585+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `0eae4645-964c-4e4b-b45a-fcdf69c258b0`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch is ahead of `origin/main` by 3.
- Working tree: pre-existing modifications, deletions, and untracked files; this diagnostic changed only this incident record.
- Running image: `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Persisted application version: `0.1.0`.
- Migration revision: `0015_contradiction_lifecycle`.
- Last checked-in configuration change: pre-existing ThreatFox `max_response_bytes` increase from 10 MiB to 50 MiB; it is not deployed by this job.

## Impact and cause

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), classified as `oversized_response` with detail `response exceeds 10485760 bytes`. The source has repeated consecutive failures; no successful retrieval has been recorded since 2026-09-11T12:06:49Z. The latest five runs are failed with 37 successful and 1 failed source. Full-success freshness and report/publication freshness remain stale.

**Cause confidence: high.** This is isolated to the ThreatFox provider response-size boundary. Web, scheduler, monitor, PostgreSQL, disk, memory, file descriptors, migration state, backup, certificate, and persistence integrity are not indicated as primary causes.

## Operational evidence

- Web, monitor, scheduler, and PostgreSQL containers are running and healthy; inspect state showed `OOMKilled=false`, no restart loop, and no restart history change. The worker exited 0 three days ago and is not the active scheduled-ingestion path.
- Monitor heartbeat was fresh (`2026-09-15T18:03:16Z`). Scheduler logs had no entries in the inspected window; monitor logs repeatedly reported stale successful run/latest failed attempt.
- PostgreSQL 16.14 accepted connections; migration revision is `0015_contradiction_lifecycle`. A bounded query confirmed 26 failed and 2 completed ingestion runs; latest run is the failed run above. The first multi-query used plural table names and failed with `relation does not exist`; no data was modified.
- Internal web liveness from the web container returned HTTP 200. Host loopback port 8000 is not published, so host curls returned connection refused; this is expected topology, not evidence of web failure.
- Host capacity: root filesystem 43% used with 278G available; 49G memory available; swap negligible; open-file limit 4096.
- Backup container healthy; latest previously observed encrypted backup metadata was `hermes-20260915T125523Z.dump.enc`, completed 2026-09-15T12:55:26Z. Restore/checksum verification was not attempted.
- Caddy certificate for `hermes.cti.scogin.dev` was previously verified valid through `2026-09-16T03:39:23Z`; certificate/edge state is not the ingestion cause. No separate proxy container exists.
- `docker compose config` could not be interpolated from the cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This remains a maintenance-job configuration gap, not evidence of a running service outage.

## Recovery gate and actions

The shared recovery gate was evaluated before any recovery action against the authoritative evidence, with the 1,800-second cooldown and `/runtime` lock. The gate recorded attempted event `52c5aca7-682f-4f7a-920a-48f08cf41ee6`, correlation `2ef356a2-8a17-4911-b7a4-e3d075baa52c`, and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Recovery was not authorized by this diagnosis-only request; the event was completed with outcome `suppressed`. Read-back verified the recovery lock is absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, data integrity, rollback, and prevention

- **Impact:** one public source is stale; collection is partial; full-success and report/publication freshness are stale. Web liveness/readiness inside the deployment and database service remain healthy.
- **Data integrity:** preserved. Failed-source and partial-ingestion evidence remains persisted and visible; no volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no application or production-data mutation occurred.
- **Prevention:** under explicit maintenance/deployment authorization, validate bounded or paginated ThreatFox retrieval, add mocked oversized-response regression coverage, and deploy only via `./scripts/update-app.sh`. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`; separately verify encrypted-backup restoreability and investigate the internal-versus-host ops-route topology mismatch.
