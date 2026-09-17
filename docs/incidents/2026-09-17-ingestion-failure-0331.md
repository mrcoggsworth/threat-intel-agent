# CTI-Hermes production ingestion failure diagnostic (03:31Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T03:35Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the configured container fallback was used before further diagnosis.
- **Monitor state:** `actionable_failure`
- **Event ID:** `dbaa0a75-0096-4297-8b0a-6afba1b193f5`
- **Observed at:** `2026-09-17T03:31:21.733819+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `61e432fb-2321-4b48-9e84-da7082b832e4`
- **Run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Signal:** `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.

The recovery gate was evaluated against this evidence with the configured 1,800-second cooldown and shared `/runtime` lock. It returned `allowed=true` and recorded attempted event `54720002-3944-426d-894f-ec73f15b5e7c` at `2026-09-17T03:32:47.910426+00`. Because this is a diagnosis-only request, no recovery action was authorized. The gate was completed with outcome `suppressed` at `2026-09-17T03:34:50.024156+00`; read-back verified the completion audit record and `/runtime/recovery.lock` was absent.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `a5a527c405067136ff4a5cf22c80bf57f0cdd830`; the tree was clean before this incident record. The branch is three commits ahead of `origin/main`, containing prior incident records.
- Running image: mutable `cti-hermes:local`; container image ID was not reprinted in this check, and no image change was performed.
- Application version: `0.1.0` from the internal `/version` endpoint.
- Database migration revision: `0015_contradiction_lifecycle`; PostgreSQL reports the same Alembic revision. Migration history was not changed.
- Last deployment evidence from running container start times: web/scheduler started around `2026-09-15T20:53:55Z`; monitor around `20:54:01Z`. Compose validation from this cron shell remains blocked because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported. No deployment or configuration mutation was made.

## Impact and cause

The latest persisted run is terminal `failed`: 37/38 sources succeeded, 1 failed, 29,841 new documents, and zero new findings. The failed source is `Krebs on Security`, with `error_classification=content_type_error` and detail `response content type did not match source policy`; it returned no HTTP status or items. The source is enabled, configuration version `2`, `max_response_bytes=10485760`, last successful retrieval `2026-09-16T02:00:49.445479+00`, last failure `2026-09-17T02:00:01.710063+00`, and consecutive failure count `1`.

**Cause confidence: high.** Evidence points to an upstream/source-policy content-type mismatch isolated to Krebs. Scheduler logs report only `source collection failed`; web, proxy path used by the monitor, scheduler, monitor, backup, and PostgreSQL are healthy. This is a partial-ingestion failure, not a database or persistence outage.

Operational impact is 37-source partial coverage; Krebs coverage is stale/unavailable and the run is not full-success. Persisted totals are 49,418 source documents (latest retrieval `2026-09-17T02:00:53.466767+00`), 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Reports, publications, and analyst artifacts last advanced at `2026-09-11T22:24:37.163555+00` (reports/publications latest `updated_at`/`created_at`), so publication/analysis freshness is separately stale.

## Service, integrity, and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL are running and healthy with restart count `0` and `OOMKilled=false`. The worker is exited with code `0` by design (`restart: no`), though its one-shot health status is unhealthy; it is not the scheduled ingestion process.
- Internal application version returned successfully. Monitor/web logs show HTTP 200 liveness, readiness, and run-status responses. Scheduler heartbeat mtime was `2026-09-17 03:34:08Z`; monitor evidence continued updating through `03:31:21Z`.
- PostgreSQL 16.14 is accepting connections; Alembic revision is present and there are zero waiting locks. The first bounded query used an incorrect plural table name and failed harmlessly; corrected read-only queries confirmed the persisted run/source state above.
- Host capacity is healthy: root filesystem 43% used with 277 GB available, 51 GiB memory available, negligible swap use, and open-file limit 4096. No relevant OOM or restart-loop evidence was observed.
- Latest backup metadata identifies `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, 26,683,360 bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`. Restore verification was not attempted.
- Caddy certificate check from the web container showed a local-authority certificate valid `2026-09-16T23:39:23Z` through `2026-09-17T11:39:23Z`; this is a short renewal window and not the ingestion cause. No certificate mutation was performed.
- Docker events in the observation window showed health-check exec activity but no relevant CTI container restart or crash event. Unrelated host containers also emitted events and were excluded from the diagnosis.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. No volumes, backups, migration history, failed evidence, partial source data, or public CTI conclusions were altered.
- **Actions taken:** read authoritative monitor evidence, evaluated and completed the recovery gate as suppressed, performed read-only container/host/database/log diagnostics, and created this incident record. No retry, restart, deployment, migration, credential change, or destructive recovery was performed.
- **Rollback:** not applicable; no production application mutation occurred. If a compatible source-policy fix is approved, deploy only through `./scripts/update-app.sh`; rollback is the prior verified image or reverting the focused source change and redeploying.
- **Prevention/follow-up:** under explicit maintenance authorization, inspect Krebs response headers/body against the source policy, add an offline content-type regression fixture, and implement the smallest compatible normalization or provider-specific policy correction. Then deploy with `./scripts/update-app.sh` and verify failed-source status, full-success/usable-run status, monitor evidence, and report/publication freshness. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` separately. Preserve the existing failed-source classification and do not bypass source validation.
