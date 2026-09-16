# CTI-Hermes production ingestion failure diagnostic (09:01Z)

## Classification

- **Recorded:** 2026-09-15T09:01:55Z
- **Impact:** partial ingestion degradation. Run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f` failed after 37/38 sources and persisted 13,108 new documents. ThreatFox freshness remains stale; full-success, usable-run, analyst, and publication freshness remain stale.
- **Cause confidence:** high for the deployed ThreatFox response-size boundary; low-to-medium for the upstream payload growth.
- **Data integrity:** preserved. Failed-source and successful-source records remain persisted. No retry, restart, deployment, migration, credential, volume, backup, or publication mutation was performed.

## Authoritative monitor evidence

The cron environment did not export `HERMES_MONITOR_EVIDENCE_FILE`; the configured fallback was read first from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`.

- `state=actionable_failure`
- `event_id=2f14f715-1a48-4bba-9551-e8ceb3e37a15`
- `observed_at=2026-09-15T09:01:15.279961+00:00`
- `correlation_id=321987b6-2666-490a-a7fb-411a8b7e1afd`
- endpoint `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- full-success signal `stale_data`, run `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- latest-attempt signal `actionable_failure`, run `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`, detail `1 source(s) failed`

## Recovery gate

The shared 1,800-second cooldown and lock were evaluated before any recovery action. The gate recorded a secret-free suppressed event for monitor event `2f14f715-1a48-4bba-9551-e8ceb3e37a15` at `2026-09-15T09:01:55.994716+00Z`, reason `recovery cooldown is active`. Read-back verified `/runtime/recovery.lock` is absent. No recovery was attempted.

## Evidence collected

- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch is three commits ahead of `origin/main`. Broad pre-existing working-tree changes were observed and not modified.
- **Application/image:** application version `0.1.0`; running image `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T12:54:53Z. Running web, scheduler, monitor, and backup containers started 2026-09-12; PostgreSQL started 2026-09-05.
- **Container/restart state:** web, scheduler, monitor, PostgreSQL, backup, and proxy are up; Hermes services healthy; restart count 0 and OOM false. No relevant container restart event was observed in the two-hour window. Scheduler heartbeat was current at `2026-09-15T09:02:12Z`.
- **Health/readiness:** web `/health/live` and `/health/ready` returned HTTP 200 with `status=ok`; readiness database/config checks were OK. The unauthenticated local `/api/v1/ops/run-status` returned HTTP 404; the monitor's internal authenticated route returned HTTP 200, so this is not treated as a service outage.
- **Ingestion/database:** PostgreSQL accepted connections; Alembic revision is `0015_contradiction_lifecycle`. Latest run started `2026-09-15T02:00:00.049118Z`, completed `2026-09-15T02:00:54.439155Z`, status `failed`, 38 total, 37 successful, 1 failed, 13,108 new documents. Failed source `threatfox-recent-indicators-abuse-ch` has no HTTP status, item count 0, classification `oversized_response`, detail `response exceeds 10485760 bytes`. No pending or failed migration evidence was observed.
- **Run status/downstream:** latest full-success remains `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`. Current persisted totals: reports 186, report versions 201, publications 201, detections 378, hunts 201, remediation 201, relationships 11; latest report/publication timestamp `2026-09-11T22:24:37.163555Z`.
- **Resources:** root filesystem 43% used with 278G available; host memory 51GiB available; load average `0.33/0.27/0.31`; open-file limit 4096. No disk, memory, or descriptor exhaustion indication.
- **Backups:** backup container healthy; latest metadata identifies `hermes-20260914T125520Z.dump.enc`, completed `2026-09-14T12:55:23Z`, 22,608,400 bytes, SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`. Restore verification was not run.
- **Certificate/proxy:** Caddy is up with no restart; local Caddy certificates are present for `matrix.scogin.dev` and `hermes.cti.scogin.dev`. No proxy or certificate failure was indicated by the internal health checks. Tailnet certificate expiry was not re-read because the configured `/var/lib/cti-hermes/tls/fullchain.pem` path is absent on this checkout host.
- **Configuration/deployment:** checked-out `config/sources.json` has ThreatFox `max_response_bytes=52428800`, while the running failure proves the deployed boundary remains 10 MiB. Compose config validation was not run because this cron shell lacks protected `HERMES_SECRET_DIR` and `HERMES_IMAGE`; this is an operator-environment limitation, not production failure evidence.
- **Log noise:** monitor repeatedly reports stale full-success/latest failed attempt. PostgreSQL operational probes include schema-drifted plural-table/column errors in prior diagnostics; authoritative singular-schema queries succeeded. These are not application transaction failures.

## Diagnosis and action

The failure is source/provider-specific: the deployed implementation rejects the ThreatFox response above 10 MiB. Web, proxy, scheduler, worker, PostgreSQL, disk, certificate, backup, and migration evidence do not indicate the cause. Re-running unchanged ingestion would predictably reproduce the failure and was not attempted.

- **Service state:** web/scheduler/monitor/database/backup/proxy healthy; one-source collection freshness degraded; full-success and downstream publication freshness stale.
- **Action:** diagnosis only; recovery gate suppressed action because cooldown was active. No stack mutation.
- **Rollback:** not applicable; no deployment or repair was made.

## Prevention / follow-up

1. Under explicit maintenance/deployment authorization, review ThreatFox pagination/filtering or the bounded 50 MiB configuration, including decompression and memory impact; retain oversized-response regression coverage.
2. Run focused tests, then deploy only through `./scripts/update-app.sh`; verify ThreatFox status, full-success/usable-run projections, monitor evidence, and publication freshness.
3. Export `HERMES_MONITOR_EVIDENCE_FILE` and protected Compose variables in maintenance cron while retaining the container fallback.
4. Reconcile operational SQL probes with the deployed singular schema to eliminate misleading PostgreSQL errors.
5. Perform encrypted-backup restore verification separately; no restore was attempted here.
