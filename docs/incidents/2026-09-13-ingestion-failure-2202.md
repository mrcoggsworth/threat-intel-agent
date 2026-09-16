# Production ingestion incident: actionable partial-run failure (22:02Z)

- **Recorded:** 2026-09-13T22:02:28Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `27ac19cd-1e11-4984-98bf-6f4b0dc87995`
- **Observed at:** `2026-09-13T21:59:43.593729+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `ca299266-acc4-4213-ada6-d29d26fc13fc`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Follow-up evidence refresh:** `2026-09-13T22:02:43.814435+00:00`, event
  `8ba9382d-0f94-46f1-8664-06ca3c279d0d`, correlation
  `e65f033d-cc74-4f99-92b9-2a208a2c720d`; state remained
  `actionable_failure` and the run remained unchanged.

## Impact and cause

The latest persisted ingestion attempt is failed but usable: 37 of 38 sources
succeeded and 5,943 new documents were persisted. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial
projection, but complete source coverage and full-success freshness remain
degraded.

PostgreSQL identifies `threatfox-recent-indicators-abuse-ch` as the sole failed
source. Its source run is `failed`, item count `0`, retry count `0`, cache state
`miss`, no HTTP status, error classification `oversized_response`, and detail
`response exceeds 10485760 bytes`. Cause confidence is high: deterministic
provider/source response-size boundary failure. There is no evidence of a web,
proxy, worker, scheduler, database, disk, certificate, backup, migration,
publication, or credential outage.

## Evidence and operational state

- Repository `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, ahead of
  `origin/main` by 3 commits; pre-existing unrelated working-tree changes were
  not modified by this job.
- Application version previously reported by the private status projection:
  `0.1.0`; running image `cti-hermes:local`, image digest label
  `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running and
  healthy with restart count 0. The worker is an intentional one-shot container
  exited 0; its generic healthcheck is `unhealthy` after exit, with no restart
  loop or OOM kill.
- Monitor evidence is fresh and reports `full_success_freshness=stale_data` and
  `latest_ingestion_attempt=actionable_failure`. Web liveness/readiness returned
  HTTP 200 with database/configuration checks OK. Scheduler logs contain only
  `source collection failed`; monitor logs repeat the same two failure signals.
- PostgreSQL `pg_isready` accepts connections; migration revision is
  `0015_contradiction_lifecycle`. No pending or failed migration evidence was
  found. Compose config validation succeeded using the protected production
  environment file.
- Host filesystem is 43% used with approximately 280G available; memory
  available is approximately 52 GiB; open-file limit is 4096 with 1,454 observed
  process descriptors. No resource pressure is indicated.
- Backup container is healthy. Latest encrypted backup is
  `hermes-20260913T125518Z.dump.enc`, 22,110,800 bytes, with metadata present.
- Caddy logs show successful local certificate renewal and reload for
  `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate outage was
  observed.
- Last running deployment started 2026-09-12T12:55:15Z–12:55:21Z. No service
  restart event was observed during this diagnosis. Relevant configuration file
  mtimes: `deploy/docker-compose.yml` 2026-09-10T21:03:21-05:00,
  `config/settings.yaml` 2026-08-26T20:15:28-05:00, and
  `config/sources.json` 2026-09-12T19:24:50-05:00.

## Recovery gate and action

The recovery gate was evaluated against the authoritative monitor file at
`/runtime/monitor-evidence.json`. Cooldown had elapsed and the lock was absent,
so it recorded attempted event `f72c793c-6cbd-4f30-af63-b43a866c5377` with
correlation `511bb559-234c-434e-8f81-8eca5e8acc98`. No safe reversible recovery
exists for a deterministic oversized provider response, and ingestion retry was
not authorized; the attempt was completed with outcome `failed`. The recovery
lock was verified absent afterward.

No restart, retry, deployment, migration, credential change, volume/data
 deletion, backup deletion, or publication mutation was performed. Existing
 partial evidence and persisted documents were preserved.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint
against an offline fixture before deploying a focused source change. Retain the
oversized-response regression fixture and partial-run visibility. Reconcile the
checked-in 50 MiB ThreatFox limit with the active 10 MiB runtime boundary and
validate transport memory/disk limits before deployment. No rollback is required;
this diagnosis performed no application or data mutation. The existing ThreatFox
maintenance request remains the remediation owner.
