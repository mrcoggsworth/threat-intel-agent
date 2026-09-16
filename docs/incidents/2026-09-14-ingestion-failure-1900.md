# CTI-Hermes ingestion failure diagnosis — 2026-09-14 19:00Z

## Status

- **Impact:** ingestion remains degraded. The latest run failed with 37/38
  sources completed; ThreatFox failed. The latest full-success run is still
  `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` from 2026-09-11, so full-success
  freshness and downstream freshness remain stale.
- **Monitor evidence:** authoritative evidence was read from
  `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; the cron shell did
  not export `HERMES_MONITOR_EVIDENCE_FILE`.
- **Monitor event:** `event_id=49f001df-2e82-4194-91d0-06b9df81f7cc`,
  `observed_at=2026-09-14T19:00:14.582374+00:00`,
  `correlation_id=20aefe8f-3984-4089-a6dc-870714e86fb6`,
  `run_id=20c8d81a-48e4-5215-8292-63a72ddac05d`.
- **Monitor signals:** endpoint `http://web:8000/api/v1/ops/run-status`, HTTP
  200. `latest_ingestion_attempt=actionable_failure` with detail `1 source(s)
  failed`; `full_success_freshness=stale_data`.
- **Recovery gate:** evaluated against the same container evidence and state
  directory. The gate recorded suppression event
  `event_id=039b6dac-9cca-4873-9706-68c670648032`, because the 30-minute
  cooldown remained active after the prior attempt. The recovery lock was
  absent. No collection, restart, deployment, migration, or data repair was
  attempted.

## Evidence and service state

- Web, monitor, scheduler, PostgreSQL, and backup containers were running;
  web, monitor, scheduler, PostgreSQL, and backup were healthy. The worker was
  exited with code 0 from two days ago and unhealthy, with its log stating it is
  reserved for a later analysis phase; the collection ran in the web process.
  Application image is `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
  Web/scheduler/monitor restart counts were zero.
- PostgreSQL accepted a live connection. Applied migration revision is
  `0015_contradiction_lifecycle`; checked-in migration head is also 0015, with
  no pending migration evidence. No schema or persistence repair was done.
- Run `20c8d81a-48e4-5215-8292-63a72ddac05d` persisted as `failed`, started
  `2026-09-14T18:32:12.667740+00`, completed
  `2026-09-14T18:33:07.628491+00`, application version `0.1.0`, configuration
  hash `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`,
  with 38 total, 37 successful, 1 failed, and 12,831 new documents.
  `threatfox-recent-indicators-abuse-ch` failed with
  `error_classification=oversized_response` and
  `response exceeds 10485760 bytes`.
- Database integrity evidence is normal: no empty-database condition, volume
  loss, or deletion was observed. Reports: 186; report versions: 201;
  publications: 201. Each latest timestamp is `2026-09-11 22:24:37.163555+00`.
- Scheduler heartbeat was current at `2026-09-14T19:03:07Z`. Web live and ready
  checks returned `{"status":"ok"}` and readiness reported configuration and
  database checks as `ok`. The internal ops routes used by the monitor returned
  404 when queried directly from web in this diagnostic context, while the
  monitor's recorded run-status probe returned HTTP 200; this route-surface
  difference is retained as an operational follow-up, not treated as evidence
  of database failure.
- Host resources were not exhausted: root filesystem 43% used with 279G
  available, approximately 54G memory available, negligible swap use, and
  file-descriptor limit 4096. No Docker container events occurred in the
  observation window.
- Backup state is present and current enough for this check: `/backups/latest.metadata`
  references `hermes-20260914T125520Z.dump.enc`, completed
  `2026-09-14T12:55:23Z`, 22,608,400 bytes, with a recorded SHA-256. Backup
  restore verification was not performed. Caddy is running; mounted cert files
  exist at `/home/cptcoggsworth/caddy/certs/hermes.crt` and `hermes.key`, both
  dated 2026-09-07. Certificate expiry was not asserted from file metadata.
- Repository HEAD is `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, ahead
  of origin by three commits, with broad pre-existing tracked and untracked
  changes. The running Compose project uses `/opt/cti-hermes/env/production.env`.
  Compose validation was not run because the cron shell lacks protected
  `HERMES_SECRET_DIR` and `HERMES_IMAGE`; no secrets were reconstructed.
  Checked-in `config/sources.json` was modified 2026-09-12, while the last
  deployment-related commit is `c925cd5` (2026-09-12 12:52:45Z).

## Diagnosis and action

- **Primary cause (high confidence):** recurring ThreatFox oversized response;
  it is the sole failed source in the latest persisted run and preserves the
  intended partial-failure classification.
- **Secondary issue (medium confidence):** the monitor's internal run-status
  surface and direct web route probe do not agree on route availability; prior
  recovery evidence also recorded status convergence divergence. This did not
  corrupt persistence and was not changed under cooldown.
- **Action:** read-only diagnosis only. Recovery was correctly suppressed by
  the cooldown gate; no destructive recovery, deployment, restart, migration,
  credential rotation, volume operation, or publication mutation occurred.

## Follow-up and rollback

After an explicitly authorized maintenance window and an elapsed gate cooldown,
validate bounded/paginated ThreatFox retrieval against an offline fixture,
preserve `oversized_response`, add the regression test, reconcile persisted
source configuration, and deploy only through `./scripts/update-app.sh`. Add a
contract test for terminal status convergence and reconcile the cron export for
`HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`. Verify
backup restore metadata and certificate expiry from protected locations. No
rollback is required because no application state was changed.
