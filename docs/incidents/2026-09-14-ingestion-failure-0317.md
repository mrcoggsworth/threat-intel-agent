# Production ingestion incident: gated diagnostic suppression (03:17Z)

- **Recorded:** 2026-09-14T03:17:18Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, image `cti-hermes:local`, application `0.1.0`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `13409382-8bdb-46cc-99d5-29548a9c2edc`
- **Observed at:** `2026-09-14T03:15:05.888194+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `3415a7c2-ba92-469a-a7f7-70ee12c15a6f`
- **Run:** `3848465e-e2a0-572a-b522-4c768d790284`

## Impact and diagnosis

The latest scheduled collection remains failed and partially usable: 37 of 38
sources succeeded, 1 failed, and 1,564 new documents were persisted. The latest
full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
2026-09-11T12:06:50.050468Z. Public CTI remains available from successful-source
and partial-run data, but complete source coverage and full-success freshness are
degraded.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its source-run
record is `status=failed`, `cache_state=miss`, `item_count=0`,
`error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The source has five consecutive
failures and its last successful retrieval was 2026-09-11T12:06:49.272951Z.
The checked-in source configuration requests 50 MiB, while the active persisted
source configuration remains 10 MiB; the checked-in configuration has not been
deployed. Cause confidence is **high**: deterministic provider/source response
boundary mismatch, not an application, database, scheduler, resource,
certificate, backup, migration, publication, or credential outage.

## Operational evidence

- Web, scheduler, monitor, PostgreSQL, and backup containers are running and
  healthy; restart count is 0. The worker is an intentional one-shot container
  exited 0. No OOM-kill or restart-loop evidence was found.
- Scheduler heartbeat was current at 2026-09-14T03:16:31Z.
- PostgreSQL accepted connections; `current_database=hermes`,
  `current_user=hermes`; Alembic revision is `0015_contradiction_lifecycle`.
  No pending-migration evidence was found.
- Pipeline counts: 31,678 source documents, 186 reports, 201 report versions,
  201 publications, 378 detections, 201 hunts, 201 remediations, and 11
  relationships. Report/publication freshness remains 2026-09-11T22:24:37Z.
- Host root filesystem is 43% used with 280 GiB available; memory available is
  52 GiB; shell open-file limit is 4096. No resource exhaustion is indicated.
- Backup metadata exists at `/backups/latest.metadata` with mode 600; the
  protected metadata contents were not exposed. Earlier verified backup evidence
  identifies `hermes-20260913T125518Z.dump.enc` as completed at
  2026-09-13T12:55:20Z.
- Caddy logs show successful local certificate renewal for
  `hermes.cti.scogin.dev`; no certificate-expiry failure is indicated.
- Docker events in the diagnostic window contained health-check/exec activity,
  with no CTI-Hermes restart or OOM event. Read-only diagnostic queries also
  attempted obsolete table/column names and produced harmless PostgreSQL errors;
  no data mutation occurred.

## Recovery gate and action

The authoritative evidence was read from
`/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`. The recovery gate
was evaluated with its 30-minute cooldown and lock. It acquired event
`715a4c3b-c3ca-4ed0-8d75-cbc30e8e0945` with gate correlation
`a93dae50-6d72-4e87-afa2-baad212fb972`, then was explicitly completed as
`suppressed` with completion correlation `5ab946e0-b335-447b-a793-41debc5fc86d`.
The recovery lock was verified absent.

No ingestion retry, service restart, deployment, migration, credential change,
response-limit change, volume/data deletion, backup deletion, or publication
mutation was performed. Diagnosis was authorized, but recovery was not.

## State, rollback, and prevention

- **Service state:** internally serving; ingestion freshness degraded.
- **Data integrity:** successful source evidence and the failed ThreatFox record
  remain persisted; no destructive operation occurred.
- **Rollback:** not applicable; no application or deployment change was made.
- **Prevention:** validate ThreatFox provider-side filtering/pagination or an
  alternate endpoint against an offline fixture; reconcile active runtime and
  checked-in source configuration through a reviewed deployment; preserve the
  oversized-response regression fixture and failure classification; and fix the
  operational diagnostic query/schema drift before the next incident run.
