# CTI-Hermes actionable ingestion failure diagnostic

- **Observed at:** 2026-09-15T05:46:00.793138Z
- **Monitor state:** `actionable_failure`
- **Event ID:** `a6ae7a67-ce44-4ebc-bfe9-7659e95b7861`
- **Correlation ID:** `de62cfb4-93a3-4423-a557-a71b5c7873db`
- **Latest attempt run ID:** `1e4c3ca2-f4d1-504d-93d3-b0e03f82db4f`
- **Monitor endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Full-success run ID:** `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`
- **Repository/release:** `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`; remote `git@github.com:mrcoggsworth/threat-intel-agent.git`
- **Working tree:** broad pre-existing modifications, deletions, and untracked files were present; this incident record is the only change made by this diagnosis.
- **Application/image:** version `0.1.0`; image `cti-hermes:local`; image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`; image created 2026-09-12T12:55:03Z.

## Impact

The latest scheduled collection failed after processing 37 of 38 sources. Successful source results remain persisted, but the ThreatFox/Abuse.ch source is not fresh. The latest run completed at 2026-09-15T02:00:54.439155Z with 38 total, 37 successful, 1 failed, and error summary `1 source(s) failed`. There are 28 ingestion runs total: 2 `completed` and 26 `failed`. Source documents were retrieved through 2026-09-15T02:00:54Z; analyst/publication output remains older (186 reports, 201 report versions/publications, latest 2026-09-11T22:24:37Z).

## Evidence and diagnosis

- Failed source: `threatfox-recent-indicators-abuse-ch`; HTTP status unavailable; classification `oversized_response`; detail `response exceeds 10485760 bytes`.
- Web version, liveness, and readiness checks returned HTTP 200. Readiness reported configuration and database `ok`.
- Scheduler, monitor, web, PostgreSQL, and backup containers are running healthy with restart count 0 and OOM false. The worker is intentionally exited with code 0. No non-health-check restart/start/die events were observed in the 24-hour window.
- PostgreSQL accepts connections. Alembic revision is `0015_contradiction_lifecycle`; no migration failure or database connectivity blockage was observed. The failed run and failed source-run record are present, preserving the failure evidence.
- Host capacity is not limiting: root filesystem is 43% used with 279G available, 52GiB memory available, and open-file limit 4096.
- Latest backup metadata identifies `/backups/hermes-20260914T125520Z.dump.enc`, completed 2026-09-14T12:55:23Z, 22,608,400 bytes, with recorded SHA-256 `b3420347e1f7352ef55f76d03d43c65c081e625d4ad34f958da00db65dc7bd09`; backup container is healthy. Restore was not attempted.
- Caddy is running with zero restarts and logged successful local certificate renewals. The managed `hermes.cti.scogin.dev` certificate is valid from 2026-09-14T23:39:23Z through 2026-09-15T11:39:23Z, issued by the Caddy local authority. External TLS verification fails because the local issuer is not trusted; this is a separate ingress/trust issue, not the ingestion cause.
- The working tree contains an uncommitted `config/sources.json` change adding `max_response_bytes: 52428800` for ThreatFox, but the running scheduler's `/app/config/sources.json` does not contain that setting. It is therefore not deployed, and the active 10 MiB transport limit still rejects the provider response.

**Cause confidence: high.** This is a recurring source/provider response-size handling failure at the ThreatFox/Abuse.ch boundary, not a web, proxy, worker, scheduler liveness, PostgreSQL, disk, memory, migration, backup, or certificate-expiry failure.

## Recovery gate and actions

The authoritative monitor evidence was read from `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1` before further diagnosis. The recovery gate was evaluated using shared `/runtime` state and returned `allowed: false` with reason `recovery cooldown is active`. The latest suppression was recorded at 2026-09-15T05:46:27.774174Z for event `a6ae7a67-ce44-4ebc-bfe9-7659e95b7861`; the prior attempt timestamp was 2026-09-15T05:31:38.934542Z. The lock was absent after the suppressed evaluation. No restart, retry, deployment, migration, credential change, or destructive recovery was performed.

## Service, integrity, rollback, and prevention

- **Service state:** internal web service healthy and serving; collection freshness degraded for one source; analyst/publication freshness stale.
- **Data integrity:** no destructive operation; 37 successful source results and the failed source record are preserved; no volume, backup, or migration changes.
- **Rollback:** not applicable; no application/config deployment was made. The uncommitted configuration change remains pre-existing and untouched.
- **Prevention:** review and deploy a bounded/paginated ThreatFox request or a deliberately tested larger limit through the normal `./scripts/update-app.sh` workflow; retain the `oversized_response` classification and add a mocked oversized-response regression test. Do not retry until the recovery gate permits it. Separately remediate trust distribution for the local Caddy CA and investigate the scheduler/API projection so full-success freshness can be restored without hiding partial failures.
