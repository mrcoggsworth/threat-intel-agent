# CTI-Hermes production ingestion failure diagnostic (02:17Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T02:17:53Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the configured container mount was used.
- **Monitor state:** `actionable_failure`
- **Event ID:** `287b2259-10c3-41c0-a592-25e98524a22e`
- **Observed at:** `2026-09-17T02:15:16.250521+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Correlation ID:** `9f086107-7e60-437f-82a0-78d77e396aa8`
- **Run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Signal:** `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.
- **Post-check evidence at `2026-09-17T02:18:16.471461+00:00`:** event ID `7ccec729-35a5-45b4-b094-d38248bfcd75`, correlation ID `a90f04ec-1c0d-486a-8b28-637b241095bc`, same run ID, endpoint HTTP 200, state still `actionable_failure`.

The recovery gate was evaluated after reading the actionable evidence with its configured 1,800-second cooldown and `/runtime` lock. It returned `allowed=true` and recorded attempted event `b0feec0f-f3dd-4174-934a-72a28fc9303a` at `2026-09-17T02:16:20.393398Z`. No collection, restart, deployment, migration, credential change, or destructive recovery was authorized by this diagnosis-only request. The gate was completed with outcome `failed` and reason `diagnosis-only request; no reversible recovery action attempted` at `2026-09-17T02:17:53.553688Z`; read-back verified the completion audit record and lock release.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `3c031166b88383d0c3662fb767b93241e693031e`; working tree was clean before this incident record.
- Running application image: mutable `cti-hermes:local`, image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`, created `2026-09-15 15:53:33 -0500`.
- Application version: `0.1.0`.
- Database migration revision: `0015_contradiction_lifecycle`; local migration set also ends at `0015`. No pending or failed migration was observed.
- Last deployment evidence: application containers started around `2026-09-15T20:53:55Z`; protected `/opt/cti-hermes/env/production.env` mtime `2026-09-10 18:42:11-05:00`. Compose config validation could not run in this cron shell because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` were not exported.

## Impact and cause

The latest persisted run is terminal `failed`: 37/38 sources succeeded, 1 failed, 29,841 new documents, and zero new findings. The failed source is `krebs-on-security` (Krebs on Security), with `error_classification=content_type_error` and detail `response content type did not match source policy`; it returned no HTTP status or items. The source was enabled, had `configuration_version=2`, `max_response_bytes=10485760`, `last_successful_retrieval=2026-09-16T02:00:49.445479Z`, `last_failure=2026-09-17T02:00:01.710063Z`, and `consecutive_failure_count=1`.

Cause confidence is **high** for an upstream/source-policy mismatch isolated to Krebs response headers/content type. The scheduler log contains only `source collection failed`; no application, database, or host failure was evidenced. This is a partial-ingestion failure, not a persistence outage.

**Operational impact:** 37-source partial coverage is available, but Krebs coverage is stale/unavailable and the run is not full-success. Source documents total 49,418 with latest retrieval `2026-09-17T02:00:53.466767Z`. Reports total 186 and publications total 201; both last advanced at `2026-09-11T22:24:37.183379Z`. Detections, hunts, remediation, and relationships remain persisted independently (378, 201, 201, and 11 respectively).

## Service, integrity, and operational evidence

- Web, scheduler, monitor, backup, and PostgreSQL containers are running and healthy with restart count 0 and `OOMKilled=false`. The worker is exited with code 0 by design (`restart: no`), and runtime-init is an old one-shot container.
- Web health/readiness checks returned HTTP 200 in monitor logs; scheduler heartbeat was fresh at `2026-09-17T02:16:07Z`. Monitor evidence continued updating. No crash or restart event was observed.
- PostgreSQL 16 is accepting connections; database size is 273 MB, 12 sessions, 1 active session, and 0 waiting locks.
- Host capacity is healthy: root filesystem 43% used with 277 GB available, 51 GiB memory available, negligible swap use, and open-file limit 4096.
- Latest encrypted backup metadata identifies `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, 26,683,360 bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`. Restore verification was not attempted.
- Certificate revalidation for `matrix-1.taild27e3c.ts.net:9444` succeeded: Let's Encrypt issuer `YE1`, valid through `2026-11-16T14:30:36Z`.

## Data integrity, rollback, and prevention

- **Data integrity:** preserved. No volumes, backups, migration history, failed evidence, partial source data, or public CTI conclusions were altered. The failed source record and partial run remain visible.
- **Actions taken:** read-only diagnosis, recovery-gate audit evaluation/completion, and creation of this incident record only.
- **Rollback:** not applicable; no production application mutation occurred. If a compatible source-policy fix is later approved, deploy only through `./scripts/update-app.sh`; rollback is the prior verified image/receipt or reverting the focused source change and redeploying.
- **Prevention/follow-up:** under explicit maintenance authorization, inspect Krebs response headers/body against the source policy, add an offline content-type regression fixture, and implement the smallest compatible normalization or provider-specific policy correction. Then deploy with `./scripts/update-app.sh` and verify the next run's failed-source status, full-success/usable-run status, monitor evidence, and publication freshness. Reconcile the missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE` separately.
