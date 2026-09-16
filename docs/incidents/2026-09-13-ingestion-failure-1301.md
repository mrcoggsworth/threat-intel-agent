# Production ingestion incident: recovery cooldown suppression (13:01Z)

- **Recorded:** 2026-09-13T13:03Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `b8321941-5596-4a0b-86f1-9bfe45e22f05`
- **Observed at:** `2026-09-13T13:01:05.185593+00:00`
- **Correlation:** `3b4b5a66-2baf-479e-9bbd-0fb944f96c2f`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact and data-integrity state

The latest persisted collection remains a failed-but-partially-usable run:
37 of 38 sources completed and 5,943 documents were newly persisted. The
ThreatFox Recent Indicators (Abuse.ch) source failed; successful-source
artifacts and the failed-source record remain persisted. The latest full-success
run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00:00`. Reports, publications, detections, hunts,
remediation, and relationships were not mutated by this job.

No evidence, database volume, backup, credential, migration, or public CTI
assessment was deleted or changed.

## Diagnosis and evidence

**Cause confidence: high.** This is the continuing deterministic ThreatFox
provider bounded-response failure, not a web, proxy, worker, scheduler,
database, disk, backup, migration, or certificate outage. The source row for
run `5caec866-d2eb-51b1-905f-ecc8a66da107` records `status=failed`,
`http_status=NULL`, `item_count=0`, `retry_count=0`, `cache_state=miss`,
`error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`.

- Repository: `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; image
  `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Web, monitor, scheduler, backup, and PostgreSQL containers were running
  healthy with restart count 0. PostgreSQL accepted connections via
  `pg_isready`.
- Applied migration revision is `0015_contradiction_lifecycle` and the
  database `alembic_version` agrees. The Alembic CLI check from the web
  container could not connect because it defaulted to localhost; this was
  read-only and did not alter the database.
- Scheduler heartbeat was fresh at approximately 13:02Z; monitor evidence was
  refreshed at 13:02Z. Monitor signals were `full_success_freshness=stale_data`
  and `latest_ingestion_attempt=actionable_failure`, both HTTP 200.
- Host resources were healthy: root filesystem 42% used with 280G available,
  52GiB memory available, and open-file limit 4096.
- Backup metadata and encrypted artifacts were present; the latest artifact was
  created around 2026-09-13T12:55Z and metadata/artifact permissions were 600.
- Certificates on local ports 9443 and 9444 were valid through
  `2026-09-13T19:39:23Z`, but are below the configured 14-day renewal minimum.
  Renewal is a separate urgent operational risk.
- Docker events in the observation window showed health-check/diagnostic execs,
  not service restarts.

## Recovery gate and action

The recovery gate evaluated the required actionable evidence with its 30-minute
cooldown and lock. It recorded a **suppressed** event at
`2026-09-13T13:02:00.671891+00` for monitor event
`b8321941-5596-4a0b-86f1-9bfe45e22f05`; reason: `recovery cooldown is active`.
No retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. The prior gate attempt for the same
run completed with outcome `failed` at approximately 12:49:50Z; no recovery
lock remained.

A bounded source-level failure has no safe reversible recovery action during
the cooldown. Re-running unchanged ingestion would reproduce the provider
failure and add provider load without repairing it.

## Prevention and rollback

Validate ThreatFox pagination, provider-side filtering, or an alternate endpoint
against an offline fixture before any source configuration/code deployment.
Retain the oversized-response regression fixture and partial-run visibility.
Renew the certificates before `2026-09-13T19:39:23Z` using the certificate
runbook and a verified rollback path.

No application or data rollback is required because this job made no such
change. The recovery audit record is the only state change and is preserved in
the runtime audit log.
