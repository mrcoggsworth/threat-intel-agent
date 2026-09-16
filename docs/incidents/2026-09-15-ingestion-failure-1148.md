# Production CTI ingestion incident: ThreatFox oversized response (11:48Z)

## Summary

- **Observed at:** 2026-09-15T11:48:27.354316+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `aa520827-7604-4cd8-8d86-79f778c7e784`
- **Correlation:** `506af131-5d6e-44e9-8c15-7af96ee301c9`
- **Latest failed run:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Full-success freshness signal run:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200 for both signals
- **Impact:** the 2026-09-15 02:00Z collection persisted 37/38 source results and 13,108 documents, but is terminal `failed`; ThreatFox coverage is unavailable and full-success freshness remains stale. Usable partial-source data remains available. Reports/publications have not advanced since 2026-09-11T22:24:37Z.

## Evidence and diagnosis

The latest run was `collect_once`, application version `0.1.0`, started at 2026-09-15T02:00:00.049118Z and completed at 02:00:54.439155Z. It has `total_sources=38`, `successful_sources=37`, `failed_sources=1`, and `error_summary=1 source(s) failed`.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its source result is `status=failed`, `item_count=0`, `http_status` unset, `error_classification=oversized_response`, and `error_detail=response exceeds 10485760 bytes`. The persisted source row records `max_response_bytes=10485760`, `configuration_version=2`, `last_successful_retrieval=2026-09-11T12:06:49.272951Z`, `last_failure=2026-09-15T02:00:54.421527Z`, and `consecutive_failure_count=7`.

The checked-out but not deployed working-tree change in `config/sources.json` raises this source limit to 52428800 bytes. The running image remains `cti-hermes:local` with image digest `sha256:0e5b124207549321f124f73c4ae1a4d56a945e683f9f09849651c3ea952da291`; the database still has the 10 MiB value. This is strong evidence of a deterministic source/provider response-size mismatch, not a web, proxy, scheduler, worker, database, disk, memory, migration, or persistence outage. Raising the limit or changing the request requires validation and explicit maintenance authorization; it was not done.

Supporting service evidence:

- Web container: running, healthy, restart count 0; `/health/live` and `/health/ready` returned HTTP 200, with database readiness `ok`.
- Scheduler: running, healthy, restart count 0; `/runtime/scheduler.heartbeat` was current at 2026-09-15T11:47:44Z.
- Worker: exited 0 two days ago and has `restart: "no"` by design; no worker crash evidence was found.
- PostgreSQL: running healthy, accepting connections; PostgreSQL 16.14; database size 195 MB; 8 active connections. No data mutation was performed.
- Migration revision: database `0015_contradiction_lifecycle`; image reports the same head. Alembic online `current` could not connect because the command used localhost inside the web container, while direct PostgreSQL connectivity succeeded; this is diagnostic command topology, not evidence of database failure.
- Disk/memory/file descriptors: root filesystem 43% used with 278 GB available; 62 GiB RAM with 51 GiB available; host `ulimit -n` 4096.
- Backups: backup container healthy; encrypted backup and metadata files exist through `hermes-20260914T125520Z`, with `/backups/latest.metadata` present. Latest backup is approximately 23 hours old at observation; restore verification was not performed in this diagnosis-only run.
- Certificate: Caddy served a local-authority certificate valid 2026-09-15T07:39:23Z through 19:39:23Z. It is not the ingestion cause, but the short remaining lifetime and local CA trust should be handled separately. The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; evidence was read from the configured `/runtime/monitor-evidence.json` container fallback.
- Proxy logs showed only unrelated incomplete client responses; no CTI upstream failure. The monitor's internal ops route returned 200, while a localhost web check for the same route returned 404, indicating a route/topology mismatch worth separate investigation.

## Recovery gate and actions

The shared recovery gate was evaluated after reading actionable evidence, with the configured 1,800-second cooldown and `/runtime` lock. It acquired attempted event `fe5670a0-9ba9-4b92-9082-af788f5748ee` at 2026-09-15T11:46:55.650026Z, using correlation `b19ebb5c-6381-4210-9dcd-d9ff71829e3f` and run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`. Because this request authorizes diagnosis only, the gate was completed with outcome `suppressed` at 2026-09-15T11:47:03.873336Z. Read-back verified the attempted/completed audit records and that `/runtime/recovery.lock` is absent.

No ingestion retry, restart, deployment, migration, source-limit change, credential change, volume/data deletion, backup deletion, or publication mutation was performed. The failed run/source records and partial successful-source data remain preserved.

## Prevention and follow-up

1. Under explicit maintenance authorization, validate a bounded/paginated ThreatFox request or the staged 50 MiB limit against an offline oversized-response fixture; assess memory/decompression impact and add regression coverage.
2. Deploy only through `./scripts/update-app.sh`, then verify persisted source configuration, failed-source classification, full-success/usable-run status, monitor evidence, and publication freshness.
3. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables while retaining the container fallback.
4. Investigate the internal-versus-localhost `/api/v1/ops/*` route mismatch, certificate trust/lifetime, and stale backup publication/restore verification separately.

**Cause confidence:** high for ThreatFox response-size enforcement mismatch; low uncertainty remains only around the provider's current payload growth and whether the staged configuration is safe to deploy.
**Rollback:** not applicable; no production application or data mutation occurred. A future compatible deployment should roll back by reverting the focused change and rerunning `./scripts/update-app.sh` if health or bounded-ingestion checks fail.
