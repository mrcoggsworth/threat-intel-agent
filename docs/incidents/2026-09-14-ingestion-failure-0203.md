# Production ingestion incident: actionable partial-run failure (02:03Z)

- **Recorded:** 2026-09-14T02:03:01Z
- **Repository/release:** `main`, `c925cd5bbb1b2c872841205b90ea05ea4636da76`, `cti-hermes:local`, application version `0.1.0`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `d86b1ac5-ec6d-428c-8db4-c6cf2a4c99c2`
- **Observed at:** `2026-09-14T02:02:00.547863+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `96d98fff-f602-4e4f-a64b-be83d4b7f336`
- **Run:** `3848465e-e2a0-572a-b522-4c768d790284`
- **Gate:** evaluated with cooldown and lock; attempted event `d86b1ac5-ec6d-428c-8db4-c6cf2a4c99c2` was recorded, then completed with outcome `suppressed` because recovery was not authorized. Lock was cleaned up and verified absent.

## Impact and cause

The 02:00Z ingestion run is persisted and usable but failed one of 38 sources:
37 succeeded, 1 failed, and 1,564 new documents were recorded. The latest
full-success run is stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
2026-09-11T12:06:50.050468Z). Public CTI remains available from the partial
projection, but complete source coverage and full-success freshness are
 degraded.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its persisted
source-run record is `status=failed`, `error_classification=oversized_response`,
and `error_detail=response exceeds 10485760 bytes`. The same deterministic
failure is present in the preceding failed runs. Cause confidence is **high**:
provider/source response-size boundary, not a web, proxy, scheduler, database,
resource, certificate, backup, migration, publication, or credential outage.
The checked-in source configuration shows `max_response_bytes=52428800`, while
the active runtime rejects at 10 MiB; this boundary mismatch is a prevention
follow-up, not changed during diagnosis.

## Evidence and operational state

- Latest run: `3848465e-e2a0-572a-b522-4c768d790284`, started
  `2026-09-14T02:00:00.095941Z`, completed `2026-09-14T02:00:06.398193Z`,
  status `failed`, 38 total / 37 successful / 1 failed, application `0.1.0`,
  configuration hash
  `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Latest full-success: `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest usable is
  the 02:00Z partial run. Database counts include 31,678 source documents,
  186 reports, 201 report versions, 201 publications, 378 detections, 201
  hunts, and 201 remediations.
- PostgreSQL is accepting connections; migration revision is
  `0015_contradiction_lifecycle`. No migration mutation was performed.
- Web liveness and readiness returned HTTP 200. Web, monitor, scheduler,
  PostgreSQL, and backup containers are healthy with restart count 0 and no OOM
  termination. The worker is an intentional one-shot container exited 0.
  Scheduler heartbeat was current at `2026-09-14T02:02:00.550Z`.
- Monitor logs repeatedly report only `last successful run stale` and
  `latest ingestion attempt failed`. Docker-event collection via the host
  command had a format-parser error, so restart-history evidence is from
  `docker inspect`; no restart or OOM was observed.
- Host resources: root filesystem 43% used (280 GiB available), 52 GiB memory
  available, shell open-file limit 4096. No exhaustion is indicated.
- Backup metadata exists mode 600 for encrypted artifact
  `/backups/hermes-20260913T125518Z.dump.enc`, completed
  `2026-09-13T12:55:20Z`, 22,110,800 bytes, SHA-256 recorded in protected
  metadata (not repeated here). No backup mutation occurred.
- Caddy certificate is locally presented by the proxy and valid through
  `2026-09-14T11:39:23Z`; renewal is urgent but unrelated to ingestion.
- Compose config validation from this shell remains blocked because protected
  production variables `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported.
  This is an operator-shell limitation, not production outage evidence.

## Action, data integrity, and rollback

No ingestion retry, service restart, deployment, migration, credential change,
response-limit change, volume/data deletion, backup deletion, or publication
mutation was performed. The recovery gate suppressed the action under the
configured 30-minute cooldown/no-recovery-authorization path. Data integrity is
preserved: the failed source evidence remains recorded and successful source
results remain usable. No rollback is required.

## Prevention and follow-up

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture before changing source behavior. Add/retain a
regression fixture for the 10 MiB response boundary, reconcile the active
runtime boundary with the checked-in 50 MiB source limit, and keep partial-run
and stale-full-success visibility. Renew the Caddy certificate before expiry.
