# CTI-Hermes production ingestion failure diagnostic (18:45Z)

- **Diagnosis time:** 2026-09-15T18:46Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **Monitor state:** `actionable_failure`
- **Event ID:** `6cea8807-d942-4b52-bc9c-c9dd5919afc1`
- **Observed at:** `2026-09-15T18:45:57.099490+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `0634771d-3809-4e6e-ad1b-a12fe0cdf635`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch ahead of `origin/main` by 3.
- Working tree has pre-existing modifications, deletions, and untracked files; this diagnostic added this incident record only.
- Running image: `cti-hermes:local`; web, scheduler, monitor, backup, and PostgreSQL containers are running approximately 3 days with restart count 0. Worker is exited 0 by design.
- Migration revision: `0015_contradiction_lifecycle`.

## Impact and cause

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), classified as `oversized_response` with detail `response exceeds 10485760 bytes`. It has seven consecutive failures; its last successful retrieval was `2026-09-11T12:06:49.272951+00`. Full-success freshness and report/publication freshness remain stale. Partial successful-source data and failed-source evidence remain preserved.

**Cause confidence: high.** This is a deterministic provider response-size boundary/configuration mismatch. The database source configuration remains `max_response_bytes=10485760`; no evidence indicates a web, proxy, worker, scheduler, database, disk, memory, descriptor, certificate, backup, or migration outage. Re-running unchanged ingestion would reproduce the provider failure.

## Operational evidence

- Container state: web/monitor/scheduler/backup/PostgreSQL healthy; worker exited 0; all inspected CTI containers restart count 0 and `OOMKilled=false`.
- Web logs show repeated liveness/readiness/run-status HTTP 200 responses. Scheduler log reports `source collection failed`; monitor repeatedly reports stale full-success plus failed latest attempt.
- Host capacity: root filesystem 43% used with 290791328 KiB available; 49 GiB memory available; shell open-file limit 4096. No restart loop or OOM evidence.
- PostgreSQL accepted connections; latest run is failed with 38 total sources, 37 successful, 1 failed. Alembic revision is `0015_contradiction_lifecycle`.
- Persistence counts: 33,797 source documents, 186 reports, 201 publications. No destructive operation or constraint bypass was performed.
- Latest encrypted backup metadata: `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, metadata SHA-256 recorded as `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`; restore verification was not attempted.
- Internal web liveness/readiness returned 200/200 with database and configuration checks OK. Host-published `127.0.0.1:18000/api/v1/ops/run-status` returned 404, consistent with the known internal-versus-host route mismatch; this does not explain the internal monitor failure.
- `docker compose config` was not runnable from this cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is an operator-environment gap, not evidence of a running outage.
- Certificate file was not available on the host path in this cron environment; prior service evidence showed the configured public certificate valid through `2026-09-16T03:39:23Z`. Revalidation was not possible here.

## Recovery gate and actions

The shared recovery gate was evaluated after reading the authoritative evidence with a 1,800-second cooldown and `/runtime` lock. It acquired gate event `b9f3df94-68a5-46ee-8f51-c1e4fcc1bf0a`, correlation `a9147bfe-992b-4f11-a112-4f9022c1961d`, and the evidence run ID above. Because this scheduled request authorizes diagnosis only, the gate was completed with outcome `suppressed`. Read-back verified `/runtime/recovery.lock` absent. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.

## Service, data integrity, rollback, and prevention

- **Impact:** partial collection; ThreatFox stale; full-success and report/publication freshness stale. Web/readiness/database services remain healthy.
- **Data integrity:** preserved. Failed-source and partial-ingestion evidence remain visible; no volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no production mutation occurred.
- **Prevention:** under explicit maintenance authorization, validate bounded or paginated ThreatFox retrieval, retain `oversized_response` classification, add mocked oversized-response regression coverage, reconcile the staged 50 MiB source configuration with the running image/database, and deploy only through `./scripts/update-app.sh`. Export `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` in maintenance cron while retaining container fallback. Separately verify encrypted-backup restoreability and correct the host/internal operations-route mismatch.
