# CTI-Hermes production ingestion failure diagnostic (18:33Z)

- **Diagnosis time:** 2026-09-15T18:33Z
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **Monitor state:** `actionable_failure`
- **Event ID:** `005fa0c6-a43c-45a3-8d75-c3693ade9303`
- **Observed at:** `2026-09-15T18:30:56.041666+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `e773569a-0c49-424a-9bdd-4371995d8b0b`
- **Run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Signals:** `full_success_freshness=stale_data`; `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch ahead of `origin/main` by 3.
- Working tree: pre-existing modifications, deletions, and untracked files; this diagnostic added this incident record only.
- Running image: `cti-hermes:local`; application containers have been up approximately 3 days with restart count 0. Persisted application version: `0.1.0`.
- Migration revision: `0015_contradiction_lifecycle`.
- Last relevant checked-in change: ThreatFox `max_response_bytes` increase from 10 MiB to 50 MiB remains uncommitted and is not deployed; the running database source configuration remains 10 MiB.

## Impact and cause

The latest persisted run is `failed`: 37/38 sources succeeded and 13,108 new documents were persisted. The failed source is `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators, Abuse.ch), classified as `oversized_response` with detail `response exceeds 10485760 bytes`. It has seven consecutive failures; its last successful retrieval was `2026-09-11T12:06:49.272951+00`. Full-success freshness and report/publication freshness remain stale. Existing source documents and partial-ingestion evidence remain preserved.

**Cause confidence: high.** This is a provider response-size boundary/configuration mismatch, not a web, proxy, worker, scheduler, database, storage, certificate, backup, or migration outage. The scheduler log records `source collection failed` at `2026-09-15T02:00:54.421653531Z`; the monitor continues to report the failed latest attempt and stale last full-success run.

## Operational evidence

- Web, monitor, scheduler, PostgreSQL, and backup containers are up/healthy; worker is exited 0 by design; all inspected CTI containers have restart count 0 and `OOMKilled=false`.
- Internal `/health/live` returned 200 and `/health/ready` returned `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`; the public HTTPS readiness endpoint also returned 200.
- PostgreSQL accepted connections. Latest run is failed with 38 total sources, 37 successful, 1 failed. Migration table reports `0015_contradiction_lifecycle`; no pending/failed migration evidence was found.
- Persistence remains coherent: 33,797 source documents; 186 reports, 201 report versions, and 201 publications. Latest report/publication timestamps remain `2026-09-11T22:24:37.163555+00`.
- Host capacity is healthy: root filesystem 43% used with 278G available; 49G memory available; open-file limit 4096. No OOM or restart loop observed.
- Scheduler heartbeat was fresh at `2026-09-15T18:32:46Z`.
- Backup container is healthy; latest encrypted backup is `hermes-20260915T125523Z.dump.enc` (24,823,024 bytes, metadata present, completed around 12:55Z). Restore/checksum verification was not attempted.
- TLS for `hermes.cti.scogin.dev` is valid through `2026-09-16T03:39:23Z`.
- `docker compose config` could not be validated from this cron environment because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. This is an operator-environment gap, not evidence of a running outage.

## Recovery gate and actions

The shared recovery gate was evaluated after reading the authoritative evidence, using the 1,800-second cooldown and `/runtime` lock. It returned `allowed=false`, `reason=recovery cooldown is active`, for event `005fa0c6-a43c-45a3-8d75-c3693ade9303`. The lock was absent on read-back. A subsequent monitor refresh at `2026-09-15T18:32:56.161769+00:00` remained `actionable_failure` with event `8e714e53-5bc7-496b-85c7-698354404a70`, correlation `c73535c4-ffd9-4973-a3cd-718b29a3f7b6`, and the same run ID. No retry, restart, deployment, migration, credential change, or destructive recovery was performed because this scheduled request authorizes diagnosis only.

## Service, data integrity, rollback, and prevention

- **Impact:** partial collection; ThreatFox is stale; full-success and report/publication freshness are stale. Web/readiness/database services remain healthy.
- **Data integrity:** preserved. Failed-source and partial-ingestion evidence remains persisted and visible; no volumes, backups, migration history, or public CTI conclusions changed.
- **Rollback:** not applicable; no production mutation occurred.
- **Prevention:** under explicit maintenance/recovery authorization, validate bounded or paginated ThreatFox retrieval, add/retain mocked oversized-response regression coverage, and deploy only through `./scripts/update-app.sh`. Reconcile the staged 50 MiB source configuration with the running image/database. Export `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` in the maintenance cron environment while retaining the container fallback. Separately perform encrypted-backup restore verification and investigate the internal-versus-host operations-route topology mismatch.
