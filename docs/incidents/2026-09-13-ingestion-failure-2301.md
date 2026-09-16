# Production ingestion incident: recovery cooldown suppression (23:01Z)

- **Recorded:** 2026-09-13T23:01:39.745335+00:00
- **Monitor state:** `actionable_failure`
- **Monitor event:** `f8827e26-8ec2-4b19-a2d7-d99f445892c1`
- **Observed at:** `2026-09-13T23:00:47.895170+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `198db305-d7f8-4eb1-a95b-8204e9133f46`
- **Run:** `5caec866-d2eb-51b1-905f-ecc8a66da107`
- **Gate result:** suppressed; recovery cooldown active; lock verified absent

## Impact and cause

The latest ingestion attempt is failed but usable: 37 of 38 sources completed and
5,943 new documents were persisted. The latest full-success run is
`b97c27ae-bcf6-59b0-adac-07bd434c0ec6`, completed at
`2026-09-11T12:06:50.050468Z`. Public CTI remains available from the partial
projection, but complete source coverage and full-success freshness remain
degraded.

`threatfox-recent-indicators-abuse-ch` is the sole failed source. Its source run
is `failed`, item count `0`, retry count `0`, cache state `miss`, HTTP status
null, classification `oversized_response`, and detail `response exceeds
10485760 bytes`.

Cause confidence is **high**: deterministic provider/source response-size
boundary failure. There is no evidence of a web, proxy, scheduler, database,
disk, memory, file-descriptor, publication, backup, migration, or credential
outage. A separate certificate risk remains: local TLS endpoints reported
expiry at `2026-09-14T03:39:23Z`.

## Evidence and operational state

- Repository is `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three
  commits ahead of `origin/main`, with pre-existing broad working-tree changes;
  this job did not modify application/configuration source.
- Application version is `0.1.0`; running image tag is `cti-hermes:local`, image
  ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Web, monitor, scheduler, PostgreSQL, and backup containers are healthy with
  restart count 0 and no OOM termination. The worker is an intentional one-shot
  container exited 0 and has no restart loop.
- `/health/live`, `/health/ready`, and `/version` returned HTTP 200; readiness
  reported configuration and database `ok`, and version `0.1.0`.
- Scheduler heartbeat was fresh at `2026-09-13T23:01:59Z`. Monitor logs repeat
  only the stale full-success and failed-attempt signals; scheduler logs showed
  no new crash/restart evidence.
- Authenticated run-status projection confirms `latest_attempt` and
  `latest_usable` are the failed-but-usable run
  `5caec866-d2eb-51b1-905f-ecc8a66da107` (37/38 sources), while
  `latest_full_success` is completed run
  `b97c27ae-bcf6-59b0-adac-07bd434c0ec6` (38/38 sources).
- PostgreSQL accepts connections; Alembic revision is
  `0015_contradiction_lifecycle`. Database status counts are 2 completed and 23
  failed ingestion runs. Bounded reads show 31,107 source documents, 186
  reports, 201 publications, 378 detections, 201 hunts, 201 remediations, and
  11 relationships. No data mutation was performed.
- Host root filesystem is 43% used with 280G available; memory available is
  approximately 52 GiB; open-file limit is 4096 with 454 process descriptors.
- Backup service is healthy. Latest encrypted backup metadata identifies
  `hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`,
  22,110,800 bytes, mode 600, with SHA-256 recorded.
- TLS endpoints 9443 and 9444 both reported `notAfter=Sep 14 03:39:23 2026 GMT`.
  No ingress outage was observed, but renewal is urgent.
- Last service start was 2026-09-12T12:55:15Z–12:55:21Z. No service restart
  occurred during this diagnosis. No deployment/configuration mutation was made.

## Recovery gate and action

The authoritative evidence was read from `/runtime/monitor-evidence.json` inside
the monitor container. The recovery gate was evaluated with its cooldown and
lock. It recorded suppressed event `f8827e26-8ec2-4b19-a2d7-d99f445892c1` at
`2026-09-13T23:01:39.745335+00:00` because `recovery cooldown is active`.
The recovery lock was verified absent.

No retry, restart, deployment, migration, credential change, response-limit
change, volume/data deletion, backup deletion, or publication mutation was
performed. Re-running unchanged ingestion would reproduce the deterministic
provider response-size failure.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture; retain an oversized-response regression fixture and
partial-run visibility. Reconcile the checked-in 50 MiB source limit with the
active 10 MiB runtime boundary before any focused change, then deploy only after
focused tests and `./scripts/update-app.sh` verification. Renew the certificate
before `2026-09-14T03:39:23Z` using the certificate runbook. No rollback is
required because this diagnosis performed no application or data mutation.
