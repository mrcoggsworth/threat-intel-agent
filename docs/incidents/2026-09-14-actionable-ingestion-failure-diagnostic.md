# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-14T00:14:53.150142Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `4370c88f-7f62-42e7-b10c-d1956eda6f5d`
- **Correlation ID:** `cc212e31-ffb2-4812-a69d-8622b0e2c142`
- **Latest attempt run ID:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Application:** version `0.1.0`, local image `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`
- **Repository:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`

## Impact

The latest scheduled collection is failed and only partially usable: 37 of 38
sources succeeded. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
2026-09-11T12:06:50.050468Z. Public CTI freshness is therefore impaired for
at least one source; successful source evidence remains persisted. No database
reset, volume deletion, credential change, restart, retry, or deployment was
performed.

## Evidence and diagnosis

- Latest attempt: scheduled 2026-09-13T02:00:00Z, completed
  2026-09-13T02:00:07.873460Z, 38 total / 37 successful / 1 failed;
  API error summary: `1 source(s) failed`.
- Failed source: `threatfox-recent-indicators-abuse-ch`; status `failed`,
  item count 0, cache state `miss`, classification `oversized_response`,
  detail `response exceeds 10485760 bytes`.
- PostgreSQL is accepting connections and the failed run plus source-run record
  are present. Alembic revision is `0015_contradiction_lifecycle`; no pending
  migration evidence was found.
- Web, scheduler, monitor, backup, and PostgreSQL containers are running;
  web, scheduler, monitor, backup, and PostgreSQL report healthy. Worker is
  intentionally exited with code 0 and has no restart loop.
- Scheduler heartbeat was current at collection time (`2026-09-14T00:17:29Z`).
- Disk usage was 43% (280G available), memory available was 52GiB, and host
  open-file limit was 4096. No OOM or container restart evidence was observed.
- Most recent backup metadata: artifact
  `hermes-20260913T125518Z.dump.enc`, completed 2026-09-13T12:55:20Z,
  22,110,800 bytes. The backup container is healthy.
- Caddy is running without restarts and logged successful local certificate
  renewal for `hermes.cti.scogin.dev`. An external curl probe returned HTTP 404
  with TLS verification result 20; internal web liveness/readiness checks were
  HTTP 200. This is a separate ingress/certificate-trust/routing follow-up,
  not the ingestion failure cause.
- `hermes-cti db status` returned the expected stale/full-success projection
  but also emitted an asyncpg event-loop cleanup traceback; this is a CLI
  hygiene defect to investigate separately.

**Cause confidence: high.** The failure is source/provider response-size
handling at the ThreatFox/Abuse.ch source boundary, not web availability,
PostgreSQL connectivity, disk, memory, certificate expiry, or migration state.
The recurring failure pattern is consistent with the same source-level limit.

## Recovery gate and actions

The recovery gate was evaluated against the monitor evidence using the shared
runtime state. It returned:

- `allowed: false`
- `reason: recovery cooldown is active`
- suppression event ID: `6786fb60-da6d-4431-9f15-280977d86464`
- suppression correlation ID: `7ff8f73d-685e-48e7-8d8e-81632c351adf`

The suppression was recorded in `/runtime/recovery-events.jsonl`; the previous
attempt timestamp was 2026-09-13T23:46:27.532981Z. No recovery action was
allowed or attempted beyond gate evaluation. This preserves the cooldown and
avoids an unapproved ingestion retry.

## State and follow-up

- **Service state:** serving internally; collection freshness degraded.
- **Data integrity:** no destructive operation; 37 successful source results
  and the failed source record are preserved.
- **Rollback:** not applicable; no code/config/deployment change made.
- **Recommended prevention:** make the ThreatFox source request bounded or
  paginated so the response cannot exceed the 10 MiB transport limit, retain
  the failure classification, add a mocked oversized-response regression test,
  and only retry after the recovery gate permits it. Separately fix the CLI
  database-status event-loop cleanup and validate the external Caddy route/TLS
  trust chain.
