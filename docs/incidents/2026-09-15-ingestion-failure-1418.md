# CTI-Hermes production ingestion failure diagnostic (14:18Z)

## Classification

- Recorded: 2026-09-15T14:18:00Z
- Impact: partial collection degradation. Latest run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox freshness and full-success freshness remain stale; reports and publications have not advanced since 2026-09-11T22:24:37Z.
- Cause confidence: high for the deployed ThreatFox response-size boundary; low-to-medium for upstream payload growth.
- Data integrity: preserved. Successful-source data and failed-source evidence remain persisted; no data, volume, backup, migration, credential, publication, or application mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`. Per the Compose configuration, the authoritative fallback was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before gate evaluation:

- state: `actionable_failure`
- event_id: `b36f9a1d-0efe-4dd7-8279-d50d022d38fa`
- observed_at: `2026-09-15T14:16:38.009300+00:00`
- correlation_id: `ac648d69-58a0-4b96-aeee-564ba26575b3`
- endpoint/status: `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- latest-attempt run_id: `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- full-success signal/run_id: `stale_data` / `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal/detail: `actionable_failure` / `1 source(s) failed`

## Recovery gate

The shared recovery gate was evaluated after reading the evidence, using its configured 1,800-second cooldown and `/runtime` lock:

- decision: `allowed=false`
- reason: `recovery cooldown is active`
- gate event/correlation/run: `b36f9a1d-0efe-4dd7-8279-d50d022d38fa` / `ac648d69-58a0-4b96-aeee-564ba26575b3` / `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- result: suppressed event appended to `/runtime/recovery-events.jsonl`
- read-back: `/runtime/recovery.lock` absent; previous attempt state was `2026-09-15T13:47:12.847451+00`

No retry, restart, deployment, migration, source-limit change, credential change, or destructive recovery was attempted.

## Evidence collected

- Repository/release: `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and left untouched.
- Application/version/image: `/version` returned HTTP 200 and `{"name":"hermes-cti","version":"0.1.0"}`. Application containers use `cti-hermes:local`; web, scheduler, and monitor started 2026-09-12T12:55:15Z/20Z.
- Container state: web, scheduler, monitor, PostgreSQL, and backup are running and healthy, restart count 0, exit code 0, OOM false. Worker is exited code 0 by design (`restart: no`) and is not the ingestion owner. No application restart/die event was observed; Docker event output was dominated by health-check exec activity.
- Health/readiness: web `/health/live` HTTP 200 `{"status":"ok"}`; `/health/ready` HTTP 200 with configuration and database `ok`.
- Scheduler/monitor: scheduler logs report `source collection failed`; scheduler heartbeat is present and current. Monitor repeatedly reports `last successful run stale, latest ingestion attempt failed`.
- Database/migrations: `pg_isready` succeeded; database size is 195 MB; Alembic revision is `0015_contradiction_lifecycle`. Latest run is `failed`, started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, with 38 total, 37 successful, 1 failed, 13,108 new documents, error summary `1 source(s) failed`. The latest usable/full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, status `completed`, completed `2026-09-11T12:06:50.050468Z`, with 38/38 sources and 23,841 new documents. The authoritative schema has 28 runs, 26 failed, 33,797 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediation records, and 11 relationships. No application migration or database-connectivity failure was observed.
- Failed source: `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, `error_classification=oversized_response`, detail `response exceeds 10485760 bytes`. Persisted source configuration has `max_response_bytes=10485760`, configuration version 2, seven consecutive failures, last successful retrieval `2026-09-11T12:06:49.272951+00`.
- Resources: root filesystem 43% used with 279G available; host memory 62 GiB total with 49 GiB available; load average 0.32/0.56/0.56; open-file limit 4096. No disk, memory, or descriptor exhaustion indication.
- Backup: backup container healthy. Latest metadata points to `/backups/hermes-20260915T125523Z.dump.enc`, completed `2026-09-15T12:55:26Z`, 24,823,024 bytes, SHA-256 `3a8850bba120e42275736ff70b5df60759d48fb7ac6b15b2d7df716175dbc3cb`. Restore/checksum verification was not run.
- Certificate/proxy: Caddy logs show successful local certificate renewal and reload for `hermes.cti.scogin.dev` and `matrix.scogin.dev`; no certificate or proxy failure was observed. Two unrelated client-disconnect warnings were present.
- Configuration/deployment: checked-out `config/sources.json` contains a pre-existing undeployed ThreatFox `max_response_bytes=52428800` change, while production persisted configuration remains 10 MiB. Compose validation could not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production failure evidence.

## Diagnosis, rollback, and prevention

The immediate cause is source/provider-specific: the deployed ThreatFox implementation rejects a response larger than 10 MiB. Web, proxy, scheduler, worker, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was correctly suppressed by the cooldown gate.

- Service state: web/readiness/database healthy; scheduler alive; one source collection degraded; full-success, analyst, and publication freshness stale.
- Action: diagnosis and gate bookkeeping only; suppressed event recorded and verified. No production state mutation.
- Rollback: not applicable; no production application or data mutation occurred.
- Prevention: validate a bounded/paginated ThreatFox request or the existing 50 MiB configuration with memory/decompression analysis and regression coverage, then deploy only via `./scripts/update-app.sh` when explicitly authorized. Reconcile the missing cron export for `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables, fix operator probes to the singular schema, and separately perform encrypted-backup restore verification.
