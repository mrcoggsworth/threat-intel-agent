# Production ingestion incident: ThreatFox bounded response failure (03:03Z)

- **Observed:** 2026-09-13T03:01:21.684321+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `2a3fdc91-e1b8-477a-8607-3ff7f7a0c439`
- **Correlation:** `d66fc0b9-fb40-4c24-b097-ea054d8e5fea`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The 2026-09-13 daily collection is `failed`: 37 of 38 sources completed and
5,943 new documents were persisted; the ThreatFox Recent Indicators (Abuse.ch)
source failed. The latest full-success run remains
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed
2026-09-11T12:06:50.050468+00. The latest publication remains
2026-09-11T22:24:37.183379+00 (201 publications / 186 reports).
Partial successful evidence is preserved; no database reset, volume deletion,
or evidence deletion occurred.

## Diagnosis

High confidence: deterministic source-level bounded-ingestion failure, not a
web, proxy, scheduler, database, disk, backup, migration, certificate, or
credential outage. PostgreSQL records the failed source with zero HTTP status,
zero items, zero retries, `cache_state=miss`,
`error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The source configuration is
`max_response_bytes=10485760`, configuration version 2, with three consecutive
failures; its last successful retrieval was 2026-09-11T12:06:49.272951+00.
The run application version is `0.1.0` with configuration hash
`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

## Evidence and verification

- Recovery gate acquired at 2026-09-13T03:01:56.014325+00 for the monitor
  event, then completed at 2026-09-13T03:03:28.443033+00 with outcome `failed`.
  The lock was verified absent. No retry, restart, deployment, migration,
  response-limit change, credential change, or data mutation was performed.
- Compose configuration validation passed when supplied the active local image
  and protected secret directory. Web `/health/live` and `/health/ready`
  returned 200; readiness reported configuration and database `ok`.
  PostgreSQL `pg_isready` accepted connections.
- Monitor, web, scheduler, backup, and PostgreSQL containers were running and
  healthy with restart count 0. The worker exited 0 with its documented
  reserved-worker message. Scheduler heartbeat was fresh at 2026-09-13T03:01:51Z.
- Host disk was 42% used with 280G available; host memory had 53GiB available;
  open-file limit was 4096. Application container FD counts were low (3, 15,
  7, and 10 for monitor, web, scheduler, and PostgreSQL respectively).
- Database migration table reports `0015_contradiction_lifecycle`; Alembic
  reports the same revision as head. A direct Alembic online check from the
  scheduler was inconclusive because its local connection target was localhost,
  but the application readiness check and direct PostgreSQL query succeeded.
- Backup metadata reports encrypted artifact
  `/backups/hermes-20260912T125515Z.dump.enc`, completed
  2026-09-12T12:55:18Z, 21,621,808 bytes. The backup was not opened or changed.
- Caddy configuration/module validation succeeded. The public certificate for
  `matrix-1.taild27e3c.ts.net` is valid through 2026-11-16T14:30:36Z. The
  internal certificate observed on port 9444 is valid through
  2026-09-13T11:39:23Z; no certificate mutation was performed.
- Existing uncommitted repository changes were present before diagnosis,
  including profile/cron/config and documentation deletions plus a scratch
  partial archive. No source or deployment file was modified by this incident
  response.

## Action and follow-up

The smallest reversible action was to abstain from retrying or restarting a
healthy stack because either would reproduce the provider payload failure or
create unnecessary operational risk. Treat the ThreatFox payload-size change as
a source/provider maintenance item: validate bounded pagination, an alternate
endpoint, or a provider-side filter in an offline fixture before changing the
10 MiB safety limit. Add a regression fixture for oversized responses and keep
partial-run/source-error evidence visible. Do not automatically retry this
source until a bounded collection strategy is tested.

## Rollback / recovery state

No application or data change was made, so no rollback is required. Persistent
data, backups, migrations, and public CTI evidence remain intact. The incident
is unresolved at the source/provider boundary and remains monitor-visible.

## Recovery-job follow-up (03:31Z cooldown suppression)

- **Latest evidence:** event `89795e77-e771-4192-9045-8e08943c24d4`, observed
  `2026-09-13T03:31:23.754187+00`, state `actionable_failure`, correlation
  `eb352661-9fc9-472a-99e6-6e7548a67cbf`, run
  `5caec866-d2eb-51b1-905f-ecc8a66da107`, endpoint/status
  `http://web:8000/api/v1/ops/run-status` / HTTP 200. A later read at
  `2026-09-13T03:33:23.900880+00` refreshed the same actionable state with event
  `edc0fd33-0f53-4b24-814c-bea916139a05` and correlation
  `ee8350e1-ffc1-4a2c-a4a2-bf3040aeb791`.
- **Gate:** suppressed at `2026-09-13T03:31:49.888125+00` because the 30-minute
  recovery cooldown was active. No retry, restart, deployment, migration,
  response-limit change, credential change, or data mutation was performed.
- **Verification:** the monitor evidence remained actionable for the same failed
  run; the recovery lock was absent after the prior failed attempt. The stack
  remains healthy and the source/provider diagnosis is unchanged.
