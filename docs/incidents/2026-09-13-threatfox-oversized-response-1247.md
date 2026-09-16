# Production ingestion incident: ThreatFox oversized response (12:47Z)

- **Recorded:** 2026-09-13T12:48:00Z (diagnosis completed)
- **Monitor state:** `actionable_failure`
- **Monitor event:** `8576e421-aa9c-4721-a6bb-3007556583b7`
- **Observed at:** `2026-09-13T12:47:04.170021+00:00`
- **Correlation:** `3dd3c12c-beb7-4db7-9d78-0cb806517c34`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Recovery-gate event:** `8576e421-aa9c-4721-a6bb-3007556583b7`

## Impact and data-integrity state

The latest persisted ingestion attempt is failed but usable for successful
sources: 37 of 38 sources completed and 5,943 documents were newly persisted.
ThreatFox Recent Indicators (Abuse.ch) returned no items. The latest full-success
run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00:00`. The latest attempt completed at
`2026-09-13T02:00:07.873460Z`; reports/publication data was not mutated by this
recovery job. Successful-source documents and failed-source evidence remain
persisted and visible.

No evidence deletion, volume deletion, database reset, migration rewrite,
backup mutation, credential rotation, or public-assessment edit occurred.

## Diagnosis and evidence

**Cause confidence: high.** This is a deterministic ThreatFox/provider bounded-
response failure, not a web, proxy, scheduler, worker, database, disk, backup,
migration, or certificate outage. The failed `source_run` row records
`status=failed`, `http_status=NULL`, `item_count=0`, `retry_count=0`,
`cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The persisted run records
`total_sources=38`, `successful_sources=37`, `failed_sources=1`,
`new_documents=5943`, `application_version=0.1.0`, and configuration hash
`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

Read-only verification:

- Web, scheduler, monitor, backup, and PostgreSQL containers are running
  healthy with restart count 0. The worker is intentionally exited 0 after its
  reserved-worker command and is not a crash-loop.
- Private run-status returned HTTP 200. `latest_usable` is the partial latest
  attempt; `latest_full_success` is the 2026-09-11 run.
- PostgreSQL accepts connections (`pg_isready`); Alembic is at
  `0015_contradiction_lifecycle`. A diagnostic query using nonexistent column
  names was rejected by PostgreSQL and made no change.
- Scheduler heartbeat was fresh at `2026-09-13T12:46:55Z`; monitor evidence was
  fresh at `2026-09-13T12:47:04Z`.
- Host disk is 42% used with 280G available; memory has 52GiB available; open
  file limit is 4096.
- Backup metadata is present with mode 600 and size 198 bytes. Encrypted backup
  artifacts are present, including the latest 21,621,808-byte artifact.
- The certificates on local ports 9443 and 9444 are valid through
  `2026-09-13T19:39:23Z`, but below the configured 14-day minimum remaining
  lifetime. Certificate renewal is a separate urgent operational risk.
- Docker events in the observation window showed health-check exec activity and
  diagnostic execs, not CTI-Hermes service restarts.
- Repository HEAD is `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, ahead of
  `origin/main` by 3 commits. The working tree contained pre-existing broad
  uncommitted changes, including a local ThreatFox `max_response_bytes` change;
  it was not deployed because its scope and provenance were not attributable to
  this recovery job.

## Recovery gate and action

The recovery gate acquired the actionable evidence after the 30-minute cooldown
had expired and no lock was present. It recorded an `attempted` event for
`8576e421-aa9c-4721-a6bb-3007556583b7`, then was completed with outcome
`failed`; the recovery lock was verified removed. No retry, restart, deployment,
migration, response-limit change, credential change, or data mutation was
performed. Re-running unchanged ingestion would reproduce the deterministic
oversized-response failure and add provider load without repairing it.

## Prevention and rollback

Validate pagination, provider-side filtering, or an alternate ThreatFox endpoint
against an offline fixture before deploying a source change. Add/retain a
regression fixture for oversized responses and preserve partial-run visibility.
Review and deploy only a focused, attributable configuration/code change; do not
include the pre-existing broad working-tree changes. Renew the certificate
before `2026-09-13T19:39:23Z` using the certificate runbook and a verified
rollback path.

No rollback is required because no application or data change was made.
