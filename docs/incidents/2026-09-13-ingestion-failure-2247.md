# Production ingestion incident: ThreatFox response-size failure (22:47Z)

- **Recorded:** 2026-09-13T22:47:36Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `e107d421-b06f-4e97-89a7-aa903f77299f`
- **Observed at:** `2026-09-13T22:45:46.857920+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `7f3e6cfa-57c9-455b-a356-e02587b6f8ba`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Evidence refresh after gate completion:** `2026-09-13T22:47:46.981914+00:00`, event
  `b26f4d03-14a9-47ff-828c-fceffd157e70`, correlation
  `73175470-a651-4b28-b432-2aefcb4251bd`; state remained `actionable_failure`.

## Impact and cause

The latest ingestion attempt is failed but usable: 37 of 38 sources completed and
5,943 new documents were persisted. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial
projection, but complete source coverage and full-success freshness remain
degraded.

`threatfox-recent-indicators-abuse-ch` is the only failed source. Its source run
has status `failed`, item count `0`, retry count `0`, cache state `miss`, no HTTP
status, classification `oversized_response`, and detail `response exceeds
10485760 bytes`.

Cause confidence is **high**: a deterministic provider/source response-size
boundary failure. The running code enforces a 10 MiB ingestion limit while the
checked-in source entry has a 50 MiB `max_response_bytes` value; the database
record confirms the active failure at 10,485,760 bytes. There is no evidence of
a web, proxy, worker, scheduler, database, disk, certificate, backup,
migration, publication, or credential outage.

## Evidence and operational state

- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree had
  pre-existing changes and untracked files before this incident record. No
  application source, configuration, deployment, or data changes were made.
- Application version: `0.1.0`; running image tag `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
  created `2026-09-12T12:55:03.601753337Z`.
- Containers: monitor, web, scheduler, PostgreSQL, and backup running healthy;
  worker exited `0` by its intentional one-shot design and reports its generic
  post-exit `unhealthy` state. All listed CTI containers have restart count 0.
  Services started 2026-09-12T12:55:15Z–12:55:21Z.
- Web checks from scheduler container: `/health/live` HTTP 200,
  `/health/ready` HTTP 200 with configuration/database `ok`, and `/version`
  returned `0.1.0`. The scheduler's direct `/api/v1/ops/*` probes returned 404
  because those routes require the monitor's configured internal request
  context; the authoritative monitor evidence recorded the run-status check as
  HTTP 200.
- Scheduler heartbeat was fresh; scheduler health was healthy with no failing
  streak. Scheduler logs contain repeated `source collection failed` only;
  no crash or restart loop was observed. Docker events for the window showed
  health-check execs only and no CTI container restarts.
- PostgreSQL reported accepting connections. Migration revision is
  `0015_contradiction_lifecycle`; no pending or failed migration evidence was
  observed. Database contains 25 ingestion runs: 2 completed and 23 failed.
  Latest failed run completed at `2026-09-13T02:00:07.87346Z`; latest completed
  run completed at `2026-09-11T12:06:50.050468Z`.
- Persistence remains populated and referentially intact by successful bounded
  reads: 31,107 source documents, 186 reports, 201 publications, 378
  detections, 201 hunts, and 201 remediations. No persistence mutation was
  performed.
- Host resources: root filesystem 43% used with approximately 280G available;
  52 GiB memory available; open-file limit 4096. Docker reported no resource
  pressure requiring cleanup.
- Backup: backup container healthy; latest encrypted backup metadata identifies
  `/backups/hermes-20260913T125518Z.dump.enc`, completed
  `2026-09-13T12:55:20Z`, 22,110,800 bytes, with a recorded SHA-256.
- Certificate state: Caddy logs show successful local certificate renewals and
  reloads for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate
  outage observed.
- Relevant configuration/deployment mtimes: running image created
  2026-09-12T12:55:03Z; `config/sources.json` 2026-09-12 19:24:50 -0500;
  `deploy/docker-compose.yml` 2026-09-10 21:03:21 -0500;
  `config/settings.yaml` 2026-08-26 20:15:28 -0500.

## Recovery gate and action

The authoritative evidence was read from `/runtime/monitor-evidence.json` inside
the running monitor container. The recovery gate was acquired after its
30-minute cooldown and lock checks, recording attempted event
`e107d421-b06f-4e97-89a7-aa903f77299f` with the evidence correlation and run IDs.
A second evaluation was correctly suppressed by the cooldown (event
`6d38bf6e-1fc9-42b9-af3c-b0c5e9327596`). The acquired attempt was completed with
outcome `failed`; the recovery lock was verified absent.

No restart, retry, deployment, migration, credential change, volume/data
 deletion, backup deletion, or publication mutation was performed. A restart
or blind retry cannot remediate a deterministic 10 MiB provider response-size
failure and would add load without improving coverage.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture. Reconcile the 50 MiB source configuration with the
active 10 MiB runtime boundary, validate transport memory/disk limits, and retain
an oversized-response regression fixture plus partial-run visibility before any
focused source change is deployed. The existing ThreatFox maintenance request
remains the remediation owner. No rollback is required because this diagnostic
made no application or data mutation; the incident record is the sole new
repository artifact.
