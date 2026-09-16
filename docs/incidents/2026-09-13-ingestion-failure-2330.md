# Production ingestion incident: recovery cooldown suppression (23:30Z)

- **Recorded:** 2026-09-13T23:32:57Z
- **Monitor state:** `actionable_failure`
- **Monitor event:** `e0d0f703-65d1-4e62-9a93-46db0d86fd54`
- **Observed at:** `2026-09-13T23:30:50.049012+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP 200
- **Correlation:** `3146f731-d505-4062-b207-b7a5d28f1bb3`
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
null, classification `oversized_response`, and detail `response exceeds 10485760 bytes`.

Cause confidence is **high**: deterministic provider/source response-size boundary
failure. There is no evidence of a web, proxy, scheduler, database, disk, memory,
file-descriptor, publication, backup, migration, or credential outage. A separate
certificate risk remains: local TLS endpoints report expiry at
`2026-09-14T03:39:23Z`.

## Evidence and operational state

- Repository is `main` at `c925cd5bbb1b2c872841205b90ea05ea4636da76`, three commits ahead of `origin/main`, with pre-existing broad working-tree changes. This job made no application/configuration source change.
- Application version is `0.1.0`; running image is `cti-hermes:local`, image ID `sha256:b8f7768c15292957867be104569f8e59f3e021863d5e426e219e58472ec8ed9d`.
- Web, monitor, scheduler, PostgreSQL, backup, and proxy containers are running and healthy or running as applicable; restart count is 0 and no OOM termination is present. Worker is not running as a persistent service, consistent with its intentional one-shot role.
- `/health/live`, `/health/ready`, and `/version` returned HTTP 200; readiness reported configuration and database `ok`; version reported `0.1.0`. Caddy remained running with restart count 0.
- Scheduler heartbeat was fresh, approximately 12 seconds old at collection. Monitor logs continuously recorded only the stale full-success and failed-attempt signals; no crash or restart loop was observed.
- PostgreSQL accepts connections; Alembic revision is `0015_contradiction_lifecycle`. Database status counts are 2 completed and 23 failed ingestion runs. Bounded reads show 31,107 source documents, 186 reports, 201 report versions, 201 publications, 378 detections, 201 hunts, 201 remediations, and 11 relationships.
- Host root filesystem is 43% used with 280G available; memory available is approximately 52 GiB; host open-file limit is 4096. No resource exhaustion evidence was found.
- Latest encrypted backup metadata identifies `hermes-20260913T125518Z.dump.enc`, completed `2026-09-13T12:55:20Z`, 22,110,800 bytes, mode 600, with SHA-256 metadata recorded.
- TLS endpoints 9443 and 9444 both reported `notAfter=Sep 14 03:39:23 2026 GMT`. No ingress outage was observed, but renewal is urgent.
- Last application service start was `2026-09-12T12:55:15Z`–`12:55:21Z`. Compose config validation from this operator shell was blocked because protected production variables `HERMES_SECRET_DIR` and `HERMES_IMAGE` are not exported; this is an operator-shell limitation, not evidence of a production outage. Migration CLI `db current` is unsupported by the installed CLI; direct database revision evidence was used instead.

## Recovery gate and action

The authoritative monitor evidence was read from `/runtime/monitor-evidence.json`
inside `cti-hermes-monitor-1` before any recovery decision. The recovery gate was
then evaluated with its 30-minute cooldown and lock. It recorded the suppressed
event `e0d0f703-65d1-4e62-9a93-46db0d86fd54` with reason `recovery cooldown is active`.
The recovery lock was verified absent.

No retry, restart, deployment, migration, credential change, response-limit change,
volume/data deletion, backup deletion, or publication mutation was performed.
Re-running unchanged ingestion would reproduce the deterministic provider
response-size failure and risk another duplicate failed attempt.

## Prevention and rollback

Validate ThreatFox provider-side filtering, pagination, or an alternate endpoint
against an offline fixture; retain an oversized-response regression fixture and
partial-run visibility. Reconcile the checked-in 50 MiB source limit with the
active 10 MiB runtime boundary before any focused change, then deploy only after
focused tests and `./scripts/update-app.sh` verification. Renew the certificate
before `2026-09-14T03:39:23Z` using the certificate runbook. No rollback is
required because this diagnosis performed no application or data mutation.
