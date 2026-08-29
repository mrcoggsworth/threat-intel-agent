# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 03:17 UTC (2026-08-28 22:17 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API boundary, TLS ingress, PostgreSQL, scheduler heartbeat, and backup
health are available. Ingestion is degraded: the latest persisted run is
failed with 12/14 sources successful, 2 failed, and 110 new documents. All six
persisted runs are failed; there is no fully completed run. Successful-source
output and failure provenance remain persisted. Existing evidence, reports, and
publications remain present; no integrity violation was found.

The monitor container is healthy but reports a monitoring-contract failure. Its
configured `/api/v1/ops/last-success`, heartbeat, and public-liveness checks do
not match the externally allowed routes. Direct external probes return 404 for
`/health/live`, `/api/v1/ops/last-success`, and `/api/v1/ops/heartbeat`; the
loopback web route for `/health/live` is 200. This weakens freshness alerting
but is not evidence of web or database unavailability.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17` (latest commit also at
  `origin/main`/`main`).
- Existing working-tree additions are prior incident records only; no source,
  migration, Compose, or source-registry changes overlap this diagnosis.
- Application version: `hermes-cti 0.1.0`.
- Active application image: mutable `cti-hermes:local`, image ID and local
  digest `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL image ID is `sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb`;
  backup image ID is `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Web/scheduler/monitor/backup were created and started at approximately
  `2026-08-28T16:56:14Z`–`16:56:16Z`; PostgreSQL has been running since
  `2026-08-26T23:20:36Z`.
- Checkout Compose validation with the protected production environment was
  not possible because the checkout lacks `deploy/.env`; no protected env or
  secret contents were read. The active stack is identified by Compose labels.
- Latest code commit: `2026-08-28 16:54:51Z`; application image created
  `2026-08-28T16:55:53Z`; Compose mtime `2026-08-27T01:14:30Z`; source registry
  mtime `2026-08-16T20:36:31Z`; watchdog mtime `2026-08-26T18:11:50Z`.

## Runtime, health, proxy, and host evidence

- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  The reserved worker exited 0 by design and is not an active queue worker;
  runtime-init exited 0 after initialization.
- Restart counts: web 0, PostgreSQL 0, scheduler 0, backup 0, worker 0,
  monitor 3. All inspected containers report `OOMKilled=false`.
- Scheduler heartbeat healthcheck is passing. Scheduler logs show repeated
  source-collection failures without a crash loop. Monitor logs report its
  route-contract failures.
- Verified external `/health/ready` and `/version` return HTTP 200. Loopback
  `/health/live` and `/health/ready` return HTTP 200. Loopback
  `/api/v1/ops/last-success`, `/api/v1/ops/scheduler-heartbeat`, and
  `/api/v1/ops/version` return 404, confirming the monitor route mismatch.
- Docker events for the preceding 48 hours show healthcheck/exec activity but
  no container lifecycle crash, kill, or restart event.
- Host capacity is normal: root filesystem 504G total/175G used/308G free
  (37%); 62GiB RAM with about 58GiB available; swap unused. Kernel file table
  reports `2560 0 9223372036854775807`; process soft limit is 4096. Docker
  reports no pressure condition; reclaimable images/build cache were not
  pruned.
- Nginx is active with `NRestarts=0`, running since `2026-08-26 23:20:33Z`.
  TLS inspection succeeds: CN `matrix-1.taild27e3c.ts.net`, issuer Let's
  Encrypt `YE1`, valid `2026-08-18T14:30:37Z` through
  `2026-11-16T14:30:36Z`. No certificate expiry or proxy process failure was
  found. Unprivileged config testing remains incomplete because the private
  key is protected; key permissions were not weakened.

## Database, migrations, backup, and integrity

- PostgreSQL 16.14 accepts connections; database is `hermes`; database size
  remains approximately 35 MB.
- Production Alembic revision is `0013_op_retention`, matching repository head
  `0013_op_retention` (`uv run alembic heads`). No pending or failed migration
  is evidenced; no migration was run.
- Latest run `4f8db05e-c29a-5c80-bfe0-464edad4a18e` started
  `2026-08-29T02:00:00.091132Z`, completed
  `2026-08-29T02:00:01.945429Z`, and is `failed`: 14 total / 12 successful /
  2 failed / 110 new documents. Historical status is 6 failed / 0 completed.
- Failed source results on the latest run are Google Threat Analysis Group:
  `http_error` with HTTP 404, and Microsoft Security Response Center:
  `malformed_xml` (`XML payload could not be parsed`).
- Current counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. No FK/orphan
  integrity issue was evidenced in the prior verified checks; no data mutation
  was performed during this capture.
- Latest encrypted backup metadata is for
  `hermes-20260828T165615Z.dump.enc`, completed
  `2026-08-28T16:56:16Z`, 3,507,536 bytes, mode 600, SHA-256
  `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`.
  `latest.metadata` is present, mode 600, and the backup container healthcheck
  passes. No restore was attempted.

## Cause assessment

- **High confidence, causal:** two authoritative configured RSS contracts are
  invalid for current upstream responses. The configured Google URL
  `https://blog.google/threat-analysis-group/rss/` reproduces HTTP 404. The
  configured MSRC URL `https://msrc.microsoft.com/blog/feed` redirects to
  `https://www.microsoft.com/en-us/msrc/blog` and returns HTML rather than RSS;
  the application records this as malformed XML. These explain the repeated
  two-source partial failures. `config/sources.json` was not changed.
- **High confidence, contributing:** no fully successful ingestion run exists,
  and the monitor's freshness/last-success route contract is not deployed.
- **Low/no evidence:** web process, Nginx/TLS, scheduler process and heartbeat,
  PostgreSQL availability, migration state, disk/memory/FD pressure, backup
  creation, publication persistence, and container crash state do not explain
  the ingestion failure.
- **Medium operational risk:** the mutable local image tag and unavailable
  protected production env weaken release reproducibility and preflight
  defensibility.

## Actions and approvals

- Completed read-only preflight: repository identity/status, release/image
  metadata, container state/restarts/health, logs, Docker events, external and
  loopback probes, TLS inspection, host resources, database connectivity and
  revision, source probes, and backup metadata.
- **No operational mutation:** no restart, migration, rollback, restore, source
  disablement, config edit, Nginx reload, credential operation, Docker prune,
  volume deletion, or data/publication mutation.
- Smallest reversible action is **no restart**: a restart cannot repair the
  upstream URL/format contracts and could obscure evidence. Rollback is not
  indicated; no approved immutable compatible target or approval reference is
  documented.
- Service/data-integrity state: available but ingestion-degraded; partial
  evidence and provenance intact; no corruption evidence.
- This local incident record is the maintenance handoff. No external issue/PR
  destination was supplied.
- Approvals required: approve replacement source URLs/adapters and any code or
  image release; separately approve restart, migration, restore, proxy,
  credential, or deployment operations. Destructive recovery remains
  unauthorized and unnecessary.

## Prevention and follow-up

1. Correct and validate Google TAG/MSRC URLs or adapters under review; add
   mocked 404, redirect-to-HTML, malformed XML, and partial-run fixtures.
2. Reconcile `monitor.py` with deployed route/ingress policy and make freshness
   require `status='completed'`, distinguishing partial ingestion from success.
3. Require immutable image digests plus release records for commit, Compose and
   source hashes, migration revision, approval, and rollback target.
4. Provide a protected production env to maintenance preflight and validate
   Compose in CI without exposing secret contents.
5. Schedule an approved isolated encrypted-backup restore rehearsal.
6. Run privileged Nginx config tests in maintenance automation while preserving
   private-key permissions.
