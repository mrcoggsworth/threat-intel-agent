# Production ingestion incident: persistent ThreatFox oversized response (23:47Z)

- **Recorded:** 2026-09-13T23:47:26Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `b4a0bd7e-1a0b-4c2d-9d96-376a114fa1af`
- **Observed at:** `2026-09-13T23:45:51.113759+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `e1f054b9-f05c-47cf-8c7b-53e451fe688a`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and cause

The latest ingestion run is failed but usable: 37 of 38 sources completed and the failed source is `threatfox-recent-indicators-abuse-ch`. Full-success freshness remains stale; the public CTI projection remains populated from prior and partial successful evidence. The failed source recorded `item_count=0`, `retry_count=0`, `cache_state=miss`, no HTTP status, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`.

Cause confidence is **high**: a deterministic provider/source response-size boundary failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, publication, or credential outage. The checked-in source configuration allows 50 MiB while the active runtime boundary rejects responses above 10 MiB; this mismatch is the likely reason the source continues to fail.

## Evidence and operational state

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; pre-existing working-tree modifications and untracked artifacts were present. No application source, configuration, deployment, or data changes were made.
- Application version/image: `0.1.0`, `cti-hermes:local`; running CTI containers use image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Monitor, web, scheduler, PostgreSQL, and backup containers are running healthy with restart count 0. The worker is an intentional one-shot container, exited 0, and is not a restart-loop signal.
- Web liveness and readiness returned HTTP 200; readiness reported configuration and database `ok`; `/version` returned `0.1.0`.
- PostgreSQL accepted connections; migration revision is `0015_contradiction_lifecycle`. Read-only queries report 25 ingestion runs: 2 completed and 23 failed. The latest failed run is the recorded run; the latest completed run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`.
- Host resources are not constrained: root filesystem is 43% used with about 280G available, memory reports 52 GiB available, and the open-file limit is 4096.
- Caddy logs show successful local certificate renewals and reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate outage was observed.
- No pending or failed migration, database connectivity, persistence-integrity, or Docker restart evidence was observed in the bounded checks.

## Recovery gate and action

The authoritative machine-readable evidence was read from `/runtime/monitor-evidence.json` inside the running monitor container. The recovery gate acquired the evidence after cooldown and lock checks, recording attempted event `b4a0bd7e-1a0b-4c2d-9d96-376a114fa1af` with the evidence correlation and run IDs. The attempt was completed with outcome `failed`; the recovery lock was verified absent. Prior cooldown suppressions remain recorded in the gate audit.

No restart, blind ingestion retry, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed. A restart or retry cannot remediate a deterministic response-size rejection and would add load without improving complete source coverage.

## Prevention and rollback

Reconcile the ThreatFox source configuration with the active response-size boundary only after validating provider-side filtering, pagination, or an alternate endpoint against an offline fixture. Preserve an oversized-response regression fixture and partial-run visibility. The existing ThreatFox maintenance request remains the remediation owner. No rollback is required because this diagnostic made no application or data mutation; this incident record is the only repository write.
