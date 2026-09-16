# Production ingestion incident: recovery cooldown suppression (02:16Z)

- **Recorded:** 2026-09-14T02:16:12.820221Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, image `cti-hermes:local`, application `0.1.0`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `66a1a2aa-f3e9-4e57-9327-426fcd78916f`
- **Observed at:** `2026-09-14T02:15:01.584932+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `7c8fd90d-da43-495c-8e8b-1bacfc38c8fc`
- **Run:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Gate:** evaluated in the monitor container with the 30-minute cooldown and lock; event `d4fb791d-593b-4dcf-b542-5f1e7bdb7555` was recorded as `suppressed` because `recovery cooldown is active`. Lock verified absent.

## Impact and diagnosis

The 02:00Z collection is usable but incomplete: 37 of 38 sources succeeded,
one failed, and 1,564 new documents were persisted. The latest full-success run
is stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
2026-09-11T12:06:50.050468Z). Public CTI remains available from the partial
projection, but full source coverage and full-success freshness are degraded.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its persisted
source-run record is `status=failed`, `error_classification=oversized_response`,
and `error_detail=response exceeds 10485760 bytes`. The same deterministic
failure is present in the preceding failed runs. Cause confidence is **high**:
a provider/source response-size boundary mismatch, not a web, proxy, scheduler,
database, resource, certificate, backup, migration, publication, or credential
outage. Checked-in `config/sources.json` contains `max_response_bytes=52428800`,
while the active runtime still rejects at 10 MiB; this change was not deployed
or modified during diagnosis.

## Evidence and operational state

- Latest run `3848465e-e2a0-572a-b522-4c768d790284`: started
  `2026-09-14T02:00:00.095941Z`, completed `2026-09-14T02:00:06.398193Z`,
  status `failed`, 38 total / 37 successful / 1 failed, application `0.1.0`,
  configuration hash
  `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Latest full-success is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest usable
  run is the 02:00Z partial run. Database has 186 reports, 201 publications,
  and latest report/publication timestamp `2026-09-11T22:24:37.163555Z`.
- Web liveness and readiness returned HTTP 200 with readiness checks
  `configuration=ok` and `database=ok`. PostgreSQL returned accepting
  connections and `current_database=hermes`, `current_user=hermes`.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running and
  healthy with restart count 0. The worker is an intentional one-shot container
  exited 0 and was not OOM-killed. Monitor logs show repeated freshness/attempt
  failures but no crash loop. Scheduler heartbeat checks continued returning
  HTTP 200.
- Migration revision is `0015_contradiction_lifecycle`; no migration mutation
  was performed. Alembic CLI checks from the web container could not connect to
  localhost PostgreSQL because the command used the wrong in-container host;
  the application and direct PostgreSQL connectivity checks were healthy.
- Host root filesystem is 43% used with 280 GiB available; memory reports 52
  GiB available; shell open-file limit is 4096. No resource exhaustion is
  indicated.
- Encrypted backup artifacts and metadata exist through
  `hermes-20260913T125518Z.dump.enc` (22 MiB class artifact; metadata mode 600).
  No backup mutation occurred. The proxy certificate file is present and was
  renewed/updated at `2026-09-13 23:39:23Z`; certificate expiry could not be
  independently parsed because the Caddy container lacks `openssl` and the
  host Docker-volume path is permission-protected.
- Docker event collection showed only diagnostic `exec_*` events in this
  window; no service restart or OOM event was observed.
- Compose validation from this operator shell remains blocked because protected
  `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables are not exported. This is a
  shell limitation, not production outage evidence. Working tree contains
  pre-existing unrelated changes; none were altered.

## Action, data integrity, and rollback

No ingestion retry, service restart, deployment, migration, credential change,
response-limit change, volume/data deletion, backup deletion, or publication
mutation was performed. The recovery gate suppressed recovery under cooldown;
therefore no destructive or unauthorized recovery was attempted. Failed
ThreatFox evidence remains persisted, successful source results remain usable,
and no rollback is required.

## Prevention and follow-up

Validate ThreatFox provider-side filtering/pagination or an alternate endpoint
against an offline fixture before deploying the checked-in 50 MiB limit. Add or
retain a regression fixture for the 10 MiB response boundary, reconcile active
runtime configuration with source configuration, and preserve partial-run and
stale-full-success visibility. Re-check certificate expiry using the proxy's
renewal tooling before the next certificate boundary.
