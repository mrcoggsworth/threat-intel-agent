# Production ingestion incident: actionable partial-run failure (01:17Z)

- **Recorded:** 2026-09-14T01:17Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `f8b915a6-0950-4459-bf7d-2169e8af91dd`
- **Observed at:** `2026-09-14T01:16:57.595019+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `91d116e9-7788-4d24-b7cc-220722ae557a`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate result:** suppressed; recovery cooldown active

## Impact and cause

The latest ingestion attempt remains failed but usable: the monitor reports one
failed source while the run remains persisted and available for the successful
sources. The latest full-success projection remains stale. Public CTI remains
available from the partial projection, but complete source coverage and
full-success freshness remain degraded.

The failure is unchanged from the preceding incident evidence: the sole failed
source is `threatfox-recent-indicators-abuse-ch`, with
`error_classification=oversized_response` and detail
`response exceeds 10485760 bytes`. Cause confidence is **high**: a deterministic
provider/source response-size boundary failure. There is no evidence in the
current checks of web, proxy, scheduler, PostgreSQL, disk, memory, file
descriptor, publication, backup, migration, or credential outage.

## Evidence and operational state

- Authoritative evidence was read from `/runtime/monitor-evidence.json` inside
  `cti-hermes-monitor-1` before the gate decision. It records both
  `full_success_freshness=stale_data` and
  `latest_ingestion_attempt=actionable_failure`, with HTTP 200 and the exact
  endpoint, correlation ID, event ID, and run ID above.
- Repository is `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three
  commits ahead of `origin/main`, with broad pre-existing working-tree changes.
  This diagnosis made no application or configuration source change.
- CTI web, monitor, scheduler, backup, and PostgreSQL containers are running;
  web, monitor, scheduler, backup, and PostgreSQL report healthy; restart count
  is 0 and no OOM termination is present. The worker is an intentional one-shot
  container exited 0 and is not a persistent worker outage.
- Monitor logs repeatedly report only `last successful run stale` and
  `latest ingestion attempt failed`. Web health requests return HTTP 200.
  PostgreSQL accepts connections (`pg_isready`). Current migration revision is
  `0015_contradiction_lifecycle`.
- Host root filesystem is 43% used with approximately 280 GiB available;
  approximately 52 GiB memory is available; the shell open-file limit is 4096.
  No resource exhaustion is indicated.
- Latest encrypted backup metadata is present at mode 600 and was updated
  2026-09-13T12:55:20Z. No backup mutation occurred.
- Local TLS endpoints currently present a Caddy certificate valid through
  2026-09-14T11:39:23Z. Renewal remains urgent but is not the ingestion cause.
- Compose config validation from this operator shell remains blocked because
  protected production variables `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not
  exported. This is an operator-shell limitation, not evidence of a production
  outage.

## Recovery gate and action

The recovery gate was evaluated against the authoritative monitor evidence with
the configured 30-minute cooldown and lock. It recorded a suppressed decision:

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
against an offline fixture before a focused source change. Retain the
oversized-response regression fixture and partial-run visibility. Reconcile the
checked-in 50 MiB source limit with the active 10 MiB runtime boundary before
any deployment. Renew the certificate before its current expiry using the
certificate runbook. No rollback is required because this diagnosis performed
no application or data mutation.
