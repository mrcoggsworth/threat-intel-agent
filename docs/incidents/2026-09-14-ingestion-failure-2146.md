# Production ingestion incident: ThreatFox oversized response (21:46Z)

- **Recorded:** 2026-09-14T21:46:38.569604Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, image `cti-hermes:local`, application `0.1.0`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `96fc2fc1-3076-4109-b771-5107cf7b2e8d`
- **Observed at:** `2026-09-14T21:45:26.447166+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200` in authoritative monitor evidence
- **Monitor correlation:** `5b9b2ce1-670a-4e36-b1ff-84761a5a9835`
- **Latest failed run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Impact and diagnosis

The latest usable collection is incomplete: 38 sources were attempted, 37
succeeded, one failed, and 12,831 new documents were persisted. The latest
full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00`. Public CTI remains available from the partial
run, but full source coverage and full-success freshness are degraded.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its persisted
source-run record is `status=failed`, `error_classification=oversized_response`,
and `error_detail=response exceeds 10485760 bytes`, with `cache_state=miss` and
`item_count=0`. Cause confidence is **high**: a provider/source response-size
boundary mismatch, not a web, proxy, scheduler, database, resource,
certificate, backup, migration, publication, or credential outage.

## Evidence and operational state

- Latest run started `2026-09-14T18:32:12.667740+00`, completed
  `2026-09-14T18:33:07.628491+00`, status `failed`, 38 total / 37 successful /
  1 failed, application `0.1.0`, configuration hash
  `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- PostgreSQL is accepting connections; revision is
  `0015_contradiction_lifecycle`. The expected public schema is present and no
  pending migration evidence was found. An Alembic CLI status probe using the
  container's localhost default failed to connect and emitted the known
  asyncpg event-loop cleanup traceback; this is CLI configuration/hygiene, not
  database unavailability. The application readiness probe independently
  reports `database=ok`.
- Web, scheduler, monitor, backup, and PostgreSQL are running and healthy with
  restart count 0. The worker is an intentional one-shot container exited 0;
  no restart loop or OOM evidence was observed.
- Web `/health/live` returned HTTP 200 `{"status":"ok"}` and
  `/health/ready` returned HTTP 200 with configuration and database checks OK.
  A direct request to the monitor-recorded run-status route returned HTTP 404
  despite monitor evidence recording HTTP 200; this route/evidence discrepancy
  is a separate follow-up.
- Database projections: 32,890 source documents, latest at
  `2026-09-14T18:33:07.632571+00`; 186 reports, 201 report versions, and 201
  publications, all latest at `2026-09-11T22:24:37.163555+00`; 378 detections,
  201 hunts, and 201 remediations.
- Host state at `2026-09-14T21:46:59Z`: root filesystem 43% used with 279 GiB
  available; 54 GiB memory available; open-file limit 4096; load average
  0.20/0.29/0.37. No resource exhaustion indicated.
- Latest encrypted backup is `hermes-20260914T125520Z.dump.enc`, completed
  `2026-09-14T12:55:23Z`, 22,608,400 bytes; `latest.metadata` is present.
- Caddy is running with restart count 0. Recent logs show successful local
  certificate renewal and reload for `hermes.cti.scogin.dev`; no certificate
  expiry or renewal failure is indicated. The external proxy/TLS trust and
  routing path remains separate follow-up work.
- Last checked-in application commit is `c925cd5`; recent deployment/config
  boundaries include `deploy/docker-compose.yml` mtime
  `2026-09-10T21:03:21-05:00` and `config/sources.json` mtime
  `2026-09-12T19:24:50-05:00`. The working tree had pre-existing unexplained
  changes and deletions; no repository reset or cleanup was performed.

## Recovery gate and action

The recovery gate was evaluated against the authoritative monitor evidence with
the configured 1,800-second cooldown and shared lock. It recorded:

- **Gate:** `allowed=false`, reason `recovery cooldown is active`
- **Gate event:** `2de3dfdc-8c24-4fbd-83a8-413c0abe4a0b`
- **Gate correlation:** `0098eb2f-cc03-4604-8727-9497ee6ea465`
- **Gate run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Audit timestamp:** `2026-09-14T21:46:38.569604+00Z`
- **Lock read-back:** absent

No ingestion retry, service restart, deployment, migration, credential change,
response-limit change, volume/data deletion, backup deletion, or publication
mutation was performed. Failed ThreatFox evidence and successful-source results
remain persisted and usable. No rollback is required.

## Prevention and follow-up

Validate ThreatFox provider-side filtering/pagination or an alternate endpoint
against an offline fixture before deploying a bounded-response fix. Retain an
oversized-response regression fixture, reconcile active runtime configuration
with `config/sources.json`, and verify the next run's failed-source and full-
success status. Separately investigate the monitor/direct run-status route
mismatch, fix the Alembic CLI database-target/event-loop hygiene, validate the
external Caddy route/trust chain, and export
`HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining
the container fallback. Any deployment or retry requires explicit authorization
and must use `./scripts/update-app.sh`.
