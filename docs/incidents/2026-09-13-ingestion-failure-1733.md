# Production ingestion incident: unchanged ThreatFox bounded-response failure (17:33Z)

- **Recorded:** 2026-09-13T17:33:09Z
- **Monitor state:** `actionable_failure`
- **Monitor evidence:** event `4af25afb-7a85-4a83-a387-530b7ecfe4ea`, observed `2026-09-13T17:32:24.544054+00:00`
- **Correlation:** `3b82c3b1-64b2-4769-b6e4-dad01de8ae62`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`

## Impact and diagnosis

The latest persisted attempt remains failed but usable: 37 of 38 sources succeeded and the latest usable projection is the partial run. The latest full-success run remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed `2026-09-11T12:06:50.050468Z`. This is unchanged from the 16:33Z incident and is not a web/proxy/scheduler/database outage.

Cause confidence remains high: the previously recorded source-run evidence identifies ThreatFox Recent Indicators (Abuse.ch) as failing with `error_classification=oversized_response` and `error_detail=response exceeds 10485760 bytes`; 5,943 documents from successful sources and failed-source evidence remain persisted. Re-running unchanged ingestion would reproduce the provider bounded-response failure.

## Read-only verification

- Monitor, web, scheduler, PostgreSQL, and backup containers are running healthy with restart count 0; scheduler heartbeat remained fresh.
- Private run status returned HTTP 200; latest attempt remains failed and latest full-success remains stale.
- PostgreSQL accepts connections. No destructive database operation was performed.
- Host disk is 43% used with approximately 280G available; memory reports approximately 52GiB available; open-file limit is 4096.
- Encrypted backup artifacts and mode-600 metadata remain present, including the 2026-09-13 artifact.
- No service restart, deployment, migration, retry, credential change, volume/data deletion, or publication mutation was performed.
- Repository remains at `c925cd5bbb1b2c872841205b90ea05ea4636da76` on `main`, with pre-existing uncommitted changes; no application update was run.

## Recovery gate and action

The recovery gate acquired the evidence after cooldown/lock checks with attempted event `01f87a1f-d4e5-4170-a983-c38a382261d9`, correlation `afc42308-17f4-468b-8be4-22493515968c`, and run `5caec866-d2eb-51b1-905f-ecc8a66da107`. It was completed with outcome `failed`; the recovery lock was verified absent. No safe reversible recovery action exists for a deterministic provider response-size failure.

## Prevention and rollback

Validate provider-side filtering, pagination, or an alternate ThreatFox endpoint against an offline fixture before deploying a focused source change. Preserve the oversized-response regression fixture and partial-run visibility. Renew the separate certificate risk identified by the prior incident before its recorded expiry. No rollback is required because this diagnosis performed no application or data mutation.
