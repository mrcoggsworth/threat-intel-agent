# CTI-Hermes production ingestion incident (01:30Z)

- **Recorded:** 2026-09-14T01:32:41Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `7945e2a7-201c-4226-9c5b-b156572759a4`
- **Observed at:** `2026-09-14T01:30:58.601695+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation ID:** `910743dc-19ce-4bbf-8651-8e0a3be5415f`
- **Latest attempt run ID:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact

The latest scheduled collection remains failed but partially usable: 37 of 38
sources succeeded and 5,943 new documents were persisted. The latest full-success
run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`; complete source coverage remains stale. Public
CTI remains internally available from the partial projection, but the failed
source has no new data from the latest run.

## Diagnosis and evidence

- The failed source is `threatfox-recent-indicators-abuse-ch`; prior evidence
  classifies it as `oversized_response` with detail `response exceeds 10485760
  bytes`, zero items, and no HTTP status. The same source failure recurs in the
  preceding failed runs.
- Database query returned 25 ingestion runs. Latest rows remain failed with
  38/37/1 source totals; the prior full-success row is present. PostgreSQL
  `pg_isready` accepts connections and Alembic revision is
  `0015_contradiction_lifecycle`.
- Web, scheduler, monitor, PostgreSQL, and backup containers are running
  healthy with restart count 0 and OOM false. Scheduler heartbeat was
  `2026-09-14T01:32:30Z` during verification.
- Internal monitor probes returned HTTP 200 for `/health/live`, `/health/ready`,
  and `/version`; `hermes-cti version` returned `0.1.0` and `hermes-cti doctor`
  returned `OK`.
- Host capacity: root filesystem 43% used with 280G available; 52 GiB memory
  available; open-file limit 4096. No resource-pressure evidence observed.
- Backup service is healthy. Latest metadata points to encrypted artifact
  `/backups/hermes-20260913T125518Z.dump.enc`, completed
  `2026-09-13T12:55:20Z`, 22,110,800 bytes, mode 600, with recorded SHA-256
  metadata. No backup was changed.
- Caddy has restart count 0 and logs successful local certificate renewal for
  `hermes.cti.scogin.dev`; certificate trust/routing remains a separate
  follow-up, not the ingestion cause.
- Repository identity at diagnosis: `main`, HEAD
  `c925cd5bbb1b2c872841205b90ea05ea4636da76`; the working tree contained
  broad pre-existing changes and was not reset or modified by recovery.

**Cause confidence: high.** This is a deterministic ThreatFox/Abuse.ch
provider/source response-size boundary, not a web, proxy, worker, scheduler,
database, disk, memory, file-descriptor, certificate, backup, migration,
publication, or credential outage.

## Recovery gate and actions

The recovery gate was evaluated against the authoritative
`/runtime/monitor-evidence.json`. It returned `allowed: true` and recorded an
`attempted` event for the exact monitor event/correlation/run identifiers.
No blind ingestion retry, restart, migration, deployment, credential change,
source-limit change, publication mutation, data deletion, volume deletion, or
backup deletion was performed: all services are healthy and the only known
fault is a source-boundary defect, so no smallest reversible service action
could improve the state. The gate was closed with `completed` outcome
`suppressed`; its lock was verified absent.

## Service/data state and prevention

- **Service:** internally serving; collection completeness degraded for one
  source.
- **Data integrity:** preserved. Successful source evidence and the failed
  source/run records remain persisted; no destructive recovery occurred.
- **Rollback:** not applicable; no application or data change was made.
- **Prevention:** bound or paginate the ThreatFox request (or use a supported
  filtered endpoint), preserve the oversized-response classification, and add
  an offline oversized-response regression fixture before any approved code
  change. Reconcile the checked-in source limit with the active 10 MiB runtime
  boundary. Separately investigate CLI asyncpg cleanup and external Caddy
  certificate trust/routing.
