# Production ingestion incident: ThreatFox bounded-response failure (13:31Z)

- **Recorded:** 2026-09-13T13:34Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `1b8fa3a1-105c-4c72-ac45-6194f6471d66`
- **Observed at:** `2026-09-13T13:31:07.358424+00:00`
- **Correlation:** `56527045-357c-430c-af79-40d6ff497dff`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact and data-integrity state

The latest persisted collection is failed but partially usable: 37 of 38
sources completed and 5,943 documents were newly persisted. The
ThreatFox Recent Indicators (Abuse.ch) source failed; successful-source
artifacts and the failed-source record remain persisted. The latest full-success
run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00:00`. Current persisted counts are 186 reports,
201 report versions, 201 publications, 378 detections, 201 hunts, 201
remediation records, and 11 relationships. No report or publication mutation
was observed from this ingestion attempt.

No evidence, database volume, backup, credential, migration, or public CTI
assessment was deleted or changed by this diagnosis.

## Diagnosis and evidence

**Cause confidence: high.** This is a deterministic ThreatFox provider
bounded-response failure, not a web, proxy, worker, scheduler, database, disk,
backup, migration, or certificate outage. The source row for run
`5caec866-d2eb-51b1-905f-ecc8a66da107` records `status=failed`,
`http_status=NULL`, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The source has three
consecutive failures and `max_response_bytes=10485760`.

- Repository: `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; working tree
  has pre-existing unexplained changes and is ahead of `origin/main` by 3.
- Running image: `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
  created `2026-09-12T12:54:53.392614-05:00`.
- Web, monitor, scheduler, backup, and PostgreSQL containers were running
  healthy with restart count 0. The application containers started around
  `2026-09-12T12:55:15Z`; PostgreSQL has been running since
  `2026-09-05T16:36:57Z`.
- Scheduler heartbeat was fresh at `2026-09-13T13:32:25Z`; scheduler logs report
  `source collection failed`. PostgreSQL accepted connections via `pg_isready`.
- Applied migration revision is `0015_contradiction_lifecycle` and the
  database `alembic_version` agrees.
- Host resources were healthy: root filesystem 43% used with 280G available,
  52GiB memory available, and open-file limit 4096. Docker events showed
  health-check/diagnostic execs and no service restarts in the window.
- Encrypted backup artifacts and metadata were present; the latest artifact was
  created around `2026-09-13T12:55Z`. The backup container was healthy.
- Certificates on local ports 9443 and 9444 were valid through
  `2026-09-13T19:39:23Z`, but are below the configured 14-day renewal minimum.
  Renewal is a separate urgent operational risk.
- Direct host HTTP checks against the published web port returned 404 for the
  guessed health paths; this does not contradict the monitor's authenticated
  internal HTTP 200 checks and is not evidence of an outage.

## Recovery gate and action

The recovery gate was evaluated against the machine-readable monitor evidence
with its cooldown and lock. It acquired event
`4b61f83b-7c2f-4b43-8315-e1b08a32e656` at `2026-09-13T13:32:09Z` (gate
correlation `224e1d3b-51fd-429a-8a28-b3cef200c32a`) and completed with outcome
`failed` at `2026-09-13T13:33:27Z` because there is no safe reversible recovery
action for an unchanged provider response-limit failure. The lock was verified
absent. No retry, restart, deployment, migration, response-limit change,
credential change, or data mutation was performed.

Re-running unchanged ingestion would reproduce the failure and add provider
load without repairing it. The monitor continues to record the actionable
failure; the usable partial run remains available.

## Prevention and rollback

Validate ThreatFox pagination, provider-side filtering, or an alternate
endpoint against an offline fixture before any source configuration/code
deployment. Retain the oversized-response regression fixture and partial-run
visibility. Renew certificates before `2026-09-13T19:39:23Z` using the
certificate runbook and a verified rollback path. No application or data
rollback is required because this job made no such change; the recovery audit
record is preserved in the runtime log.
