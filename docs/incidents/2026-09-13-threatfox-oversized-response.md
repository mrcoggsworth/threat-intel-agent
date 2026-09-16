# Production ingestion incident: ThreatFox bounded response failure

- **Observed:** 2026-09-13T01:46:16.389331+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `4656147d-06bc-46d7-b010-d0c842938da6`
- **Correlation:** `8c6b675f-189f-46b2-bbfd-8c352d951968`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The latest daily collection remains `failed`: 37 of 38 sources completed,
12,787 new documents were persisted, and the ThreatFox Recent Indicators
(Abuse.ch) source failed. The latest full-success run is the prior run
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11T12:06:50.050468Z.
The latest publication is 2026-09-11T22:24:37.183379Z (201 publications).
Partial successful evidence is preserved; no database reset or evidence deletion
occurred.

## Diagnosis

High confidence: deterministic source-level bounded-ingestion failure, not a web,
proxy, worker, scheduler, database, disk, certificate, backup, migration, or
configuration outage. Database evidence records source `threatfox-recent-indicators-abuse-ch`
with status `failed`, no HTTP status, zero items, zero retries,
`error_classification=oversized_response`, and `response exceeds 10485760 bytes`.
The run application version is `0.1.0` with configuration hash
`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

## Verification and actions

- Recovery gate acquired at 2026-09-13T01:47:04.347703Z for the monitor event,
  then completed with outcome `failed` at 2026-09-13T01:49:37.789364Z; the
  recovery lock was verified absent. No retry, restart, deployment, migration,
  response-limit change, credential change, or data mutation was performed.
- Web liveness and readiness returned HTTP 200; readiness reported database and
  configuration `ok`. PostgreSQL was healthy and `pg_isready` succeeded.
- Monitor, web, scheduler, backup, and PostgreSQL containers were healthy/running
  with restart count 0; the worker was intentionally reserved/exited 0.
- Scheduler heartbeat was fresh at 2026-09-13T01:48:50Z. Host disk was 42% used
  with 280G available; memory pressure was not indicated; open-file limit was
  4096. Docker events showed only diagnostic execs, not service restarts.
- PostgreSQL migration revision is `0015_contradiction_lifecycle` (head).
  Backup metadata exists through 2026-09-12T12:55:18Z; encrypted backup contents
  were not opened. Certificate files are managed by the Caddy certificate mount;
  no certificate mutation was performed.

## Follow-up

Treat the ThreatFox payload-size change as a source/provider maintenance item:
validate a bounded pagination, alternate endpoint, or provider-side filter in a
fixture before changing the 10 MiB safety limit. Preserve partial-run and
source-error evidence, and add a regression fixture for the oversized response.
Until then, the scheduler and monitor should continue surfacing the failure
without automatic retries that would reproduce it.

## Rollback / recovery state

No application or data change was made, so no rollback is required. Persistent
data, backups, migrations, and public CTI evidence remain intact.
