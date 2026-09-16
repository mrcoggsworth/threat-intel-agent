# Production ingestion incident: actionable partial-run failure (20:30Z)

- **Recorded:** 2026-09-13T20:33:00Z
- **Monitor state:** `actionable_failure`
- **Monitor evidence:** event `96457f9a-86c9-4dcd-afdd-0cadc512d112`, observed `2026-09-13T20:30:37.269036+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `bf3e1d33-4fec-48f7-9757-848b5a307a73`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources succeeded and 5,943 new documents were persisted. The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial projection, but complete source coverage and full-success freshness are degraded.

PostgreSQL identifies `threatfox-recent-indicators-abuse-ch` as the sole failed source. Its source run has status `failed`, item count `0`, retry count `0`, cache state `miss`, no HTTP status, error classification `oversized_response`, and detail `response exceeds 10485760 bytes`. The same deterministic failure occurred in the preceding run; the prior full-success ThreatFox run returned 11,267 items. Cause confidence is high: a provider/source response-size boundary failure, not a web, proxy, worker, scheduler, database, disk, certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- Application version is `0.1.0`; running application image is `cti-hermes:local`, digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Repository is `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, ahead of `origin/main` by 3 commits with pre-existing unrelated working-tree changes. No application source was changed by this job.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running and healthy. Worker is an intentional one-shot container exited `0`; restart count is zero and no OOM kill or restart loop is present.
- Liveness, readiness, and the monitor's run-status check returned HTTP 200. Scheduler heartbeat was fresh at `2026-09-13T20:31:58Z`. Direct PostgreSQL `pg_isready` reports accepting connections; PostgreSQL is 16.14.
- Persisted migration revision is `0015_contradiction_lifecycle`; no pending or failed migration evidence was found.
- Compose inspection/config validation from this shell is blocked by missing protected production variables (`HERMES_SECRET_DIR`, `HERMES_IMAGE`); this is an operator-shell limitation, not evidence of a production outage.
- Host filesystem is 43% used with approximately 280G available; memory available is approximately 52GiB; host open-file limit is 4096. Container fd limits are 1024 with low observed usage.
- Latest encrypted backup metadata is present for `/backups/hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes; checksum remains protected and was not reproduced.
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; no certificate outage was observed.
- Projection counts are 31,107 source documents, 186 reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships. No publication mutation was performed.
- Latest deployment/config evidence: Compose and update script mtimes are 2026-09-10; the working-tree `config/sources.json` change adds `max_response_bytes: 52428800` for ThreatFox but is not deployed in the running image, whose recorded run configuration hash is `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

## Recovery gate and action

The recovery gate was acquired after monitor evidence validation and cooldown evaluation:

- Gate event: `96457f9a-86c9-4dcd-afdd-0cadc512d112`
- Gate correlation: `bf3e1d33-4fec-48f7-9757-848b5a307a73`
- Result: actionable evidence acquired
- Completion: `failed`, because no safe reversible service action can remediate a deterministic provider response-size failure
- Recovery lock: verified absent after completion

No restart, retry, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed. Re-running unchanged ingestion would reproduce the provider boundary failure and risk another duplicate failed attempt.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint against an offline fixture before deploying a focused source change. Retain the oversized-response regression fixture and partial-run visibility. Review the existing open maintenance request `maintenance-request-threatfox-2026-09-13.json`; reconcile its proposed 50 MiB limit with the active 10 MiB runtime limit and validate transport memory/disk bounds before deployment. No rollback is required because this diagnostic job made no application or data mutation.
