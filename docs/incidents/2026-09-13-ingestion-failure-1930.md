# Production ingestion incident: bounded ThreatFox response failure (19:30Z)

- **Recorded:** 2026-09-13T19:33:30Z
- **Monitor state:** `actionable_failure`
- **Monitor evidence:** event `765284fe-05e5-4bc5-a8a7-a05db495e215`, observed `2026-09-13T19:30:33.014695+00:00`
- **Correlation:** `be7f4b6b-03e3-47f4-8cae-00ccbfbcb511`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial projection, but complete source coverage and full-success freshness are degraded.

PostgreSQL source-run evidence identifies `ThreatFox Recent Indicators (Abuse.ch)` as the sole failed source: status `failed`, item count `0`, retry count `0`, error classification `oversized_response`, detail `response exceeds 10485760 bytes`. Cause confidence is high: a deterministic provider/source response-size boundary failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- Application version is `0.1.0` per prior verified production evidence; running application image is `cti-hermes:local`, digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Repository is `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`; the working tree contains pre-existing unrelated/uncommitted changes. No source or application file was changed by this job.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy. Worker is an intentional one-shot container exited `0`; no restart loop or OOM kill is present. Restart counts are zero for inspected services.
- Monitor evidence and web logs show liveness, readiness, and run-status HTTP 200. Scheduler heartbeat is fresh. Direct PostgreSQL `pg_isready` reports accepting connections.
- Persisted migration revision is `0015_contradiction_lifecycle`; no pending/failed migration evidence was found. A Compose config validation attempt from this shell was blocked by missing protected production variables (`HERMES_SECRET_DIR`, `HERMES_IMAGE`), an environment limitation rather than a production failure.
- Host filesystem is 43% used with approximately 280G available; memory available is approximately 52GiB; host open-file limit is 4096. Container fd limits are 1024 with low current usage.
- Latest encrypted backup metadata is present for `/backups/hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes; checksum remains in protected metadata and is not reproduced.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no certificate outage observed.
- Projection counts: 31,107 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. No publication mutation was performed.

## Recovery gate and action

The recovery gate was re-read and acquired after cooldown expiry:

- Gate event: `765284fe-05e5-4bc5-a8a7-a05db495e215`
- Gate correlation: `be7f4b6b-03e3-47f4-8cae-00ccbfbcb511`
- Result: actionable evidence acquired
- Completion: `failed` because no safe reversible service action can remediate a deterministic provider response-size failure
- Recovery lock: verified absent after completion

No restart, retry, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Re-running unchanged ingestion would reproduce the provider boundary failure and risk another duplicate failed attempt.

The runtime audit also contains a later cooldown-suppressed event `5c69d794-b7c3-4272-b57b-b5f3f2406117` followed by an erroneous manual completion record created during gate verification; the actual acquired event above was separately completed, and the lock was verified absent. The audit log was not rewritten or deleted.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint against an offline fixture before deploying a focused source change. Retain the oversized-response regression fixture and partial-run visibility. Review the existing uncommitted `config/sources.json` change raising the ThreatFox limit before deployment; do not deploy it solely as recovery without verifying transport memory/disk limits and provider behavior. No rollback is required because this diagnostic job made no application or data mutation.
