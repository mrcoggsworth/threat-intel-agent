# Production ingestion incident: recovery cooldown suppression (22:32Z)

- **Recorded:** 2026-09-13T22:32:40Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `acde054a-85b1-4f2a-83a7-addb90b02604`
- **Observed at:** `2026-09-13T22:30:45.824675+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `ce535fba-33ee-4ce3-bda4-2d22a3374743`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Follow-up evidence refresh:** `2026-09-13T22:32:45.949916+00:00`, event
  `61de77da-593f-46f8-8191-331bb5fc35df`, correlation
  `77decc85-7b69-4d14-af41-41b095c6018f`; state remained
  `actionable_failure` and the run remained unchanged.

## Impact and cause

The latest ingestion run is failed but usable: 37 of 38 sources succeeded and
5,943 new documents were persisted. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial
projection, but complete source coverage and full-success freshness remain
degraded.

`threatfox-recent-indicators-abuse-ch` is the sole failed source. Its source
run is `failed`, item count `0`, retry count `0`, cache state `miss`, no HTTP
status, error classification `oversized_response`, and detail `response exceeds
10485760 bytes`. Cause confidence is **high**: deterministic provider/source
response-size boundary failure. There is no evidence of a web, proxy, worker,
scheduler, database, disk, certificate, backup, migration, publication, or
credential outage.

## Evidence and operational state

- Repository HEAD: `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, three
  commits ahead of `origin/main`; pre-existing working-tree changes were not
  modified except for this incident record.
- Application version: `0.1.0`; running image: `cti-hermes:local`; services
  started 2026-09-12T12:55:15Z–12:55:21Z; monitor, web, scheduler, PostgreSQL,
  and backup restart counts are 0. Worker is an intentional one-shot exit 0
  and remains exited with its generic post-exit health state `unhealthy`.
- Monitor evidence is fresh and reports `full_success_freshness=stale_data` and
  `latest_ingestion_attempt=actionable_failure`. Web liveness and readiness
  returned HTTP 200; readiness reported configuration and database `ok`.
  Scheduler and monitor logs repeat source collection failure without a crash
  loop.
- PostgreSQL accepts connections (`pg_isready`); migration revision is
  `0015_contradiction_lifecycle`. No pending/failed migration evidence was
  observed. Database counts were 2 completed and 23 failed ingestion runs,
  with latest run at 2026-09-13T02:00:00Z.
- Host filesystem is 43% used with approximately 280G available; approximately
  52 GiB memory is available; open-file limit is 4096. No resource pressure was
  observed.
- Backup service is healthy and `/backups/latest.metadata` identifies encrypted
  backup `hermes-20260913T125518Z.dump.enc`, completed 2026-09-13T12:55:20Z,
  22,110,800 bytes, SHA-256 recorded in metadata.
- Caddy logs show successful local certificate renewals and reloads for
  `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate outage was
  observed.
- Relevant configuration mtimes: `deploy/docker-compose.yml`
  2026-09-10T21:03:21-05:00, `config/settings.yaml`
  2026-08-26T20:15:28-05:00, and `config/sources.json`
  2026-09-12T19:24:50-05:00.

## Recovery gate and action

The authoritative machine-readable evidence was read from
`/runtime/monitor-evidence.json` inside the monitor container. The recovery
gate was evaluated with its 30-minute cooldown and lock. It recorded suppressed
event `acde054a-85b1-4f2a-83a7-addb90b02604`, correlation
`ce535fba-33ee-4ce3-bda4-2d22a3374743`, because `recovery cooldown is active`.
The recovery lock was verified absent. No restart, retry, deployment,
migration, credential change, volume/data deletion, backup deletion, or
publication mutation was performed.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox
endpoint against an offline fixture before deploying a focused source change.
Retain the oversized-response regression fixture and partial-run visibility.
Reconcile the checked-in 50 MiB ThreatFox limit with the active 10 MiB runtime
boundary and validate transport memory/disk limits before deployment. The
existing ThreatFox maintenance request remains the remediation owner. No
rollback is required because this diagnosis made no application or data
mutation.
