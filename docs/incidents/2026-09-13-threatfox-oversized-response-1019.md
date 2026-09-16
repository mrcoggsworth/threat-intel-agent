# Production ingestion incident: ThreatFox oversized response (10:19Z)

- **Observed:** `2026-09-13T10:16:53.514816+00:00`
- **Monitor state:** `actionable_failure`
- **Event:** `5a0acd43-2cb3-4c3a-86f1-debd03bf02ca`
- **Correlation:** `99867e3a-53f8-45a2-b94b-e2779b3eff09`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200

## Impact

The latest persisted run remains failed but partially usable: 37 of 38 sources
completed, 5,943 new documents were persisted, and ThreatFox produced no items.
The latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, started at
`2026-09-11T12:06:01.816497+00`. Reports remain 186 and publications 201; the
latest publication is `2026-09-11T22:24:37.163555+00`.

## Diagnosis and evidence

High confidence: deterministic ThreatFox provider/source-boundary failure, not a
web, proxy, scheduler, database, disk, backup, migration, or certificate outage.
The source run records `status=failed`, `http_status=NULL`, `item_count=0`,
`error_classification=oversized_response`, and `response exceeds 10485760 bytes`.
The stored ThreatFox configuration is version 2 with a 10 MiB cap and three
consecutive failures. Repository working-tree evidence contains an uncommitted
50 MiB source-cap change, but the running image remains `cti-hermes:local` with
image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`;
that change was not deployed because the tree contains unrelated pre-existing
changes and deployment would be unsafe without review.

Web, scheduler, monitor, backup, and PostgreSQL are healthy with zero restarts;
the worker is intentionally exited 0 (`restart: no`). The scheduler heartbeat is
fresh. PostgreSQL accepts connections and reports Alembic revision
`0015_contradiction_lifecycle`. Host disk is 42% used with 280G available,
52 GiB memory available, and open-file limit 4096. The latest encrypted backup
metadata is present and completed `2026-09-12T12:55:18Z`. The local TLS
certificate is valid until `2026-09-13T19:39:23Z`, below the configured 14-day
renewal threshold, but unrelated to this ingestion failure.

## Recovery gate and action

The recovery gate acquired the actionable evidence for event
`5a0acd43-2cb3-4c3a-86f1-debd03bf02ca` at `2026-09-13T10:17:00.918437+00`.
It was completed with outcome `failed`; the recovery lock was verified absent.
No retry, restart, deployment, migration, response-limit change, credential
change, or data mutation was performed. Re-running unchanged ingestion would
reproduce the deterministic oversized-response failure.

## Prevention and rollback

Validate pagination, provider-side filtering, or an alternate ThreatFox endpoint
against an offline fixture before changing the bounded response policy. Review
the existing source-cap change, add a regression fixture, and deploy only through
`./scripts/update-app.sh` after isolating unrelated working-tree changes. Renew
the certificate before the minimum-lifetime threshold. No rollback is required;
no application or database change was made.
