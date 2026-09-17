# Production ingestion incident: actionable failure, recovery cooldown suppression (04:04Z)

- **Observed:** 2026-09-17T04:04:24.106355+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `fdd79477-e378-4c3b-8fa1-a76178c6f141`
- **Monitor correlation:** `8f1ff4b1-ab25-4e30-bfb6-3db08a28da88`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Ingestion run:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Failure signal:** `latest ingestion attempt failed`; detail `1 source(s) failed`

## Impact

The 2026-09-17 02:00Z collection is partial, not a total outage: 37 of 38 enabled sources completed and 29,841 new source documents were persisted. The run is correctly recorded as `failed` because one source failed. The latest full-success run is 2026-09-16 02:00Z (`ff79134f-5fbf-5469-ba5a-80b739ee58b9`). Reports and publications are materially staler than ingestion: 186 reports, 201 report versions, and 201 publications; each latest timestamp is 2026-09-11T22:24:37Z.

## Evidence and diagnosis

- Latest run: started `2026-09-17T02:00:00.087498Z`, completed `2026-09-17T02:00:54.951189Z`, totals 38 / 37 successful / 1 failed, error summary `1 source(s) failed`.
- Failed source: **Krebs on Security**, `https://krebsonsecurity.com/feed/`; `content_type_error`, `response content type did not match source policy`, HTTP status absent, zero items.
- A bounded live HEAD check at diagnosis time returned HTTP 200, `application/rss+xml; charset=UTF-8`, 168491 bytes, indicating the upstream currently serves an acceptable RSS type. This supports a transient/upstream content-negotiation or response variation cause; confidence medium. No evidence implicates PostgreSQL, web, scheduler, proxy, disk, memory, file descriptors, certificate, backup, or deployment as the source of this ingestion failure.
- Australian Cyber Security Centre remains a separate persistent source failure (last failure 2026-09-10T14:29:53Z, eight consecutive failures); it did not fail in the current run and is not the current event's failed source.

## Runtime and integrity checks

- Application version endpoint: `hermes-cti` `0.1.0`.
- Running application image: `cti-hermes:local`, image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`; web/monitor/scheduler/backup containers were created 2026-09-15T20:53Z and have restart count 0.
- Web liveness/readiness: both HTTP 200; readiness reported configuration/database `ok`.
- Scheduler heartbeat was current at diagnosis (`2026-09-17T04:04:08Z`); scheduler remained running and logged only the expected `source collection failed` summary.
- Worker is exited 0/unhealthy with the reserved later-phase worker message; this is not the collection execution path and did not change during this incident.
- PostgreSQL 16.14 is healthy and accepting connections; Alembic revision is `0015_contradiction_lifecycle`. Database size is 273 MB. No pending migration was established from the container because `uv` is not installed there; no migration error or database integrity error was observed in application/runtime evidence.
- Host capacity: filesystem 43% used with 277 GB available; 62 GiB RAM with approximately 51 GiB available; process file-descriptor limits and observed PID-1 descriptor counts were normal.
- Latest encrypted backup metadata: `/backups/hermes-20260916T205359Z.dump.enc`, completed 2026-09-16T20:54:01Z, 26,683,360 bytes; SHA-256 read-back matched metadata (`57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`).
- Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev`; live TLS inspection showed validity through 2026-09-17T11:39:23Z. No certificate cause found.

## Recovery gate and actions

The authoritative evidence was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` because the cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`. The shared 1,800-second cooldown and `/runtime` lock were evaluated before recovery. Gate event `dc3a7a76-19e6-4939-b218-c72cc7ebcb96` was recorded as `suppressed` at `2026-09-17T04:02:24.192767Z`, reason `recovery cooldown is active`, for the then-current event `abd4f0d6-a248-47d7-92c4-f1d388542d65`, correlation `49a9c592-22db-49df-bb8b-3351c9979019`, and the same run. Read-back verified `/runtime/recovery.lock` absent.

No retry, restart, deployment, migration, source edit, credential change, publication mutation, restore, or destructive recovery was performed. Failed run/source records and successful partial ingestion remain preserved. Rollback is not applicable.

## Prevention / follow-up

1. Add a mocked regression fixture for a content-type mismatch followed by a valid RSS response, and consider a narrowly scoped tolerant content-type policy only after reviewing source safety and provenance requirements.
2. Investigate the persistent ACSC failure separately; do not conflate it with this event.
3. Reconcile the public ops projection routes returning HTTP 404 in direct container checks despite monitor evidence recording HTTP 200 for the same endpoint; this is an observability/configuration follow-up, not a recovery authorization.
4. Keep retries gated; an unchanged retry is not justified while the cooldown is active.
