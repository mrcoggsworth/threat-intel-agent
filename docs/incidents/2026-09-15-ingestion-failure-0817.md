# Production ingestion incident: actionable source failure (2026-09-15 13:17Z)

## Impact

The latest scheduled collection is not a full-success run. Ingestion completed
37/38 enabled sources and persisted 13,108 new documents, but the run remains
`failed`; the full-success projection is `stale_data`. The web portal and
readiness checks remain available. No data deletion, database reset, migration,
or deployment was performed.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured
Compose fallback was read from `/runtime/monitor-evidence.json` in
`cti-hermes-monitor-1` before diagnosis.

- State: `actionable_failure`
- Event: `81f459cf-1bba-48ae-9897-94dbbc623ca5`
- Observed: `2026-09-15T13:16:33.698322+00:00`
- Correlation: `a830fb81-2441-468e-babb-2d8da3fd3472`
- Endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP 200
- Full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- Latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`
- Run: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`

## Recovery gate and actions

The 1,800-second recovery cooldown and shared lock were evaluated before any
recovery action. The gate acquired attempted event
`81f459cf-1bba-48ae-9897-94dbbc623ca5` with correlation
`a830fb81-2441-468e-babb-2d8da3fd3472`. Because this scheduled request
authorizes diagnosis only, no restart, collection retry, deployment, or
migration was attempted. The event was completed with outcome `suppressed` at
`2026-09-15T13:16:55.353119+00Z`; read-back verified `/runtime/recovery.lock`
absent. The monitor refreshed during bookkeeping and still reported the same
failed run and source-level failure.

## Evidence and diagnosis

- Application version: `0.1.0`; image tag `cti-hermes:local`; image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Web, scheduler, monitor, PostgreSQL, backup, and Caddy containers were up;
  application containers were healthy with zero restarts. Web was published on
  `127.0.0.1:18000`; no direct host port 8000 is expected.
- Internal web checks returned HTTP 200: `/health/live` and `/health/ready`;
  readiness reported database `ok`. The monitor's internal run-status request
  returned HTTP 200. Direct host requests to port 8000 returned no connection
  because that port is not published.
- PostgreSQL accepted connections. `alembic_version` is
  `0015_contradiction_lifecycle`, matching the image migration head reported
  by `alembic heads`; no pending migration was applied. An `alembic current`
  attempt from the web container was not usable because its default database
  host is localhost, while the live database is a separate container; direct
  SQL verification succeeded.
- Latest run: 38 total, 37 successful, 1 failed; status `failed`; started
  `2026-09-15T02:00:00.049118+00`, completed `2026-09-15T02:00:54.439155+00`.
- Failed source: `threatfox-recent-indicators-abuse-ch`; classification
  `oversized_response`; detail `response exceeds 10485760 bytes`; its last
  successful retrieval was `2026-09-11T12:06:49.272951+00`, with seven
  consecutive failures and a 10 MiB configured bound.
- Scheduler logs show `source collection failed` without a process crash.
- Disk: 43% used, 279G available. Memory had 49G available; host open-file
  count was 261,615 and the shell limit was 4,096. Docker disk usage was
  informational only; no prune was run.
- Backups: backup container healthy with zero restarts. Encrypted backup files
  were present through `2026-09-14T12:55:20Z`; no restore was attempted.
- Certificates: Caddy was up. TLS certificates for the public/internal names
  were renewed successfully by Caddy; the observed certificate validity was
  `2026-09-15 07:39:23Z` through `2026-09-15 19:39:23Z`.
- Compose validation from the cron shell was blocked by absent protected
  environment variables (`HERMES_SECRET_DIR` and `HERMES_IMAGE`); this did not
  affect inspection of the already-running containers and is an operational
  diagnostic-environment defect.

**Cause confidence: high.** The failure is source/provider-specific and
reproducibly recorded as an oversized ThreatFox response. Web, scheduler,
database, storage, backup, and TLS failures are not supported by the evidence.

## Data integrity and rollback

The 37 successful source results and 13,108 new documents remain persisted.
The failed ThreatFox source result is preserved as failed evidence; no
constraints were bypassed and no public CTI conclusion was edited. No rollback
is applicable because no application or data mutation was made.

## Prevention / follow-up

Under explicit recovery or deployment authorization, validate a bounded or
paginated ThreatFox request (or an alternate provider endpoint) with an offline
oversized-response fixture, assess decompression/memory impact, and deploy only
through `./scripts/update-app.sh`. Verify the next run's source status,
full-success and usable-run projections, monitor evidence, and publication
freshness. Export `HERMES_MONITOR_EVIDENCE_FILE` and the protected Compose
variables in the maintenance cron environment while retaining the container
fallback. Review the operational diagnostic path so Compose config validation
can run without exposing secret values.
