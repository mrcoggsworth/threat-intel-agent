# CTI-Hermes production ingestion failure diagnostic (03:02Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T03:02:54Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`, so the configured container fallback was used before further diagnosis.
- **Monitor state:** `actionable_failure`
- **Event ID:** `7a581ed1-9f77-4cc6-a686-74c16e54407a`
- **Observed at:** `2026-09-17T03:00:19.524479+00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `f491cfed-388a-4f6f-981f-3be26baa0aeb`
- **Run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Signal:** `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.

The recovery gate was evaluated against that evidence with the configured 1,800-second cooldown and shared `/runtime` lock. It returned `allowed=false`, reason `recovery cooldown is active`, for gate event `b4150250-2497-4ca0-b95a-26610e3f4565` at `2026-09-17T03:01:48.377567+00`. The secret-free suppression audit was read back and `/runtime/recovery.lock` was absent. No retry, restart, deployment, migration, credential change, or destructive recovery was attempted.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `3ff0e4a3ab431cff4160cf9da8e30e7ce494748a`; working tree was clean before this incident record.
- Running image: mutable `cti-hermes:local`, image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`, created `2026-09-15T20:53:43Z`.
- Application version: `0.1.0`.
- Database revision: `0015_contradiction_lifecycle`; local Alembic head is also `0015_contradiction_lifecycle`. No pending migration was indicated. A container-side `alembic current` check was not usable because the scheduler's database URL resolves to its own localhost, while PostgreSQL connectivity from the database container is healthy.
- Last deployment evidence: application containers started around `2026-09-15T20:53:55Z`. The last relevant checked-in configuration change is commit `3c03116`, which changed ThreatFox response sizing; no production configuration mutation was made during this diagnosis. Compose validation from the cron shell remains blocked by missing protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` exports.

## Impact and cause

The latest persisted run is terminal `failed`: 37/38 sources succeeded, 1 failed, 29,841 new documents, and zero new findings. The failed source is `krebs-on-security` (Krebs on Security), with `error_classification=content_type_error` and detail `response content type did not match source policy`; it returned no HTTP status or items. The source is enabled, `configuration_version=2`, `max_response_bytes=10485760`, last successful retrieval `2026-09-16T02:00:49.445479+00`, last failure `2026-09-17T02:00:01.710063+00`, and consecutive failure count `1`.

Cause confidence is **high** for an upstream/source-policy mismatch isolated to the Krebs response content type. The scheduler log only reports `source collection failed`; web, monitor, scheduler, backup, and PostgreSQL services are healthy, and no host resource exhaustion or crash/restart evidence was found. This is a partial-ingestion failure, not a database or persistence outage.

Operationally, 37-source partial coverage is available, but Krebs coverage is stale/unavailable and the run is not full-success. The latest full-success/usable persisted run is `2026-09-16T02:00:00Z`–`02:01:00Z`, with 38/38 sources successful and 27,818 new documents. Current persisted totals are 49,418 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. Source documents last advanced at `2026-09-17T02:00:53.466767+00`; reports/publications and analyst artifacts last advanced at `2026-09-11T22:24:37Z`.

## Service, integrity, and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running and healthy with restart count 0. The worker is exited with code 0 and is configured as a one-shot/non-restarting service; runtime-init is an old one-shot container.
- Web liveness/readiness and run-status checks returned HTTP 200 in monitor/web logs. Scheduler heartbeat was fresh at `2026-09-17T03:02:37Z`; monitor evidence continued updating.
- PostgreSQL 16.14 is accepting connections (`pg_isready` succeeded). The database is serving the expected `hermes` database/user. No migration or database connectivity failure was evidenced.
- Host capacity is healthy: root filesystem 43% used with 277 GB available, 51 GiB memory available, host open-file limit 4096, and no relevant container OOM/restart signal.
- Latest backup metadata identifies `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, 26,683,360 bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`. Restore verification was not attempted.
- Caddy logs show successful local-issuer certificate renewals for `matrix.scogin.dev` and `hermes.cti.scogin.dev`; certificate state is not the ingestion cause. The certificates are in a short renewal window and should be monitored separately.
- No Docker container events or restart-loop evidence was observed in the deployment window.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. No volumes, backups, migration history, failed evidence, partial source data, or public CTI conclusions were altered. The failed source record and partial run remain visible.
- **Actions taken:** authoritative evidence read, read-only service/database/host diagnostics, recovery-gate suppression audit, and creation of this incident record only.
- **Rollback:** not applicable; no production application mutation occurred. If a compatible source-policy fix is approved, deploy only through `./scripts/update-app.sh`; rollback is the prior verified image or reverting the focused source change and redeploying.
- **Prevention/follow-up:** under explicit maintenance authorization, inspect Krebs response headers/body against the source policy, add an offline content-type regression fixture, and implement the smallest compatible normalization/provider-specific policy correction. Then deploy with `./scripts/update-app.sh` and verify failed-source status, full-success/usable-run status, monitor evidence, and report/publication freshness. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` separately. Keep the existing failed-source classification and do not bypass source validation.
