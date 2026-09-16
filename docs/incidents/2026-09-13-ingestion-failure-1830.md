# Production ingestion incident: bounded ThreatFox response failure (18:30Z)

- **Recorded:** 2026-09-13T18:31:20Z
- **Monitor state:** `actionable_failure`
- **Monitor evidence:** event `7171f7ff-7904-4074-b601-c1354496a397`, observed `2026-09-13T18:30:28.648847+00:00`
- **Correlation:** `ccbf5409-7fe6-4460-87f0-b161e85faeb4`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial projection, but complete source coverage and full-success freshness are degraded.

Database source-run evidence identifies `threatfox-recent-indicators-abuse-ch` as the sole failed source in run `5caec866-d2eb-51b1-905f-ecc8a66da107`: status `failed`, item count `0`, retry count `0`, error classification `oversized_response`, and detail `response exceeds 10485760 bytes`. The source remains enabled. Cause confidence is high: a deterministic provider/source response-size boundary failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- Application version: `0.1.0`; running image `cti-hermes:local`, digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Repository: `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`; working tree has pre-existing unexplained/uncommitted changes, including a `config/sources.json` change raising ThreatFox `max_response_bytes` to 52,428,800. That change is not deployed in the running image.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy. The worker is an intentional one-shot container exited `0`; no restart loop or OOM kill is present. Web/scheduler/monitor/backup were started 2026-09-12T12:55:15Z–12:55:21Z; PostgreSQL has been running since 2026-09-05T16:36:57Z.
- Health/readiness: monitor evidence shows run-status HTTP 200; web logs show repeated `/health/live`, `/health/ready`, and run-status HTTP 200 responses. PostgreSQL `pg_isready` reports accepting connections.
- Migration revision: `0015_contradiction_lifecycle` in `alembic_version`; no pending migration evidence observed. Compose configuration validation succeeded using the protected production environment and the currently running local image tag.
- Resource state: filesystem `/` is 43% used with approximately 280G available; memory available is approximately 52GiB; host open-file limit is `4096`.
- Backup: latest metadata is present and readable for `/backups/hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes; recorded SHA-256 is retained in protected metadata and not reproduced here.
- Certificate: Caddy logs show successful local renewal and reload for `hermes.cti.scogin.dev`; no certificate outage observed.
- Persistence projection counts: 31,107 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. No publication mutation was performed.

## Recovery gate and action

The recovery gate was acquired after re-reading the machine evidence. It recorded:

- Gate event: `7171f7ff-7904-4074-b601-c1354496a397`
- Gate correlation: `ccbf5409-7fe6-4460-87f0-b161e85faeb4`
- Gate result: actionable evidence acquired after cooldown expiry
- Recovery lock: acquired and then verified released
- Completion outcome: `failed` — no safe reversible service action could remediate a deterministic provider response-size failure
- Audit note: the attempted record retained correlation `ccbf5409-7fe6-4460-87f0-b161e85faeb4`; the completion record used refreshed monitor correlation `7c219c3d-0f99-44fb-a824-0e696df536a3` because the monitor rewrote its snapshot during diagnosis. The gate event ID and run ID remained unchanged.

No restart, retry, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Restarting a healthy scheduler or re-running unchanged ingestion would not alter the provider response boundary and would risk another duplicate failed attempt.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint against an offline fixture before deploying the focused source change. Retain an oversized-response regression fixture and partial-run visibility. Review the existing uncommitted `config/sources.json` change before any deployment; do not deploy it solely as a recovery action without verifying transport memory/disk limits and provider behavior. No rollback is required because this diagnostic job made no application or data mutation. The next recovery evaluation must reacquire the gate and re-read machine evidence.
