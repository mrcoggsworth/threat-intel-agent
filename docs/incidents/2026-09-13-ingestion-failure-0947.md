# Production ingestion incident: ThreatFox bounded response failure (09:47Z)

- **Observed:** 2026-09-13T09:47:18Z gate evaluation; monitor evidence observed at 2026-09-12T20:00:51.685946+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `a2d78640-143f-4cb3-a7f5-39733aaafc4f`
- **Correlation:** `c39db4c5-3cac-4423-83a6-204eba486a9b`
- **Run:** `e3f0e4df-f6eb-5828-9eb3-25de925befbc`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The latest persisted ingestion attempt is failed, with 37 of 38 sources
successful and one source failed. The failed source is ThreatFox Recent
Indicators (Abuse.ch). The prior full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
2026-09-11T12:06:50.050468+00:00. The latest run remains partially usable:
successful source results and persisted documents are retained, while the
failed source has no items. The database reports 12,787 new documents for this
run's persisted result; reports remain 186 and publications 201, with latest
publication 2026-09-11T22:24:37.183379+00:00.

No evidence deletion, volume deletion, database reset, migration rewrite,
backup mutation, credential rotation, or public-assessment edit occurred.

## Diagnosis and evidence

High confidence: deterministic source/provider bounded-ingestion failure, not a
web, proxy, scheduler, worker, database, disk, backup, or migration outage.
The `source_run` row for ThreatFox records `status=failed`, `http_status=NULL`,
`item_count=0`, `retry_count=0`, `cache_state=miss`,
`error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The source configuration has a
10,485,760-byte response cap, configuration version 2, last successful
retrieval 2026-09-11T12:06:49.272951+00:00, and three consecutive failures.

Read-only service verification:

- Web, scheduler, monitor, backup, and PostgreSQL containers are up and
  healthy; restart counts are 0. The worker is intentionally exited 0 after
  its reserved-worker command and is not a crash-loop.
- PostgreSQL accepts connections (`pg_isready`). PostgreSQL and Alembic are at
  `0015_contradiction_lifecycle`.
- The scheduler heartbeat exists in the monitor container and is fresh during
  verification. Monitor evidence is present and machine-readable.
- Host disk is 42% used with 280G available; memory has 52GiB available; open
  file limit is 4096.
- Backup metadata is present in the backup container with mode 600 and size 198
  bytes; encrypted backup artifacts are present, including a 21,621,808-byte
  artifact. No backup write was made.
- The running application image is `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`,
  created 2026-09-12T07:54:53.392614948-05:00. The monitor container's Compose
  image label is `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`.
- Docker events in the observation window showed health-check exec activity,
  not CTI-Hermes service restarts. Application logs show successful liveness,
  readiness, and run-status responses.
- Compose config validation from the repository shell was unavailable because
  the shell environment lacks the production-only `HERMES_SECRET_DIR` and
  `HERMES_IMAGE` variables. This is a diagnostic environment limitation, not
  evidence of a live Compose failure.
- The certificate served on local port 9444 is currently valid, but expires at
  2026-09-13T19:39:23Z. This is below the configured 14-day minimum remaining
  lifetime and is a separate certificate-rotation risk; it is not the cause
  of the ingestion failure.

## Recovery gate and action

The recovery gate acquired the actionable evidence at
2026-09-13T09:47:18.062452+00, event
`a2d78640-143f-4cb3-a7f5-39733aaafc4f`. The gate audit was completed with
outcome `failed` after diagnosis, and the recovery lock was verified absent.
No retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. A retry with the unchanged request
would reproduce the deterministic oversized-response failure and add provider
load without repairing it.

## Recovery / prevention

The smallest safe action was abstention. Validate a bounded ThreatFox retrieval
strategy (pagination, alternate endpoint, or provider-side filter) against an
offline fixture before changing the 10 MiB safety limit. Add a regression
fixture for oversized responses and keep failed source rows and partial-run
evidence visible. Separately rotate or renew the certificate before its
configured minimum-lifetime threshold is breached, using the certificate
runbook and a verified rollback path.

No rollback is required because no application or data change was made.
Existing uncommitted repository changes were present before this diagnosis;
this incident record is the only file added by this response.
