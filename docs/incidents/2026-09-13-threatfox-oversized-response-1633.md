# Production ingestion incident: ThreatFox oversized response (16:33Z)

- **Recorded:** 2026-09-13T16:33:00Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `b79edc5d-5282-44b7-af81-3c56aac8387e`
- **Observed at:** `2026-09-13T16:30:20.059110+00:00`
- **Correlation:** `6ac582aa-6820-4fe2-b983-1a30e231c8c4`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Post-action evidence refresh:** event `d4b34dbd-afb7-47c0-9421-5c266bd77e27`, observed at
  `2026-09-13T16:33:20.269516+00:00`, correlation
  `5ea07d31-b29b-4b51-9032-3f26313d9241`; state remained `actionable_failure`
  for the same run and endpoint/status.

## Impact and data-integrity state

The latest persisted ingestion attempt is failed but usable for successful
sources: 37 of 38 sources completed and 5,943 documents were newly persisted.
ThreatFox Recent Indicators (Abuse.ch) returned no items. The latest full-success
run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`. The latest usable attempt completed at
`2026-09-13T02:00:07.873460Z`; no report or publication mutation was performed.
Successful-source documents and failed-source evidence remain persisted and
visible.

No evidence deletion, volume deletion, database reset, migration rewrite,
backup mutation, credential rotation, or public-assessment edit occurred.

## Diagnosis and evidence

**Cause confidence: high.** This is a deterministic ThreatFox/provider bounded-
response failure, not a web, proxy, scheduler, worker, database, disk, backup,
migration, or service-restart outage. The failed `source_run` records
`status=failed`, `http_status=NULL`, `item_count=0`, `retry_count=0`,
`cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`. The persisted run records
`total_sources=38`, `successful_sources=37`, `failed_sources=1`,
`new_documents=5943`, `application_version=0.1.0`, and configuration hash
`d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.

Read-only verification:

- Web, scheduler, monitor, backup, and PostgreSQL containers are running
  healthy with restart count 0 and no OOM termination. PostgreSQL accepts
  connections (`pg_isready`); Alembic is at `0015_contradiction_lifecycle`.
- Private run-status returned HTTP 200. `latest_usable` is the partial latest
  attempt and `latest_full_success` is the 2026-09-11 run.
- Scheduler heartbeat was fresh at `2026-09-13T16:31:26Z`; monitor evidence was
  fresh at `2026-09-13T16:30:20Z`.
- Host disk is 43% used with 280G available; memory reports 52GiB available;
  open-file limit is 4096.
- Encrypted backup artifacts and metadata are present; the latest artifact is
  `hermes-20260913T125518Z.dump.enc`, 22,110,800 bytes, with mode-600 metadata.
- Certificates on local ports 9443 and 9444 expire at `2026-09-14T03:39:23Z`.
  This is an urgent separate certificate-renewal risk because it is below the
  configured 14-day minimum.
- Docker events in the observation window showed diagnostic exec activity and
  no CTI-Hermes service restarts.
- Repository HEAD is `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, three
  commits ahead of `origin/main`; the working tree contains pre-existing broad
  uncommitted changes, including source configuration changes. No deployment
  was performed.

## Recovery gate and action

The recovery gate acquired the actionable evidence after its cooldown and lock
checks. It recorded attempted event
`8bec6bba-725b-42e3-93ae-9c912691f406` with correlation
`66f9e4d6-2408-41b8-b3da-3fe90d9858da`, then recorded completion with outcome
`failed` at `2026-09-13T16:33:00.808501+00`. The recovery lock was verified
absent. No retry, restart, deployment, migration, response-limit change,
credential change, or data mutation was performed: re-running unchanged
ingestion would reproduce the provider bounded-response failure.

## Prevention and rollback

Validate pagination, provider-side filtering, or an alternate ThreatFox
endpoint against an offline fixture before deploying a focused source change.
Retain the oversized-response regression fixture and partial-run visibility.
Review the pre-existing local configuration change separately before any
application update. Renew the certificate before
`2026-09-14T03:39:23Z` using the certificate runbook and a verified rollback
path. No rollback is required because no application or data change was made.
