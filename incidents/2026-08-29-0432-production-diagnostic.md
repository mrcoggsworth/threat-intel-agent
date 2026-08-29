# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 04:32 UTC (2026-08-28 23:32 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live probes and the latest detailed production snapshot).

## Impact

The application boundary is currently reachable and ready, but ingestion remains degraded based on the latest detailed production evidence: the latest persisted run was `failed` with 12/14 sources completed, 2 failed, and 110 new documents; no completed run was present in the captured database state. Partial successful-source output and provenance remain persisted. No data-integrity mutation or destructive recovery was performed.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17`, merge of PR #41. Working-tree changes are incident records only; no overlapping source, migration, Compose, or application edits were found.
- Live `/version` probe: HTTP 200, `{"name":"hermes-cti","version":"0.1.0"}`.
- Latest detailed production snapshot (2026-08-29 03:48 UTC) identified the running application image as mutable `cti-hermes:local`, image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`. A current remote image inspection was not available through the HTTP surface.
- Current source registry SHA-256: `825c0f11886c99b1bb2e60a75f08a57c2def919d3dfbd49948816da4f18eb715`.
- Repository-local Compose validation is blocked because the protected production `HERMES_SECRET_DIR`/environment is not present. No secret contents were read.

## Current health and proxy evidence

- Public liveness: `GET https://matrix-1.taild27e3c.ts.net:9443/health/live` returned HTTP 200, `{"status":"ok"}`. Response carried security headers and request ID `611cbb7677354495b9b73bc0db5f9666`.
- Private readiness: `GET https://matrix-1.taild27e3c.ts.net:9444/health/ready` returned HTTP 200, `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`.
- Private version: `GET https://matrix-1.taild27e3c.ts.net:9444/version` returned HTTP 200.
- Public portal: `GET https://matrix-1.taild27e3c.ts.net:9443/reports` returned HTTP 200. Public `/api/v1/ops/*` returned HTTP 404 as intended isolation.
- Private `/api/v1/ops/*` returned HTTP 404 without an admin token; this is consistent with fail-closed route/auth behavior and is not evidence of outage.
- TLS verification succeeded with OpenSSL. Certificate subject `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt `YE1`, valid 2026-08-18 14:30:37Z through 2026-11-16 14:30:36Z, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Runtime, database, backup, and host state

The current execution environment is the repository workstation, not the production Docker host. `docker compose ps -a` could not run because no Compose configuration was supplied in the environment; no production Docker command, restart, migration, or host mutation was attempted.

Latest detailed production snapshot, still the freshest available host-level evidence:

- Web, scheduler, PostgreSQL, backup, and monitor were running and Docker-healthy; worker exited 0 by design (`restart: no`). Restart counts were web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3; inspected containers had `OOMKilled=false`.
- Scheduler heartbeat was fresh; scheduler logs showed repeated source-collection failures without a crash loop. Monitor route checks were mismatched with the deployed host proxy policy.
- PostgreSQL 16 accepted connections; Alembic revision was `0013_op_retention`, matching repository head. No pending or failed migration was evidenced.
- Persisted counts were 1,889 source documents, 65 raw artifacts, 1,908 evidence claims, 3,494 indicators, 453 reports, and 454 publications. Orphan checks returned zero.
- Latest encrypted backup metadata was present and mode 600, completed 2026-08-28 16:56:16Z, 3,507,536 bytes, SHA-256 `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`; backup healthcheck passed. No restore was attempted.
- Host capacity was normal: 37% root filesystem use, approximately 58 GiB available RAM, swap unused, and no file-descriptor exhaustion evidence. Nginx had no observed restart; no lifecycle crash/restart events were found in the sampled window.

Current database connectivity is corroborated only by the live readiness response; current migration revision, restart history, Docker events, exact backup age, disk/memory/FD metrics, and current logs require production-host access or the authenticated operations API and were not guessed.

## Cause assessment

- **High confidence, causal:** two configured upstream source contracts are stale/invalid. Google TAG points to `https://blog.google/threat-analysis-group/rss/` and returned HTTP 404 HTML; MSRC points to `https://msrc.microsoft.com/blog/feed`, which redirected to an HTML blog page and failed XML parsing. These explain the repeated two-source partial failures.
- **High confidence, contributing:** no fully successful ingestion run was present in the latest database snapshot, creating freshness and publication risk for affected feeds.
- **Medium confidence, operational:** mutable `cti-hermes:local` image tagging and unavailable protected Compose environment weaken release reproducibility and prevent complete local deployment preflight.
- **Medium confidence, monitoring:** monitor checks and host Nginx route policy have differed, creating potential false alerts even while liveness/readiness pass.
- **Low/no evidence:** web outage, proxy/TLS failure, scheduler crash, PostgreSQL failure, migration failure, resource exhaustion, backup failure, publication persistence failure, or data corruption.

## Actions and approvals

- Completed read-only current probes for liveness, readiness, version, public portal, route isolation, TLS certificate validity, repository identity/status, and source-registry identity.
- No restart, migration, rollback, restore, source edit/disablement, proxy reload, credential operation, Docker prune, volume operation, or data/publication mutation.
- **Smallest reversible action:** no restart. A restart cannot repair upstream feed contracts and could obscure evidence; all available health probes are passing.
- Incident record created locally at this path. No external issue/PR destination was supplied.

## Service/data-integrity state, rollback, and prevention

- Service state: web/API and database readiness are currently OK; ingestion is degraded.
- Data-integrity state: no corruption evidence in the latest detailed snapshot; partial-run provenance is retained; no mutation was made during this diagnostic.
- Rollback: not indicated. No approved immutable compatible target or approval reference is documented. Destructive recovery remains unauthorized and unnecessary.
- Prevention: approve replacement/adapted Google TAG and MSRC contracts with mocked 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; correct success semantics so only `status='completed'` is successful; reconcile monitor routes with Nginx; require immutable image digests and release records; provide protected Compose environment discovery; verify the next encrypted backup and schedule an approval-gated isolated restore rehearsal.

Approvals are required for source/config or code release, restart, migration, restore, proxy reload, credential operations, deployment, or rollback.
