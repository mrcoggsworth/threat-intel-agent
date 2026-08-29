# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 04:48 UTC (2026-08-28 23:48 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The web/API and database are available and ready. Scheduled ingestion is degraded: the latest persisted run (`2026-08-29 02:00:00Z`) is `failed`, with 12/14 sources successful, 2 failed, and 110 new documents. All six persisted ingestion runs are `failed`; no fully successful run is recorded. Successful-source documents and partial-run provenance remain persisted. Freshness/publication risk is limited to the two failing source contracts and subsequent downstream freshness. No destructive recovery or data mutation was performed.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, also `main`/`origin/main`. Working-tree additions are incident records only; no overlapping source, migration, Compose, or application edits were found.
- Live application: `hermes-cti 0.1.0`.
- Running image: mutable tag `cti-hermes:local`, also inspectable as `cti-hermes@sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; created `2026-08-28T16:55:53Z`. Web/scheduler/backup/monitor started about `16:56Z`; PostgreSQL started `2026-08-26T23:20Z`.
- Current repository hashes: source registry `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`; Compose file `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`.
- Running Compose project uses `/opt/cti-hermes/env/production.env` and protected secrets under `/home/cptcoggsworth/.local/state/cti-hermes/secrets`; secret contents were not read. With the immutable image digest and protected secret directory supplied, `docker compose ... config --quiet` passed.

## Health, proxy, certificate, and runtime evidence

- Host ingress: public `9443/health/live` returned HTTP 200 `{"status":"ok"}` and public `/reports` returned HTTP 200. Private `9444/health/ready` and `/version` returned HTTP 200. Private ops paths without authentication returned intentional HTTP 404; internal web healthcheck traffic reaches the ops routes successfully. This is proxy route isolation, not a web outage.
- TLS verification succeeded: `CN=matrix-1.taild27e3c.ts.net`, Let's Encrypt `YE1`, valid `2026-08-18 14:30:37Z` through `2026-11-16 14:30:36Z`, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Containers: web, scheduler, PostgreSQL, backup, and monitor running/healthy; worker exited 0 by design (`restart: no`) and is unhealthy after exit. Restart counts are web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3; all inspected CTI containers report `OOMKilled=false`.
- Scheduler heartbeat is non-empty, mode 644, and fresh at capture (`04:46:19Z`). Logs show source collection failures without a scheduler crash loop. Monitor's initial failures concern route-contract checks; later internal checks return 200.
- Host capacity is normal: root filesystem 504G/175G used/308G available (37%); 62 GiB RAM with about 58 GiB available; swap unused; host open-file limit 4096. Container PID 1 has 1,024 soft / 524,288 hard open-file limit and only 6 web FDs at capture. Nginx is active, `NRestarts=0`, with no journal errors in the sampled window. Docker event sampling shows healthcheck/exec events only, no CTI lifecycle restarts.

## Database, migration, backup, and integrity

- PostgreSQL 16.14 accepts connections; database size is 35 MB; 8 sessions/1 active at capture.
- Alembic revision is `0013_op_retention`; it matches repository migration head. No pending or failed migration is evidenced; no migration was run.
- Latest run: `4f8db05e-c29a-5c80-bfe0-464edad4a18e`, failed, 14 total / 12 successful / 2 failed / 110 new documents, application `0.1.0`, error summary `2 source(s) failed`.
- Failed sources: Google TAG (`http_error`, HTTP 404) at `https://blog.google/threat-analysis-group/rss/`; MSRC (`malformed_xml`) because `https://msrc.microsoft.com/blog/feed` redirects to HTML at `https://www.microsoft.com/en-us/msrc/blog`. Direct probes reproduced both failures. Other 12 source runs completed (HTTP 200 or 304).
- Current counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks for entity evidence, relationship evidence, and current report versions each returned zero.
- Latest encrypted backup: `/backups/hermes-20260828T165615Z.dump.enc`, mode 600, 3,507,536 bytes, SHA-256 `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`; metadata mode 600 and backup healthcheck passed. Metadata age was 11h 52m at capture; no restore was attempted and no backup was deleted.

## Cause assessment

- **High confidence, causal:** stale/invalid Google TAG and MSRC source contracts explain the exact repeated two-source partial failures. This is a source/provider contract problem.
- **High confidence, contributing:** no fully successful ingestion run exists, creating freshness and publication risk for affected feeds.
- **Medium confidence, operational:** the mutable production image tag weakens release reproducibility even though the current image digest is recorded; no formal release/approval record was found in the repository snapshot.
- **Medium confidence, monitoring/proxy:** monitor route checks have historically mismatched the host Nginx policy; external 9444 intentionally returns 404 for unauthenticated/non-exposed paths while internal application health remains good.
- **Low/no evidence:** web process failure, proxy/TLS failure, scheduler crash, PostgreSQL failure, migration failure, resource exhaustion, backup failure, publication persistence failure, or data corruption.

## Actions and approvals

- Completed read-only probes for repository/release identity, Compose validation, container state/restarts/health, application and proxy health, logs, Docker events, host resources/FDs, database connectivity/revision/integrity, source contracts, backup metadata/hash, Nginx, and TLS.
- **No restart, migration, rollback, restore, source edit/disablement, proxy reload, credential action, Docker prune, volume operation, or data/publication mutation.**
- Smallest reversible action is **no restart**: restarting cannot repair the two upstream contracts and could obscure evidence. Rollback is not indicated; no approved immutable compatible target or approval reference is documented.
- Incident record created at this path. No external issue/PR destination was supplied.

## Service/data-integrity state and prevention

- Service state: public portal, web/API liveness, private readiness, scheduler heartbeat, PostgreSQL, and backup are operational; ingestion is degraded.
- Data-integrity state: no corruption or orphan evidence found; partial successful results and provenance are retained; backup exists and passed its healthcheck.
- Rollback/recovery: not performed and not required. Destructive recovery remains unauthorized.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with mocked 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; ensure only `status='completed'` is treated as successful; reconcile monitor checks with Nginx's route policy; require immutable image digests plus release/approval records and a compatible rollback target; verify the next backup and schedule an approval-gated isolated restore rehearsal.

Approvals are required for source/config or code release, restart, migration, restore, proxy reload, credential operations, deployment, or rollback.
