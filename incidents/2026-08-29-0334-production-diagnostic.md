# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 03:34 UTC (2026-08-28 22:34 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API service and database are available, but ingestion is degraded. The
latest persisted run (`4f8db05e-c29a-5c80-bfe0-464edad4a18e`) ran at
2026-08-29 02:00:00Z–02:00:01Z and is `failed`: 14 sources, 12 successful, 2
failed, and 110 new documents. PostgreSQL confirms six persisted runs, all
`failed`, and no run with `status='completed'`. Successful-source output,
partial-run provenance, existing reports, indicators, and publications remain
present. No referential-integrity/orphan evidence was found.

External health policy exposes `/health/ready` and `/version` (HTTP 200), while
`/health/live` and private `/api/v1/ops/*` paths return proxy HTTP 404. Internal
container probes for liveness/readiness/version return 200. This is a
monitoring/ingress-contract concern, not evidence of application outage.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`; latest commit is the merge
  of PR #41. Working-tree additions are incident records only; no overlapping
  source, migration, Compose, or registry edits were found.
- Application version: `hermes-cti 0.1.0`.
- Running application image: mutable tag `cti-hermes:local`, image ID/digest
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL image ID is `sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb`;
  backup image ID is `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Web/scheduler/backup/monitor were created 2026-08-28 16:56Z; PostgreSQL
  started 2026-08-26 23:20Z. The application image was created 2026-08-28
  16:55:53Z. Latest code commit was 2026-08-28 16:54:51Z.
- Repository Compose validation is blocked without the protected
  `HERMES_IMAGE` and `HERMES_SECRET_DIR` environment values. No secret contents
  were read. The active stack was inspected by container identity and labels.
- Config/source hashes at capture: Compose
  `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`, settings
  `4a849700741275acf17415b940a4d04b558896dd6737ea582a40c57f3340af44`, source
  registry `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.

## Runtime, health, proxy, and host evidence

- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  The worker exited 0 by design (`restart: no`) and is not an active queue
  worker; Docker reports it unhealthy because its healthcheck is not suitable
  for an exited one-shot container. Runtime-init also exited 0 after setup.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0,
  monitor 3. Inspected containers report `OOMKilled=false`.
- Scheduler heartbeat is fresh and its healthcheck passes. Scheduler logs show
  repeated source-collection failures without a crash loop. Monitor logs show
  its initial route-contract failures. Internal `/api/v1/ops/last-success`,
  `/api/v1/ops/scheduler-heartbeat`, and `/api/v1/ops/version` are now 200;
  external access remains intentionally/policy-blocked with 404.
- Nginx is active with `NRestarts=0` since 2026-08-26 18:20:33 CDT. TLS
  handshake succeeds. Certificate CN is `matrix-1.taild27e3c.ts.net`, issuer
  Let's Encrypt `YE1`, validity 2026-08-18 14:30:37Z–2026-11-16 14:30:36Z,
  SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
  Privileged Nginx config testing was not attempted; key permissions were not
  weakened.
- Host capacity is normal: root filesystem 504G total/175G used/308G free
  (37%), 62GiB RAM with about 58GiB available, swap unused. Kernel file table
  is `2528 0 9223372036854775807`; PID 1 open-file limit is 1,048,576.
  Docker events in the sampled 48-hour window show healthcheck/exec activity,
  not service lifecycle crash, kill, or restart events.

## Database, migrations, backup, and integrity

- PostgreSQL 16.14 accepts connections; database is `hermes`; readiness is
  passing. Database size was not changed by this diagnostic.
- Current Alembic revision is `0013_op_retention`, matching repository head;
  no pending or failed migration is evidenced. No migration was run.
- Latest source failures are Google Threat Analysis Group: `http_error` with
  HTTP 404, and Microsoft Security Response Center: `malformed_xml` because
  the response is HTML. Other 12 sources completed.
- Current counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence
  claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks
  for entity evidence, relationship evidence, and report versions each return
  zero.
- Latest encrypted backup is `/backups/hermes-20260828T165615Z.dump.enc`,
  completed 2026-08-28 16:56:16Z, 3,507,536 bytes, mode 600. Metadata SHA-256
  is `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`, and
  an independent `sha256sum` inside the backup container matches it. Backup
  healthcheck passes; no restore was attempted.

## Cause assessment

- **High confidence, causal:** configured source contracts are stale/invalid.
  `config/sources.json` still points Google TAG to
  `https://blog.google/threat-analysis-group/rss/`, which directly returns
  HTTP 404 with HTML. It points MSRC to
  `https://msrc.microsoft.com/blog/feed`, which returns HTTP 301 to
  `https://www.microsoft.com/en-us/msrc/blog` and then HTML HTTP 200, not RSS.
  These two failures explain the repeated 2-source partial failures.
- **High confidence, contributing:** no fully successful ingestion run exists.
  The CLI `db status` output labels the latest failed run's completion time as
  `last_successful_completed_at`; SQL correctly returns `NONE`. This weakens
  freshness alerting and is a status-semantics defect.
- **Medium confidence, operational:** the mutable `cti-hermes:local` tag and
  unavailable protected Compose environment weaken release reproducibility and
  preflight defensibility.
- **Low/no evidence as causes:** web process, Nginx/TLS, scheduler heartbeat,
  PostgreSQL connectivity, migrations, disk/memory/file descriptors, backup
  creation, publication persistence, and container crash state.

## Actions and approvals

- Completed read-only preflight: repository identity/status, release/image
  metadata, container state/restarts/health, logs, Docker events, external and
  internal probes, TLS inspection, host resources, database connectivity and
  revision, source probes, and backup metadata/hash verification.
- **No operational mutation:** no restart, migration, rollback, restore, source
  edit/disablement, Nginx reload, credential operation, Docker prune, volume
  operation, or data/publication mutation.
- Smallest reversible action is **no restart**. Restarting cannot repair the
  upstream feed contracts and could obscure evidence. Rollback is not
  indicated; no approved immutable compatible target or approval reference is
  documented.
- Local incident record created at this path. No external issue/PR destination
  was supplied.

## Prevention and approval gates

1. Review and approve replacement/adapted Google TAG and MSRC source contracts;
   add mocked 404, redirect-to-HTML, malformed-XML, and partial-run fixtures.
2. Fix success semantics so only `status='completed'` is a successful run;
   distinguish partial ingestion from full success in monitor and CLI endpoints.
3. Reconcile monitor routes with the deployed Nginx policy and make freshness
   checks use an authenticated, reachable contract.
4. Require immutable image digests and release records containing commit,
   Compose/source hashes, migration revision, approval, and rollback target.
5. Provide protected production env discovery for non-secret Compose validation.
6. Schedule an approval-gated isolated encrypted-backup restore rehearsal and
   privileged Nginx config test.

Approvals are required for source/config or code release, restart, migration,
restore, proxy reload, credential operations, deployment, or rollback.
Destructive recovery remains unauthorized and unnecessary.
