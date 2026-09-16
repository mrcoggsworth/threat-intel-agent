# Production ingestion incident: gated recovery failed (23:17Z)

- **Recorded:** 2026-09-13T23:17:09Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `65afdb8f-5f89-417e-9cde-baea3701a130`
- **Observed at:** `2026-09-13T23:16:49.060350+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `eaed01c2-b75e-42a7-9981-1cb2cb8c5e50`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate result:** suppressed after the recorded failed attempt; cooldown active; lock absent

## Impact and diagnosis

The latest ingestion run is failed but usable: 37 of 38 sources succeeded and
5,943 new documents were persisted. The latest full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; public CTI remains available from the
partial projection, but complete source coverage and full-success freshness are
degraded.

The sole failed source is `threatfox-recent-indicators-abuse-ch`. The persisted
source run has status `failed`, item count `0`, retry count `0`, cache state
`miss`, no HTTP status, classification `oversized_response`, and detail
`response exceeds 10485760 bytes`. Cause confidence is **high**: deterministic
provider/source response-size boundary failure. There is no evidence of a web,
proxy, worker, scheduler, database, disk, memory, file-descriptor, migration,
publication, or backup outage.

## Operational evidence

- Repository is `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three
  commits ahead of `origin/main`, with pre-existing broad working-tree changes.
  This diagnosis made no source/configuration change.
- Application version is `0.1.0`; running image is `cti-hermes:local`.
  Monitor, web, scheduler, PostgreSQL, and backup containers are healthy with
  restart count 0 and no OOM termination. Worker is an intentional one-shot
  container exited 0.
- `/health/live`, `/health/ready`, and `/version` returned HTTP 200; readiness
  reported configuration and database `ok`; version reported `0.1.0`.
- PostgreSQL accepts connections. Alembic revision is
  `0015_contradiction_lifecycle`; ingestion status counts are 2 completed and
  23 failed. The latest run has 38 total sources, 37 successful, 1 failed,
  status `failed`, and completed at `2026-09-13T02:00:07.87346Z`.
- Host root filesystem is 43% used with approximately 280G available; memory
  available is approximately 52 GiB; open-file limit is 4096. No resource
  pressure was observed.
- Backup service is healthy; prior verified metadata identifies encrypted backup
  `hermes-20260913T125518Z.dump.enc`, completed at `2026-09-13T12:55:20Z`, with
  SHA-256 recorded. No backup mutation occurred.
- No service restart, deployment, migration, credential change, response-limit
  change, volume/data deletion, or publication mutation occurred.

## Recovery gate and action

The authoritative evidence was read from `/runtime/monitor-evidence.json` inside
the monitor container. The recovery gate recorded an attempted event
`11c71178-21cc-4b88-a35d-274c859ac97f` at `2026-09-13T23:16:23.037185+00Z`.
Read-only diagnosis found no safe reversible recovery action: retrying unchanged
ThreatFox collection would reproduce the deterministic oversized-response
failure. The attempt was completed with outcome `failed`. A subsequent gate
check recorded suppressed event `65afdb8f-5f89-417e-9cde-baea3701a130` at
`2026-09-13T23:17:09.385282+00Z` because the 30-minute cooldown was active.
The recovery lock was verified absent.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture; retain an oversized-response regression fixture and
partial-run visibility. Reconcile the checked-in 50 MiB source limit with the
active 10 MiB runtime boundary before any focused change. Deploy only after
focused tests and `./scripts/update-app.sh` verification. No rollback is needed
because no application or data mutation was performed.
