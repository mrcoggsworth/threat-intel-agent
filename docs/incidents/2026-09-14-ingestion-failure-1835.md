# CTI-Hermes ingestion recovery incident — 2026-09-14 18:35Z

## Status

- **Impact:** the ad-hoc recovery collection completed with partial coverage and
  `failed` status. 37 of 38 sources completed; ThreatFox failed. The latest
  full-success run remains 2026-09-11, so freshness and full-success guarantees
  remain degraded.
- **Monitor evidence:** `/runtime/monitor-evidence.json` in
  `cti-hermes-monitor-1` (the cron environment did not export
  `HERMES_MONITOR_EVIDENCE_FILE`).
- **Monitor event:** `event_id=b4840248-0222-45aa-ab33-ae55d896cf56`,
  `observed_at=2026-09-14T18:30:12.415446+00:00`,
  `correlation_id=a4847443-7c8b-4107-85be-1e670f6b3af6`, prior failed
  `run_id=3848465e-e2a0-572a-b522-4c768d790284`.
- **Monitor signal:** endpoint `http://web:8000/api/v1/ops/run-status`, HTTP
  200; `latest_ingestion_attempt=actionable_failure`, with one failed source;
  `full_success_freshness=stale_data`.
- **Recovery gate:** allowed after cooldown; attempted event was recorded and
  completed with outcome `failed`. No destructive recovery, deployment,
  migration, volume operation, credential change, or database repair was done.

## Recovery attempt

- **Trigger:** `fbd4aefa-e50d-4760-8b01-83e74b817c3f`
- **Recovery run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- **Readiness before trigger:** `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`
- The collection endpoint reported `running` after source processing even though
  application logs recorded terminal completion. PostgreSQL verification is
  authoritative: the run row is present as `failed`, started
  `2026-09-14T18:32:12.667740+00`, completed
  `2026-09-14T18:33:07.628491+00`. The status endpoint's in-memory state did
  not converge and continued to report `running`.
- The run log recorded `error_classification=oversized_response` for
  `threatfox-recent-indicators-abuse-ch`; all observed other source completions
  were successful. This is consistent with the prior recurring failure and is
  the leading cause (high confidence).

## Evidence and service state

- Web, monitor, scheduler, and PostgreSQL containers were running and healthy;
  restart counts were zero. The worker container was exited with code 0 from two
  days ago, but the authenticated collection executed in the web process.
- PostgreSQL accepted connections; migration revision is
  `0015_contradiction_lifecycle`. No database initialization or schema change
  was performed. Existing ingestion totals are 2 completed and 25 failed runs;
  the recovery run is persisted and no data deletion was observed.
- Host disk was 43% used (279G available), memory had approximately 55G
  available, swap use was negligible, and the shell file-descriptor limit was
  4096. No resource exhaustion evidence was found.
- Compose config validation could not be completed from the cron environment:
  protected `HERMES_SECRET_DIR` and immutable `HERMES_IMAGE` variables were not
  exported. This is an operational configuration gap, not authorization to
  reconstruct secrets or update the stack.
- Backup metadata and certificate paths were not readable at their configured
  host locations during this run; backup/certificate freshness therefore
  remains unverified. No backup or certificate was modified.
- Running image is `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
  Repository HEAD is `c925cd5bbb1b2c872841205b90ea05ea4636da76`; the working tree
  already contained broad unexplained changes before this incident and was not
  modified by recovery.

## Cause and data integrity

Primary cause is the recurring ThreatFox oversized-response failure. Secondary
operational issue is status publication divergence: the collection status
endpoint retained `running` after PostgreSQL and logs recorded `failed`. The
monitor correctly preserved partial failure and did not treat the run as a
full-success run. No evidence of database corruption, volume loss, or public
publication mutation was found.

## Follow-up and rollback

- Do not retry repeatedly during the recovery cooldown.
- Under explicit maintenance/deployment authorization, bound or paginate the
  ThreatFox request (or validate an alternate endpoint) against an offline
  fixture, preserve the `oversized_response` classification, and deploy through
  `./scripts/update-app.sh` only after reconciling the persisted source
  configuration with `config/sources.json`.
- Add a regression test for the oversized ThreatFox response and a contract test
  ensuring the asynchronous collection status converges from `running` to the
  persisted terminal state after worker/web completion.
- Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in the
  recovery cron environment while retaining the container-mounted evidence
  fallback. Verify backup metadata and certificate state from their protected
  locations in the next maintenance run.
- Rollback: no application change was made; no rollback is required. If a later
  compatible deployment fails health checks, use the previous stable commit and
  `./scripts/update-app.sh`. Never delete volumes or reset migrations.
