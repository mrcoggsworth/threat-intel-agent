# Production ingestion incident: recovery cooldown suppression (01:45Z)

- **Recorded:** 2026-09-14T01:45Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `99983f64-ec71-41c6-807f-da6b3885806b`
- **Observed at:** `2026-09-14T01:45:59.659083+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `77b98568-6bb2-4d88-9076-65685bcdd0ea`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate event:** `99983f64-ec71-41c6-807f-da6b3885806b`; suppressed at 2026-09-14T01:46:11Z because recovery cooldown is active
- **Post-check evidence refresh:** event `e9515dcf-360d-4878-b168-01e374ddbe21`, observed `2026-09-14T01:47:59.805866+00:00`, correlation `6d27beca-01f1-4a1d-859a-0080175ac351`, same actionable state and run; recovery lock absent

## Impact and cause

The latest ingestion run is persisted as failed but usable: 37 of 38 sources
completed and produced 12,241 new documents. Public CTI remains available from
the partial projection, but complete source coverage and full-success freshness
are degraded. The last full-success run is `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`,
completed at `2026-09-11T12:06:50.050468+00:00`.

The sole failed source is `threatfox-recent-indicators-abuse-ch`, with
`error_classification=oversized_response` and detail `response exceeds 10485760
bytes`. Cause confidence is **high**: deterministic provider/source response-size
boundary failure. There is no evidence of a web, proxy, scheduler, PostgreSQL,
disk, memory, file-descriptor, publication, backup, migration, certificate, or
credential outage.

## Evidence and operational state

- Repository is `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`; broad pre-existing working-tree changes remain and were not modified.
- Running application image is `cti-hermes:local`, image ID and repo digest `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`, created `2026-09-12T07:54:53.392614948-05:00`; application `/version` reports `0.1.0`.
- Web, monitor, scheduler, backup, and PostgreSQL containers are running and healthy with restart count 0 and no OOM termination. The worker is an intentional one-shot container exited 0; it is not a persistent worker outage.
- Web liveness and readiness returned HTTP 200; readiness reported configuration and database `ok`. PostgreSQL `pg_isready` reported accepting connections.
- Monitor logs repeatedly report only `last successful run stale` and `latest ingestion attempt failed`; scheduler logs were empty in the inspected two-hour window. Docker events showed health-check/exec activity and no service restart or crash event.
- Database migration revision is `0015_contradiction_lifecycle`; the `alembic_version` table contains one revision and no pending/failed migration evidence was found. The application DB status command reports the expected last-successful run and no stale run IDs; its connection-close warning is a CLI event-loop cleanup cosmetic issue, not a database failure.
- Host root filesystem is 43% used with approximately 280 GiB available; approximately 52 GiB memory is available; open-file limit is 4096. No resource exhaustion is indicated.
- Latest encrypted backup metadata is present at mode 600, completed `2026-09-13T12:55:20Z`, artifact size 22,110,800 bytes, with recorded SHA-256; no backup mutation occurred.
- TLS certificate presented by `hermes.cti.scogin.dev` is Caddy-issued and valid through `2026-09-14T11:39:23Z`; renewal is urgent but unrelated to ingestion.
- Latest repository deployment/config evidence is the running image created 2026-09-12 and the checked-out `c925cd5`; no deployment or configuration mutation was performed by this job. Compose validation from this shell remains blocked by unexported protected production variables `HERMES_SECRET_DIR` and `HERMES_IMAGE`.

## Recovery gate and action

The authoritative monitor evidence was read from `/runtime/monitor-evidence.json`
inside `cti-hermes-monitor-1` before gate evaluation. The recovery gate was then
evaluated with its configured 30-minute cooldown and lock. It returned:

```text
allowed=false
reason=recovery cooldown is active
lock: not acquired
```

No retry, restart, deployment, migration, credential change, response-limit
change, volume/data deletion, backup deletion, or publication mutation was
performed. Re-running unchanged ingestion would reproduce the deterministic
provider response-size failure and was not authorized.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture before a focused source change. Reconcile the
checked-in 50 MiB source limit with the active 10 MiB runtime boundary before
any deployment. Retain the oversized-response regression fixture and partial-run
visibility. Renew the certificate before expiry using the certificate runbook.
No rollback is required because this diagnosis performed no application or data
mutation; persistent data integrity is preserved.
