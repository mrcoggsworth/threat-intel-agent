# Production ingestion incident: ThreatFox bounded-response failure (02:00Z)

## Classification

- **Impact:** ingestion is partially degraded. The latest scheduled run processed 37/38 sources and failed only `threatfox-recent-indicators-abuse-ch`.
- **Cause confidence:** high for the immediate cause: the deployed response-size guard rejected the ThreatFox payload at 10 MiB. Confidence is low-to-medium for why the upstream payload grew.
- **Monitor state:** `actionable_failure`.
- **Data integrity:** no database reset, volume deletion, migration, credential rotation, evidence deletion, restart, rerun, or deployment was performed. Failed run/source records remain preserved.

## Authoritative monitor evidence

The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; per the Compose configuration, the authoritative fallback was read from `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1` before diagnosis:

- `state=actionable_failure`
- `event_id=6ca0d63c-87cb-4ad2-b4c2-bbeee2880334`
- `observed_at=2026-09-15T02:15:45.733366+00:00`
- `correlation_id=27984aa2-b32a-4094-9a78-18388a9ab2e2`
- endpoint `http://web:8000/api/v1/ops/run-status`, HTTP status `200`
- full-success signal: `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal: `actionable_failure`, detail `1 source(s) failed`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`

## Recovery gate

The 30-minute gate acquired the actionable event before diagnosis:

- gate event: `6ca0d63c-87cb-4ad2-b4c2-bbeee2880334`
- correlation: `27984aa2-b32a-4094-9a78-18388a9ab2e2`
- run: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- outcome: `suppressed` because this scheduled request authorizes diagnosis, not recovery/deployment

No recovery action was attempted. The gate lock must be completed and verified absent by the job finalization step.

## Evidence collected

- **Repository/release:** checked-out `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; repository is ahead of `origin/main` by 3 commits and has substantial pre-existing working-tree changes. No reset or cleanup was performed.
- **Application:** running CTI containers use `cti-hermes:local`; web reports application version `0.1.0`. Monitor, web, scheduler, PostgreSQL, and backup are up/healthy with restart count 0. CTI containers started 2026-09-12 around 12:55Z. No deployment or config update ran.
- **Database/migrations:** PostgreSQL accepts connections; `current_timestamp` query succeeded. Alembic revision is `0015_contradiction_lifecycle`; no pending/failed migration was observed. Authoritative tables are singular (`ingestion_run`, `source_run`).
- **Runs/source:** latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` started 2026-09-15 02:00:00.049118Z and completed 02:00:54.439155Z; status `failed`; 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source is `threatfox-recent-indicators-abuse-ch`, with no HTTP status, `item_count=0`, `error_classification=oversized_response`, and `response exceeds 10485760 bytes`. Latest full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed 2026-09-11 12:06:50Z, 38/38.
- **Analysis/publication:** `source_document` has 33,797 rows with latest retrieval 2026-09-15 02:00:54Z. Detection/hunt/remediation/report/report_version/publication rows are 378/201/201/186/201/201, with latest timestamps 2026-09-11 22:24:37Z (reports/publications through 22:24:37.183Z). This incident does not alter analyst-owned conclusions.
- **Services/readiness:** container health is healthy. The host port 8000 is not published, so direct host curl to `127.0.0.1:8000` returned connection refused; this is expected topology, not evidence of web failure. The monitor's internal run-status endpoint returned HTTP 200. Scheduler logs report `source collection failed` without a service crash; monitor logs repeatedly report stale successful run/latest failed attempt.
- **Resources:** root filesystem 43% used with 279G available; host memory 62Gi total/52Gi available; CTI container FD counts are low and no resource-exhaustion signal was found.
- **Backups:** backup container is healthy; latest encrypted artifact is `/backups/hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes, with metadata and SHA-256 metadata present. Restore verification was not run.
- **Certificate/proxy:** Caddy logs show successful local certificate renewal/reload for `hermes.cti.scogin.dev`; the presented certificate is valid 2026-09-14 23:39:23Z through 2026-09-15 11:39:23Z. Host trust verification failed because the local issuer is not trusted by the host curl, not because of an expired certificate. No proxy/certificate cause was found.
- **Configuration/deployment:** the working tree contains an un-deployed `config/sources.json` change adding `max_response_bytes: 52428800` for ThreatFox. The running image did not show that setting, consistent with the persisted 10 MiB guard. No deployment was authorized or executed.

## Diagnosis and action

The web, scheduler, monitor, database, migrations, storage, memory, file descriptors, backups, and TLS are healthy. This is a source/provider-specific ingestion failure: the deployed ThreatFox request exceeded the 10 MiB bounded transport limit. The smallest safe follow-up is to review and test the existing bounded 50 MiB configuration change, assess decompression/memory impact, then deploy only through `./scripts/update-app.sh` under explicit recovery/deployment authorization. Do not bypass the guard or delete failed evidence.

## Prevention and follow-up

1. Add/retain an oversized-response regression fixture and validate bounded ThreatFox filtering/pagination or an alternate endpoint before deployment.
2. Reconcile the missing cron export of `HERMES_MONITOR_EVIDENCE_FILE` while retaining the container fallback.
3. Use singular operational table names in future diagnostics to avoid PostgreSQL log noise.
4. Verify encrypted-backup restore separately; this check verified artifact presence/metadata only.
5. Add source-specific monitor/runbook classification for repeated `oversized_response` failures.

**Rollback:** not applicable; no application or data mutation occurred. If the bounded configuration change is later deployed and fails health or ingestion verification, revert the focused commit and rerun `./scripts/update-app.sh` using the previous stable state.
