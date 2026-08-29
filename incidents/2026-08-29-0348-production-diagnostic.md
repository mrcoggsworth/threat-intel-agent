# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 03:48 UTC (2026-08-28 22:48 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The public/private web process and PostgreSQL are available, but scheduled ingestion is degraded. The latest persisted run began at 2026-08-29 02:00:00Z and is `failed`: 14 sources, 12 completed, 2 failed, and 110 new documents. PostgreSQL contains six persisted runs, all `failed`, and no run with `status='completed'`. The 12 successful-source results and partial-run provenance remain persisted; existing documents, evidence, indicators, reports, and publications remain present. No data-integrity mutation was performed and no orphan evidence was found in the preceding diagnostic record.

The supplied private endpoint returns intentional proxy 404s for paths not exposed by the 9444 policy (`/health`, `/ready`, `/docs`); this is not evidence of a web-process outage. Internal application liveness/readiness/version probes return 200.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, merge of PR #41. Working-tree additions are incident records only; no overlapping source, migration, Compose, or application edits were found.
- Application version: `hermes-cti 0.1.0`.
- Running application image: mutable `cti-hermes:local`, image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; created 2026-08-28 16:55:53Z. Web/scheduler/backup/monitor started 2026-08-28 16:56Z. PostgreSQL started 2026-08-26 23:20Z.
- Compose config hash: `3d72c4d61d86a445680999cfed5d0f1be55c97ebe3bd5b5c93cdd1eb67db7743`; source registry hash: `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`; settings hash: `de5b6d30b1f780255f5a0327c8561255636a2c174f85a4c306475090cd73ec3e`.
- Compose read-only validation remains blocked because protected `HERMES_SECRET_DIR` is not present in the supplied environment. No secret contents were read.

## Runtime, health, proxy, and host evidence

- `cti-hermes-web-1`, `cti-hermes-scheduler-1`, `cti-hermes-postgres-1`, `cti-hermes-backup-1`, and `cti-hermes-monitor-1` are running and Docker-healthy. The worker exited 0 by design (`restart: no`) and is a reserved one-shot/later-phase service; its healthcheck reports unhealthy after exit.
- Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3. All inspected CTI containers report `OOMKilled=false`. No container lifecycle events were returned in the sampled 48-hour Docker event window.
- Internal application probes: `/health/live` 200 `{"status":"ok"}`, `/health/ready` 200 with configuration/database checks `ok`, `/version` 200 with version `0.1.0`. The private ops paths are reachable internally; the external 9444 listener intentionally proxies only the private route pattern and returns 404 for other paths.
- Scheduler heartbeat is writable, non-empty, mode 644, and fresh at capture (`2026-08-29T03:47:49Z`). Scheduler logs show repeated source-collection failures without a crash loop. Monitor logs show repeated route-contract failures because its configured public/private checks do not match the host proxy policy.
- Host capacity is normal: root filesystem 504G total/175G used/308G free (37%); 62GiB RAM with approximately 58GiB available and swap unused; shell open-file limit 4096. No disk, memory, or file-descriptor exhaustion evidence.
- Nginx is active with `NRestarts=0` since 2026-08-26 18:20:33 CDT. TLS certificate subject is `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt YE1, valid 2026-08-18 through 2026-11-16, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`. Certificate mode is 644 and key mode 600. No proxy reload or privileged config test was attempted.

## Database, migration, backup, and integrity

- PostgreSQL 16 accepts connections (`pg_isready` passing), database size is 35 MB, and the database is reachable from the application. Current Alembic revision is `0013_op_retention`; it matches repository head. No migration was run and no pending/failed migration is evidenced.
- Latest source-run failures are `google-threat-analysis-group` (`http_error`, HTTP 404) and `microsoft-security-response-center` (`malformed_xml`, HTML returned where XML was expected). The configured Google URL is `https://blog.google/threat-analysis-group/rss/`; the configured MSRC URL is `https://msrc.microsoft.com/blog/feed`. Direct probes returned Google HTTP 404 HTML and MSRC HTTP 200 HTML after redirect to `https://www.microsoft.com/en-us/msrc/blog`.
- Current persisted counts: 1,889 source documents, 65 raw artifacts, 1,908 evidence claims, 3,494 indicators, 453 reports, and 454 publications. No restore, cleanup, or data mutation was attempted.
- Latest encrypted backup metadata is present and mode 600: completed `2026-08-28T16:56:16Z`, artifact size 3,507,536 bytes, artifact SHA-256 `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`. Backup healthcheck passes; no restore was attempted. The backup service has been running since 16:56Z and its scheduled interval is 24 hours, so the age is expected but the next backup should be verified.

## Cause assessment

- **High confidence, causal:** two stale/invalid configured source contracts explain the repeated two-source partial failures. Google returns 404, while MSRC redirects to an HTML page and cannot be parsed as RSS/XML. This is a source/provider contract problem, not a web, worker, scheduler-process, database, disk, certificate, or deployment crash.
- **High confidence, contributing:** no fully successful ingestion run exists; the latest run remains failed despite 12 successful sources. This creates freshness/publication risk for affected feeds and exposes a status-semantics weakness if failed completion is treated as success by any CLI/monitor path.
- **Medium confidence, operational:** the mutable `cti-hermes:local` image tag and unavailable protected Compose environment prevent strong release reproducibility and complete deployment preflight validation.
- **Medium confidence, monitoring:** monitor logs report route-contract failures because the host Nginx configuration intentionally returns 404 on port 9443 and only exposes selected private paths on 9444. This can create false incident signals, but internal service health is passing.
- **Low/no evidence:** web/proxy process failure, scheduler crash, PostgreSQL failure, pending migration, resource exhaustion, certificate expiry, backup failure, publication persistence failure, or data corruption.

## Actions and approvals

- Completed read-only preflight: repository identity/status, release/image metadata, container state/restarts/health, application probes, logs, Docker events, host resources, database connectivity/revision, source probes, backup metadata/hash, Nginx/TLS state, and configuration timestamps.
- **No operational mutation:** no restart, migration, rollback, restore, source edit/disablement, Nginx reload, credential operation, Docker prune, volume operation, or data/publication mutation.
- Smallest reversible action is **no restart**. A restart cannot repair the two upstream feed contracts and could obscure evidence. Rollback is not indicated; no approved immutable compatible target or approval reference is documented.
- This incident record is the maintenance handoff. No external issue/PR destination was supplied.

## Prevention and approval gates

1. Review and approve replacement/adapted Google TAG and MSRC source contracts; add mocked 404, redirect-to-HTML, malformed-XML, and partial-run fixtures.
2. Correct success semantics so only `status='completed'` is a successful run; distinguish partial ingestion from full success in monitor and CLI endpoints.
3. Reconcile monitor route checks with the deployed Nginx policy and use an authenticated, reachable operations contract.
4. Require immutable image digests and release records containing commit, Compose/source hashes, migration revision, approval, and compatible rollback target.
5. Provide protected production environment discovery for non-secret Compose validation.
6. Verify the next scheduled encrypted backup and schedule an approval-gated isolated restore rehearsal; perform a privileged Nginx config test only with approval.

Approvals are required for source/config or code release, restart, migration, restore, proxy reload, credential operations, deployment, or rollback. Destructive recovery remains unauthorized and unnecessary.
