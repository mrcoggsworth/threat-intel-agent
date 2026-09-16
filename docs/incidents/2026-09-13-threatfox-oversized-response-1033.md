# Production ingestion incident: ThreatFox oversized response (10:33Z)

- **Recorded:** `2026-09-13T10:33:45+00:00`
- **Monitor evidence observed:** `2026-09-13T10:30:54.536781+00:00`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `7e75843e-f1ce-4f99-9579-37c923f366e0`
- **Correlation:** `f55fce69-346e-4b2e-86d8-70f21c234c31`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact and data state

The latest persisted ingestion attempt is failed but partially usable: 37 of 38
sources succeeded, 5,943 documents were newly persisted, and ThreatFox Recent
Indicators produced no items. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468+00:00`. Current persisted projections are 186 reports,
201 report versions, 201 publications, 378 detections, 201 hunts, 201
remediation records, and 11 relationships; latest publication is
`2026-09-11T22:24:37.163555+00:00`.

No evidence of data deletion, volume deletion, database reset, migration rewrite,
backup mutation, credential rotation, or public-assessment editing was found.

## Diagnosis and evidence

High confidence: deterministic ThreatFox/provider bounded-response failure, not a
web, proxy, scheduler, database, disk, backup, migration, or certificate outage.
The ThreatFox `source_run` row is `failed`, has no HTTP status, zero items and
retries, `cache_state=miss`, `error_classification=oversized_response`, and
`error_detail=response exceeds 10485760 bytes`.

- Web, scheduler, and monitor are running and healthy with zero restarts.
- The worker is intentionally exited 0 with message `reserved for a later
  analysis phase`; it is not a crash-loop.
- Web liveness and readiness both returned HTTP 200; readiness reported
  configuration and database `ok`.
- PostgreSQL is accepting connections; stored Alembic revision is
  `0015_contradiction_lifecycle` (the image-side Alembic command could not connect
  to its default localhost URL, so no migration was run).
- Scheduler heartbeat was fresh at `2026-09-13 10:33:24+00`.
- Running application image is tag `cti-hermes:local`, image ID
  `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`;
  Compose image label is
  `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`.
  Repository HEAD is `c925cd5bbb1b2c872841205b90ea05ea4636da76`; the working tree
  had pre-existing unrelated changes.
- Host root and Docker storage are 42% used with 280G available; 52GiB memory is
  available; open-file limit is 4096. No resource pressure was observed.
- Encrypted backup artifacts and `latest.metadata` are present. Metadata is mode
  600, 198 bytes, timestamped `2026-09-12T12:55:18Z`; no backup write occurred.
- Caddy proxy logs show successful local certificate renewals and no CTI upstream
  outage. The certificate for `hermes.cti.scogin.dev` is currently valid through
  `2026-09-13T19:39:23Z`, but remains below the configured minimum-lifetime
  threshold and is a separate renewal risk.
- Repository-side Compose validation was not possible because this cron shell
  lacks production-only `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables.

## Recovery gate and action

The gate was evaluated using the current actionable evidence and recorded gate
event `7da1957c-ff0e-4c2f-a64b-6b093d615db8` with correlation
`3db3cf73-48ab-4fad-ae2c-7ffee7f77585`. Recovery was **suppressed** because the
30-minute cooldown was active after the prior attempted recovery at
`2026-09-13T10:17:00.918437+00`. The lock was absent. No retry, restart,
deployment, migration, response-limit change, credential change, or data
mutation was performed. Re-running the unchanged ingestion would reproduce the
same bounded-response failure and add provider load without repairing it.

## Prevention and rollback

The smallest safe action is abstention. Validate pagination, provider-side
filtering, or an alternate ThreatFox endpoint against an offline fixture before
changing the 10 MiB response cap. Add or retain a regression fixture for
oversized responses and preserve failed source rows and partial-run visibility.
Renew the certificate before its minimum-lifetime threshold is breached. No
rollback is required because no application or database change was made.
