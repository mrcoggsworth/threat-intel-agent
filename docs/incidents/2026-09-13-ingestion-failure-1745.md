# Production ingestion incident: recovery cooldown suppression (17:45Z)

- **Recorded:** 2026-09-13T17:46:20Z
- **Monitor state:** `actionable_failure`
- **Monitor evidence:** event `d1a7ccd3-0d2f-4951-85f8-8c869a9d79d4`, observed `2026-09-13T17:45:25.438375+00:00`
- **Correlation:** `5444ad7a-d90c-463f-8f54-01c658ed7b38`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources
succeeded. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
`2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial
projection, but source coverage and full-success freshness are degraded.

PostgreSQL source-run evidence identifies
`threatfox-recent-indicators-abuse-ch` as failed with
`error_classification=oversized_response` and
`error_detail=response exceeds 10485760 bytes`; it has zero items and zero
retries in run `5caec866-d2eb-51b1-905f-ecc8a66da107`. Cause confidence is high:
this is a deterministic provider/source response-size boundary failure, not a
web, proxy, worker, scheduler, database, disk, certificate, backup, or
migration outage.

## Evidence and operational state

- Application version endpoint returned `0.1.0` (private API).
- Running application image is `cti-hermes:local`, image digest
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Repository is at `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`; the
  working tree contains pre-existing changes and this incident record.
- Web, scheduler, monitor, PostgreSQL, and backup containers are healthy. Web,
  scheduler, monitor, and backup were recreated 2026-09-12T12:55:15Z–
  12:55:21Z; PostgreSQL has been running since 2026-09-05T16:36:57Z. The
  worker is an intentional one-shot service, exited 0 after startup, and is
  not a restart loop.
- Scheduler heartbeat was fresh at `2026-09-13T17:46:57Z`; private readiness,
  run-status, last-success, and version checks returned HTTP 200.
- PostgreSQL accepted connections with `pg_isready`; persisted migration is
  `0015_contradiction_lifecycle`, also reported as the image's migration head.
  The Alembic current check from the web container could not connect because
  its default localhost target is not the Compose PostgreSQL host; the direct
  PostgreSQL check is authoritative for connectivity and revision state.
- Host filesystem is 43% used with about 280G available; memory availability
  is about 52GiB; open-file limit is 4096.
- Latest encrypted backup metadata is present and healthy for artifact
  `/backups/hermes-20260913T125518Z.dump.enc`, completed 2026-09-13T12:55:20Z,
  22,110,800 bytes, with its recorded SHA-256 retained in the protected
  metadata (not reproduced here).
- Caddy logs show successful local certificate renewal and reload for
  `hermes.cti.scogin.dev`; no certificate outage was observed.
- Compose configuration validation succeeded with the protected production
  environment. No deployment, restart, migration, retry, credential change,
  volume/data deletion, or publication mutation was performed.

## Recovery gate and action

The recovery gate evaluated the required actionable evidence and recorded a
suppressed event:

- Gate event: `d1a7ccd3-0d2f-4951-85f8-8c869a9d79d4`
- Gate correlation: `5444ad7a-d90c-463f-8f54-01c658ed7b38`
- Gate result: suppressed because `recovery cooldown is active`
- Recovery lock: verified absent

No recovery was attempted. Re-running unchanged ingestion would reproduce the
same bounded provider failure, and no smaller safe reversible action is
available during the cooldown.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox
endpoint against an offline fixture before deploying a focused source change.
Retain the oversized-response regression fixture and partial-run visibility.
The certificate was renewed successfully; continue monitoring its next renewal
window. No rollback is required because this job performed no application or
data mutation. The next permitted recovery evaluation must reacquire the gate
and re-read machine evidence before any action.
