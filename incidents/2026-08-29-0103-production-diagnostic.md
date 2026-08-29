# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 01:03 UTC (2026-08-28 20:03 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The public web/API boundary, TLS ingress, PostgreSQL, scheduler heartbeat, and
backup health are available. Ingestion is degraded: the latest persisted run is
failed with 12/14 sources successful, 2 failed, and 1,840 new documents. All
five persisted runs are failed; there is no fully completed run. Partial
successful-source output and failure provenance are persisted. Public evidence
and publication records remain present; no integrity violation was found.

The monitor container is running and its Docker healthcheck is currently
passing, but its configured last-success path is not a deployed route when
probed directly (`/api/v1/ops/last-success` returns 404). Earlier monitor logs
reported failures for public liveness/private readiness/last-success. This is
an operations-monitoring contract gap and weakens freshness alerting; it is not
evidence of web or database unavailability.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17` (`origin/main` and `main`).
  Existing working-tree additions are prior incident records only and do not
overlap application/deployment source.
- Application version: `hermes-cti 0.1.0`.
- Active application image tag: mutable `cti-hermes:local`, resolved image ID
  and local digest `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL image ID is `sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb`;
  backup image ID is `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Containers were created 2026-08-28 16:56:03--04Z; web/scheduler/monitor/backup
  use the application image above. Compose labels identify the protected
  runtime env at `/opt/cti-hermes/env/production.env`.
- Checkout Compose validation is blocked because `deploy/.env` is absent and
  required `HERMES_IMAGE`/`HERMES_SECRET_DIR` values are not available in the
  checkout. The active stack itself is running from the pinned Compose file.
- Latest code commit is the 2026-08-28 11:54:51 CDT merge of PR #41. Compose
  mtime is 2026-08-26 20:14:30 CDT; source registry mtime is 2026-08-16 15:36:31
  CDT; scheduler script mtime is 2026-08-24 09:02:52 CDT.

## Runtime, health, proxy, and host evidence

- Web, scheduler, PostgreSQL, backup, and monitor are running/healthy. The
  reserved worker exited 0 by design (`restart: no`) and is not an active queue
  worker. Runtime-init exited 0 after initialization.
- Restart counts: web 0, PostgreSQL 0, scheduler 0, backup 0, monitor 3,
  worker 0. All inspected containers report `OOMKilled=false`. Docker events in
  the 48-hour review showed healthcheck/exec activity, not lifecycle crash or
  kill events.
- Scheduler heartbeat is fresh (`2026-08-29T01:02:48Z`); scheduler logs show
  two source-collection failures and no crash loop. Worker log states it is
  reserved for a later analysis phase.
- External `/health/ready` and `/version` return HTTP 200. External
  `/health/live` returns Nginx 404, consistent with the current ingress
  allowlist; loopback application `/health/live`, `/health/ready`, and
  `/version` return 200. PostgreSQL readiness is accepting connections.
- Nginx is active since 2026-08-26 18:20:33 CDT with `NRestarts=0`. Unprivileged
  `nginx -t` cannot read `/etc/nginx/ssl/tailscale/hermes.key` (permission
  denied); do not weaken key permissions. Live TLS inspection succeeds:
  CN `matrix-1.taild27e3c.ts.net`, Let's Encrypt `YE1`, valid through
  2026-11-16 14:30:36Z, SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Host capacity is normal: root filesystem 504G total/175G used/308G free
  (37%), 62GiB RAM with about 58GiB available, swap unused, kernel file table
  2,592 allocated, process soft limit 4,096. Container memory usage is below
  150MiB for the largest inspected service.

## Database, migrations, backup, and integrity

- PostgreSQL 16.14 is accepting connections; database size is 35 MB.
  Production `alembic_version` is `0013_op_retention`, matching the repository
  head `0013_op_retention`. No migration was run and no pending/failed
  migration is evidenced.
- Latest run ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7` started
  `2026-08-28T16:56:16.219818Z`, completed `2026-08-28T16:56:18.054359Z`, and is
  `failed`: 14 total / 12 successful / 2 failed / 1,840 new documents.
  Google TAG failed `http_error` (`HTTP 404`); MSRC failed `malformed_xml`
  (`XML payload could not be parsed`). Historical counts are 0 completed and 5
  failed.
- Current row counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Unvalidated FK
  count and orphan checks for entity evidence, relationship evidence, and
  current report versions are all zero.
- Latest encrypted backup is `hermes-20260828T165615Z.dump.enc`, 3,507,536
  bytes, mode 600; its SHA-256 is
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  Metadata and `latest.metadata` are mode 600, and the backup container
  healthcheck passes. No restore was attempted.

## Cause assessment

- **High confidence, causal:** two configured public source contracts are
  invalid for the current upstream responses. Direct TLS-verified probes
  reproduce Google TAG HTTP 404 and MSRC HTTP 200 redirect to HTML; the
  supported Microsoft Threat Intelligence URL returns RSS/XML. These explain
  the repeated two-source partial failures. The authoritative
  `config/sources.json` has not been changed.
- **High confidence, contributing:** no fully successful ingestion run exists,
  while operational monitoring expects a `/api/v1/ops/last-success` route that
  is not deployed. Freshness/last-success alerting is therefore not reliable.
- **Low/no evidence:** web process, proxy TLS validity, scheduler process and
  heartbeat, PostgreSQL availability, migrations, disk/memory/FD pressure,
  backup creation, publication persistence, and container crash state do not
  explain the ingestion failure.
- **Medium operational risk:** mutable local image tag and missing checkout env
  weaken release defensibility; unprivileged Nginx config testing is incomplete.

## Actions and approvals

- Completed read-only preflight: repository identity/status, container/image
  state, restart counts, healthchecks, Docker events/logs, local and external
  health probes, TLS inspection, host capacity, database connectivity and
  revision, integrity/orphan checks, source probes, and backup metadata/hash.
- **No operational mutation:** no restart, migration, rollback, restore,
  source disablement, config edit, Nginx reload, credential operation, Docker
  prune, volume deletion, or data/publication mutation.
- Smallest reversible action is **no restart**: restart cannot repair upstream
  URL/format failures and could obscure evidence. Rollback is not indicated;
  no approved immutable compatible target or approval reference is documented.
- Service/data-integrity state: available but ingestion-degraded; partial
  evidence and provenance intact; no corruption evidence.
- Local incident record created at this path. No external issue/PR was created;
  no issue destination or approval reference was supplied.
- Approvals required: approve replacement source URL/adapter changes and any
  image/code release; separately approve restart, migration, restore, proxy,
  credential, or deployment operations. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Correct and validate Google TAG/MSRC source URLs or adapters under review;
   add mocked 404, redirect-to-HTML, malformed XML, and partial-run fixtures.
2. Reconcile `monitor.py` with the deployed API route contract and make
   freshness require `status='completed'`, distinguishing partial ingestion
   from full success.
3. Require immutable image digests plus release records for commit, Compose and
   source hashes, migration revision, approval, and rollback target.
4. Provide the protected production env to maintenance preflight and validate
   Compose in CI without exposing secret contents.
5. Schedule an approved isolated encrypted-backup restore rehearsal.
6. Run privileged Nginx config tests in maintenance automation while preserving
   private-key permissions.
