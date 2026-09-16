# Production ingestion incident: ThreatFox bounded-response failure (00:16Z)

## Classification

- **Impact:** CTI ingestion is partially degraded. Latest run `20c8d81a-48e4-5215-8292-63a72ddac05d` processed 37/38 sources and persisted 12,831 new documents; ThreatFox coverage failed and full-success freshness is stale.
- **Cause confidence:** high for the immediate cause: the deployed ThreatFox response-size guard rejected a response larger than 10 MiB. Confidence is low-to-medium for why the provider payload grew.
- **Data integrity:** no database reset, volume deletion, migration, credential rotation, evidence deletion, publication mutation, retry, restart, or deployment was performed. Failed-source and partial-run records remain preserved.

## Authoritative monitor evidence

Read first from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` because `HERMES_MONITOR_EVIDENCE_FILE` was not exported in the cron shell:

- **state:** `actionable_failure`
- **event_id:** `c9bd8357-9ea4-4867-9b6a-aa9c91df1adc`
- **observed_at:** `2026-09-15T00:15:37.110828+00:00`
- **endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **correlation_id:** `7de5858d-4873-4660-9582-e5ea0c1e0703`
- **run_id:** `20c8d81a-48e4-5215-8292-63a72ddac05d`
- Signals: full-success freshness `stale_data` for run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest ingestion attempt `actionable_failure`, detail `1 source(s) failed`.

## Recovery gate

The configured 1,800-second recovery gate was evaluated after evidence collection. The prior attempt at `2026-09-15T00:01:33.678994+00Z` is inside cooldown, so no recovery lock was acquired and no recovery action was attempted.

- **Gate decision:** `allowed=false`; reason `recovery cooldown is active`.
- **Suppressed event:** `c9bd8357-9ea4-4867-9b6a-aa9c91df1adc`, recorded `2026-09-15T00:16:32.940475+00Z`.
- **Previous gate event:** `8b01aa44-bf9f-4cb9-9f98-25b2808c11b2`; audit read-back shows `attempted` then `completed outcome=suppressed`.
- **Lock read-back:** `/runtime/recovery.lock` absent.

## Evidence collected

- **Repository/release:** remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch `main`; HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; branch is ahead of `origin/main` by 3 commits. Working tree has broad pre-existing modifications, deletions, and untracked files; no application file was changed by this incident.
- **Application/image:** containers use `cti-hermes:local`, version `0.1.0`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`. Web, scheduler, monitor, PostgreSQL, and backup containers are running healthy with restart count `0` and `OOMKilled=false`; started 2026-09-12 (PostgreSQL 2026-09-05).
- **Database/migrations:** `pg_isready` accepted connections; database/user `hermes|hermes`; Alembic revision `0015_contradiction_lifecycle`. No pending or failed migration evidence was found.
- **Runs/source:** latest run status `failed`, started `2026-09-14T18:32:12.667740+00`, completed `2026-09-14T18:33:07.628491+00`, total 38, successful 37, failed 1, new documents 12,831. `threatfox-recent-indicators-abuse-ch` has `status=failed`, `item_count=0`, no HTTP status, `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`, last successful retrieval `2026-09-11 12:06:49.272951+00`, consecutive failures `6`, configured persisted limit `10485760` bytes.
- **Health/readiness:** internal monitor checks reached run-status HTTP 200; container health is healthy. Host-path curl returned HTTP 308 redirect for both health paths and was not treated as an outage. No service restart or proxy action was needed.
- **Logs/events:** monitor repeatedly reports only stale full success plus failed latest attempt. Scheduler emitted no useful diagnostic output. PostgreSQL showed a prior operator query error for nonexistent plural table `ingestion_runs`; this is diagnostic schema drift, not an application transaction failure. No container events were observed in the checked window due Docker event format incompatibility; inspect/restart evidence independently showed no restarts.
- **Resources:** root filesystem 43% used with 279G available; memory 62Gi total / 52Gi available; load `0.95 0.48 0.39`; open-file limit 4,096. No resource exhaustion indication.
- **Backups:** read-only backup volume contains encrypted artifacts through `/backups/hermes-20260914T125520Z.dump.enc`, 22,608,400 bytes. `/backups/latest.metadata` reports completion `2026-09-14T12:55:23Z` and SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Restore verification was not run.
- **Certificate/proxy/config:** certificate expiry was not independently verified from this cron environment; no proxy or certificate action was taken. Checked-in `config/sources.json` contains a pre-existing staged ThreatFox limit increase to 50 MiB, but the running image still uses the persisted 10 MiB limit. No deployment/config update was run.

## Diagnosis and action

This is a source/provider-specific deterministic response-size failure, not a web, proxy, scheduler, database, disk, memory, certificate, backup, or migration outage. Public CTI from successful sources and usable partial-run data remain available, while ThreatFox coverage and full-success freshness are degraded. Recovery was suppressed by cooldown; no retry, restart, `./scripts/update-app.sh`, migration, or data mutation was authorized or performed.

## Prevention and follow-up

1. Under explicit maintenance/deployment authorization, validate ThreatFox filtering/pagination or an alternate endpoint with an offline fixture, retain an oversized-response regression test, reconcile the staged `config/sources.json` change with the running image, and deploy only via `./scripts/update-app.sh`.
2. After authorized deployment, verify the next source status, full-success/usable-run semantics, monitor evidence, and publication/data integrity.
3. Correct diagnostic queries to the authoritative singular schema names (`ingestion_run`, `source_run`) to avoid PostgreSQL log noise.
4. Export `HERMES_MONITOR_EVIDENCE_FILE` in the recovery cron environment while retaining the container fallback.
5. Run encrypted-backup restore verification and independently verify certificate state in a maintenance window.

**Rollback:** not applicable; no application or data mutation occurred. The recovery lock is absent and the gate audit is preserved.
