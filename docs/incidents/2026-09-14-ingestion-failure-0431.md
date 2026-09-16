# Production ingestion incident: monitor-gated diagnosis (04:31Z)

- **Observed at:** `2026-09-14T04:30:11.125019+00:00`
- **Monitor state:** `actionable_failure`
- **Event ID:** `2cde8879-2043-4f47-90b5-e266f4139c04`
- **Evidence correlation ID:** `9272e0af-7327-4c36-bb83-44110bbe4ac8`
- **Latest failed run ID:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Evidence endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Signals:** `full_success_freshness=stale_data` (run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`); `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`

## Impact and cause

The 2026-09-14 02:00Z collection is persisted as `failed`: 38 sources,
37 successful, 1 failed, 1,564 new documents, and 0 new findings. The failed
source is `threatfox-recent-indicators-abuse-ch` with
`error_classification=oversized_response` and
`error_detail=response exceeds 10485760 bytes`. This is a deterministic,
source/provider response-size failure, not a web, proxy, scheduler, database,
disk, certificate, or backup outage. Ingestion completeness is degraded for
one source; existing persisted evidence and publications remain intact.

Cause confidence: **high** (exact source-run classification and threshold are
persisted in PostgreSQL and match the monitor detail). A focused, uncommitted
working-tree change raises the ThreatFox configured response limit to
`52428800` bytes, but the running `cti-hermes:local` image was built before
that change and still used the 10 MiB limit. No deployment was authorized or
performed by this diagnosis-only job.

## Recovery gate and actions

The recovery gate was evaluated against the authoritative monitor evidence with
a 1,800-second cooldown and lock. During diagnosis the monitor continued to
refresh; a later read at `2026-09-14T04:33:11.323885+00:00` remained
`actionable_failure` for the same run, with a new monitor event and correlation
ID. The gate evaluation itself recorded suppressed event
`5ec464b9-9536-457a-b23f-f86c14bdbd27` at
`2026-09-14T04:31:43.388551+00`, reason `recovery cooldown is active`.
The previous attempt was `2026-09-14T04:16:28.865025+00`; the recovery lock was
verified absent. Diagnosis is authorized but recovery is not, so no restart,
collection retry, migration, deployment, or data mutation was performed.

## Service and data-integrity evidence

- Current time captured: `2026-09-14T04:30:57Z`.
- Repository: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote
  `git@github.com:mrcoggsworth/threat-intel-agent.git`. Working tree contains
  pre-existing unexplained changes and deletions; no reset or cleanup was done.
- Running application image: `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`;
  application `/version` reports `0.1.0`.
- Web, monitor, scheduler, PostgreSQL, and backup containers are running and
  healthy with zero restart count. The worker is an exited one-shot container
  (exit 0) and has not restarted.
- Web liveness and readiness returned HTTP 200; readiness reported
  `configuration=ok,database=ok`. Scheduler heartbeat was current at
  `2026-09-14T04:32:31Z`.
- PostgreSQL `16.14` accepted connections. Alembic revision is
  `0015_contradiction_lifecycle`; no pending/failed migration was observed.
- Latest successful collection is run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`,
  completed `2026-09-11T12:06:50.050468+00`. Latest source-document retrieval
  is `2026-09-14T02:00:05.858334+00`; reports: 186 (latest
  `2026-09-11T22:24:37.163555+00`); publications: 201 (same timestamp).
- Disk is 43% used with 280G available; memory has 52Gi available; host file
  descriptor limit is 4096. Docker reports no active build cache or volume
  pressure requiring action.
- Backup container is healthy. Encrypted backup metadata and dump are present,
  latest dump timestamp `2026-09-13T12:55:18Z`, size 22,110,800 bytes.
- Caddy logs show successful local certificate renewals for
  `hermes.cti.scogin.dev` and `matrix.scogin.dev`, plus successful reloads;
  no certificate failure is present in the observation window.
- Proxy/web logs show normal health/readiness responses. Repeated monitor
  failures are the expected stale-success/latest-attempt signals, not process
  crashes. No scheduler error log was emitted.

## Recovery / prevention

No rollback is required because no mutation occurred. The smallest reversible
approved follow-up is to review the existing `config/sources.json` ThreatFox
limit change, run focused tests, then deploy via `./scripts/update-app.sh` only
under an explicit recovery/deployment authorization. Verify a subsequent run's
source status, response-size handling, monitor evidence, and publication/data
integrity. Keep the old 10 MiB behavior as rollback until the larger bounded
limit is validated against memory and provider behavior.
