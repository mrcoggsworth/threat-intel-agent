# Production ingestion incident: ThreatFox oversized response (21:17Z)

- **Recorded:** 2026-09-14T21:17:39Z
- **Repository/release:** `main`, HEAD `c925cd5bbb1b2c872841205b90ea05ea4636da76`, image `cti-hermes:local`, application `0.1.0`
- **Monitor state:** `actionable_failure`
- **Monitor event:** `190af31c-a475-4b58-b6dd-e4827f353d13`
- **Observed at:** `2026-09-14T21:18:24.529415+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200` in authoritative monitor evidence
- **Correlation:** `9acfd1e8-4ae2-47f8-8d75-2e8ba2d2c3f1`
- **Latest failed run:** `20c8d81a-48e4-5215-8292-63a72ddac05d`

## Impact and diagnosis

The latest usable collection is incomplete: 38 sources were attempted, 37
succeeded, one failed, and 12,831 new documents were persisted. The latest
full-success run remains stale (`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, as
reported by the monitor). Public CTI remains available from the partial run,
but full source coverage and full-success freshness are degraded.

The failed source is `threatfox-recent-indicators-abuse-ch`. Its persisted
source-run record is `status=failed`, `error_classification=oversized_response`,
and `error_detail=response exceeds 10485760 bytes`. This repeats the established
failure pattern. Cause confidence is **high**: a provider/source response-size
boundary mismatch, not a web, proxy, scheduler, database, resource,
certificate, backup, migration, publication, or credential outage. The
checked-in source configuration advertises a 50 MiB bound while the active
runtime rejects at 10 MiB; no deployment was authorized or performed.

## Evidence and operational state

- Latest run `20c8d81a-48e4-5215-8292-63a72ddac05d`: started
  `2026-09-14T18:32:12.667740+00`, completed `2026-09-14T18:33:07.628491+00`,
  status `failed`, 38 total / 37 successful / 1 failed, application `0.1.0`,
  configuration hash
  `d7d8a6330ab0fb7449170d91b1556558f35edca4b4de45d102907abe28f2e864`.
- Latest full-success is the monitor-reported run
  `b97c27ae-bcf6-59b0-adac-07bd434c0ec6`; latest usable run is the partial
  `20c8d81a-48e4-5215-8292-63a72ddac05d`.
- Database contains 186 reports and 201 publications; both latest timestamps
  are `2026-09-11T22:24:37.163555+00`.
- Web `/health/live` returned `{"status":"ok"}` and `/health/ready` returned
  HTTP 200 with `configuration=ok` and `database=ok`. A direct recheck of the
  monitor-recorded run-status path returned HTTP 404 despite monitor evidence
  recording HTTP 200; this route/evidence discrepancy is follow-up work, not
  evidence of database or web process failure.
- Web, scheduler, monitor, backup, and PostgreSQL containers are running and
  healthy with restart count 0; PostgreSQL is accepting connections and
  migration revision is `0015_contradiction_lifecycle`. The worker is an
  intentional one-shot container exited 0, with restart count 0 and no OOM kill.
- Scheduler heartbeat was fresh at `2026-09-14 21:17:08Z`; monitor evidence was
  refreshed at `21:15:24Z`. No service restart or OOM event was observed.
- Root filesystem is 43% used with approximately 279 GiB available; host
  memory has approximately 54 GiB available; open-file limit is 4096. No
  resource exhaustion is indicated.
- Encrypted backup `hermes-20260914T125520Z.dump.enc` and `latest.metadata`
  exist, with latest metadata at `2026-09-14 12:55:23Z`. Certificate file
  `/data/caddy/certificates/local/hermes.cti.scogin.dev/hermes.cti.scogin.dev.crt`
  exists and was updated at `2026-09-14 15:39:23Z`; expiry was not parsed
  because the Caddy container has no `openssl`.
- The cron shell did not export `HERMES_MONITOR_EVIDENCE_FILE`; authoritative
  evidence was read from `/runtime/monitor-evidence.json` in
  `cti-hermes-monitor-1`, the configured Compose mount. Compose validation in
  this shell is also blocked by protected, unexported `HERMES_SECRET_DIR` and
  `HERMES_IMAGE`; this is an operator-shell limitation.

## Recovery gate and action

The recovery gate was evaluated against the authoritative evidence with its
30-minute cooldown and lock. It recorded suppressed event
`ad8ff8c7-95e5-4c3f-82aa-e4caa96c919a` at `2026-09-14T21:16:36.821995+00Z`,
correlation `a215c58b-736f-45c7-92ac-9dd02f45738c`, because the recovery
cooldown was active. The recovery lock was verified absent.

No ingestion retry, service restart, deployment, migration, credential change,
response-limit change, volume/data deletion, backup deletion, or publication
mutation was performed. Failed ThreatFox evidence and successful-source results
remain persisted and usable. No rollback is required.

## Prevention and follow-up

Validate ThreatFox provider-side filtering/pagination or an alternate endpoint
against an offline fixture before deploying the checked-in 50 MiB limit. Retain
a regression fixture for the 10 MiB boundary, reconcile active runtime
configuration with `config/sources.json`, and investigate why the monitor's
run-status HTTP 200 does not reproduce in a direct container request. Recheck
certificate expiry using proxy renewal tooling and reconcile the missing
operator `HERMES_MONITOR_EVIDENCE_FILE` export. Any deployment or retry requires
explicit authorization and must use `./scripts/update-app.sh`.
