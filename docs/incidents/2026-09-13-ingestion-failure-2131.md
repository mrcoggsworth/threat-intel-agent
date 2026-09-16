# Production ingestion incident: actionable partial-run failure (21:30Z)

- **Recorded:** 2026-09-13T21:31:34Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `c53e55eb-e645-4c9a-92a5-779534d9c4b6`
- **Observed at:** `2026-09-13T21:30:41.561878+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `c13a31bd-059e-45ec-97f1-4170e4af9c50`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Follow-up evidence refresh:** `2026-09-13T21:47:42.755466+00:00`, event `603a7f81-49f9-4c61-bd6c-2885922ed71a`, correlation `a531d912-8155-4eab-997d-e8f61c994bdf`; state and run remained unchanged.

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial projection, but complete source coverage and full-success freshness are degraded.

PostgreSQL identifies `threatfox-recent-indicators-abuse-ch` as the sole failed source. Its source run has status `failed`, item count `0`, retry count `0`, cache state `miss`, no HTTP status, error classification `oversized_response`, and detail `response exceeds 10485760 bytes`. The failure is consistent with the prior failed run and with the open maintenance request `maintenance-request-threatfox-2026-09-13.json`. Cause confidence is high: a provider/source response-size boundary failure, not a web, proxy, scheduler, database, disk, certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- Application version: `0.1.0`; running image: `cti-hermes:local`; Compose image digest label: `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`.
- Repository: `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, ahead of `origin/main` by 3 commits, with pre-existing unrelated working-tree changes. This job made no application-source or configuration changes.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy with restart count 0. The worker is an intentional one-shot container exited 0 at startup; no OOM kill or restart loop is present.
- Liveness, readiness, version, and authenticated run-status checks returned HTTP 200. Scheduler heartbeat was `2026-09-13T21:31:28Z`; monitor evidence was fresh. Scheduler logs show only `source collection failed`; monitor logs consistently report the same failed attempt and stale full-success projection.
- PostgreSQL `pg_isready` reports accepting connections; PostgreSQL is 16.14. Alembic revision is `0015_contradiction_lifecycle`; no pending/failed migration evidence was found. The initial schema-table query used an incorrect table name (`schema_version`) and was corrected to `alembic_version`; no data was changed.
- Host filesystem is 43% used with approximately 280G available; memory available is approximately 52GiB; host open-file limit is 4096 with 1,585 observed process file descriptors. CTI container memory use is low; no resource pressure is indicated.
- Latest encrypted backup metadata is present for `/backups/hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes. Backup checksum was not reproduced or exposed in this report.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate outage was observed.
- Projection counts: 31,107 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. No publication mutation was performed.
- Compose config validation succeeded when run with the protected production environment file and local image value. Last running deployment started 2026-09-12T12:55:15Z–12:55:21Z; no restart event was observed during this diagnosis.

## Recovery gate and action

The recovery gate validated the actionable monitor evidence but suppressed recovery because the 30-minute cooldown was active:

- Gate event: `c53e55eb-e645-4c9a-92a5-779534d9c4b6`
- Gate correlation: `c13a31bd-059e-45ec-97f1-4170e4af9c50`
- Result: `allowed=false`; `recovery cooldown is active`
- Recovery lock: verified absent
- Audit: suppressed event recorded in the runtime recovery event log

No restart, retry, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Re-running unchanged ingestion would reproduce the deterministic provider boundary failure and risk another duplicate failed attempt.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint against an offline fixture before deploying a focused source change. Retain the oversized-response regression fixture and partial-run visibility. Reconcile the checked-in 50 MiB ThreatFox limit with the active 10 MiB runtime limit and validate transport memory/disk bounds before deployment. No rollback is required because this diagnostic job made no application or data mutation. The existing open maintenance request remains the owner for remediation.
