# Production ingestion incident: actionable partial-ingestion failure (16:04Z)

- **Diagnosis time:** 2026-09-15T16:04:06Z
- **Authoritative monitor evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`
- **State:** `actionable_failure`
- **Event:** `cb2d9135-5a34-486e-bc72-7348b274cb5b`
- **Observed at:** `2026-09-15T16:01:45.506438+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `70d0926e-17e6-43c6-927d-71e8dab49831`
- **Latest attempt run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success signal:** run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, `stale_data`

## Repository and release

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `c925cd5bbb1b2c872841205b90ea05ea4636da76`; ahead of `origin/main` by 3
- Working tree: pre-existing modifications, deletions, and untracked files; not modified except for this incident record.
- Running image: `cti-hermes:local`; application version `0.1.0`
- Containers: web, scheduler, monitor, backup healthy; PostgreSQL healthy; all reported restart count 0 and `OOMKilled=false`. CTI containers started 2026-09-12T12:55Z; PostgreSQL started 2026-09-05T16:36Z.
- Migration revision: `0015_contradiction_lifecycle`; no pending/failed migration was observed.

## Impact and data integrity

The latest scheduled run persisted `failed` after 37/38 sources succeeded and 13,108 new documents were written. The failed source remains stale. The latest five runs are all failed with one source failure each. Source documents: 33,797, latest retrieval `2026-09-15T02:00:54.267448Z`. Reports: 186; report versions: 201; publications: 201. Report/version/publication freshness is `2026-09-11T22:24:37Z`. Partial-ingestion and failed-source records remain visible; no data loss or persistence-integrity failure was found.

## Diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch` (ThreatFox Recent Indicators (Abuse.ch)).
- Persisted source-run error: `error_classification=oversized_response`, `response exceeds 10485760 bytes`; HTTP status unavailable.
- Persisted source configuration remains version 2 with `max_response_bytes=10485760`, last success `2026-09-11T12:06:49.272951Z`, last failure `2026-09-15T02:00:54.421527Z`, seven consecutive failures.
- Checked-out `config/sources.json` contains a pre-existing 50 MiB limit change, but it is undeployed and was not changed by this diagnosis.
- Web private-network liveness/readiness and run-status returned HTTP 200; scheduler heartbeat was current at diagnosis. PostgreSQL accepted connections and database size was 195 MB.
- Host capacity was adequate: root filesystem 43% used with 278G available, 49G memory available, swap 1.8 MiB, open-file limit 4096. Docker events were health-check executions, not restarts.
- Latest backup: `hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 recorded as `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`; backup container healthy. Restore verification was not attempted.
- Certificate: Caddy local-authority certificate for `hermes.cti.scogin.dev`, observed valid through `2026-09-16T03:39:23Z`; not the ingestion cause.
- Compose validation from this cron environment could not interpolate protected `HERMES_SECRET_DIR`/`HERMES_IMAGE`; this is an operator cron-export gap, not evidence of a running-stack crash.

**Cause confidence: high.** The failure is source/provider-specific at the ThreatFox response-size boundary. No primary web, proxy, worker/scheduler liveness, database, disk, memory, file-descriptor, migration, backup, certificate, or credential cause was observed.

## Gate and actions

The 1,800-second recovery gate and shared lock were evaluated before any recovery action. Gate event `cb2d9135-5a34-486e-bc72-7348b274cb5b` was recorded as `attempted` and completed with outcome `suppressed`; the lock read-back was absent. No retry, restart, deployment, migration, credential change, database mutation, or destructive recovery was performed because this scheduled request authorizes diagnosis only.

## Rollback and prevention

- Rollback: not applicable; no production application or data mutation occurred.
- Under explicit maintenance/deployment authorization, validate bounded/paginated ThreatFox retrieval or the existing 50 MiB configuration change, add/retain an oversized-response regression fixture, and deploy only with `./scripts/update-app.sh`.
- Reconcile cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, protected Compose variables, and operational query/schema drift. Separately validate encrypted-backup restoreability and investigate internal-versus-host ops-route topology.
