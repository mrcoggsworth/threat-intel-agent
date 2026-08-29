# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 18:18 CDT (2026-08-28 23:18Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

Service availability is healthy, but ingestion freshness is degraded. The latest
persisted collection run is failed: 12/14 sources completed and 1,840 documents
were added; Google Threat Analysis Group and Microsoft Security Response Center
failed. Partial successful-source output and failure provenance remain persisted.
There are five failed runs and zero fully completed runs in the database. The
private `last-success` endpoint incorrectly reports the latest failed run's
completion timestamp, so freshness monitoring is materially misleading. No
public portal or database-integrity outage was observed.

## Identity and runtime evidence

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD
  `a84a20340aad85bcb1777928dc2f7270468eec17` (merge of PR #41). Working-tree
  changes are incident records only; no overlapping application/deployment
  source changes were found.
- Application version: `hermes-cti 0.1.0`.
- Web/scheduler/monitor image: `cti-hermes:local`, image ID and local digest
  `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`.
  PostgreSQL is `postgres:16-alpine`; backup is `postgres:16`.
- Web, scheduler, PostgreSQL, backup, and monitor are running and healthy.
  Worker is exited 0 with restart policy `no` (reserved idle entrypoint).
  Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, monitor 3;
  all inspected services report `OOMKilled=false`.
- Containers started 2026-08-28 16:56:14--16:56:16Z; PostgreSQL started
  2026-08-26 23:20:36Z. Host Nginx is active with `NRestarts=0` since
  2026-08-26 18:20:33 CDT. No relevant lifecycle restart/kill events were
  observed in the 48-hour Docker event review.
- Repository compose mtime is 2026-08-26 20:14:30 CDT, source registry mtime
  is 2026-08-16 15:36:31 CDT, and deployment script mtime is 2026-08-25
  19:44:41 CDT. No newer application/config source mutation was evidenced.

## Health, proxy, and certificate

- Loopback `/health/live` and `/health/ready` return 200; readiness reports
  configuration and database `ok`. `/version` returns `0.1.0`.
- External `/health/ready` returns 200. The supplied external port intentionally
  exposes only the private allowlist; external `/health/live` and root return
  Nginx 404 and are not evidence of application failure.
- Authenticated internal operations checks return: version `0.1.0`, readiness
  `ok`, scheduler heartbeat `2026-08-28T23:17:17Z`, and
  `last_success=2026-08-28T16:56:18.054359+00:00`. The latter is inconsistent
  with database status and is a monitoring/application defect.
- TLS verification succeeds. Certificate subject is
  `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt `YE1`, valid
  2026-08-18T14:30:37Z through 2026-11-16T14:30:36Z, SHA-256 fingerprint
  `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity

- PostgreSQL accepts connections; database size is 35 MB. Alembic revision is
  `0013_op_retention`, and repository `alembic heads` reports the same single
  head. No pending or failed migration was evidenced; no migration was run.
- Latest run ID `43b7881e-965a-56c5-9bdd-eb0cdb207ed7`, started
  `2026-08-28T16:56:16.219818Z`, completed
  `2026-08-28T16:56:18.054359Z`, status `failed`, 14 total / 12 successful /
  2 failed / 1,840 new documents. Failed sources: Google TAG `http_error`
  (HTTP 404), MSRC `malformed_xml` (XML could not be parsed).
- Counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence claims,
  3,494 indicators, 453 reports, 454 publications. No orphan entity evidence,
  relationship evidence, or current report versions; no empty database or
  corruption evidence.
- Latest encrypted backup is `hermes-20260828T165615Z.dump.enc`, 3,507,536
  bytes, mode 600, metadata-completed at 2026-08-28T16:56:16Z. Metadata checksum
  matches the artifact record and backup healthcheck is passing. No restore was
  attempted.

## Cause assessment

- **High confidence, causal:** configured Google TAG RSS URL
  `https://blog.google/threat-analysis-group/rss/` returns HTTP 404 HTML.
  Configured MSRC URL `https://msrc.microsoft.com/blog/feed` returns HTTP 301 to
  the MSRC blog and the resulting content is HTML, not RSS/XML. Direct probes
  reproduced both conditions. These deterministic upstream/adapter-contract
  failures explain the repeated two-source partial failures.
- **High confidence, contributing:** `last-success` returns a failed run's
  completion timestamp rather than requiring `status='completed'`, masking the
  absence of a fully successful run.
- **Low/no evidence as causes:** web, proxy, scheduler heartbeat/process,
  PostgreSQL, migration state, disk, memory, file descriptors, certificate,
  backup, publication persistence, and container crash state.
- **Medium operational risk:** running application uses mutable `cti-hermes:local`
  rather than an explicitly recorded immutable deployment reference. Compose
  validation from the checkout could not run because `deploy/.env` is absent;
  this is a preflight gap, not evidence that the active stack is down.

## Actions, state, and approvals

- Completed read-only preflight: repository identity/status, container health and
  restart/event review, service logs, local/external health probes, authenticated
  operations probes, TLS inspection, host resource checks, PostgreSQL/migration/
  integrity queries, source endpoint probes, and backup metadata review.
- **No operational mutation:** no restart, migration, rollback, restore,
  credential operation, source disablement, config edit, Nginx reload, Docker
  prune, volume deletion, or publication/data mutation.
- Smallest reversible action is no action: restart cannot repair deterministic
  upstream URL/format failures and could obscure evidence. Rollback is not
  indicated, and no approved immutable compatible target or approval reference
  is documented.
- Service/data-integrity state: available but ingestion-degraded; persisted
  partial output and provenance intact; no corruption evidence.
- Incident record created locally at this path. No external issue/PR was created
  because no issue target or approval reference was supplied.
- Approvals required: approve replacement source URLs/adapters and any code/image
  change; separately approve restart, migration, restore, proxy, credential, or
  deployment operations. Destructive recovery remains unauthorized and
  unnecessary.

## Prevention and follow-up

1. Approve replacement URLs/adapters for Google TAG and MSRC; add fixtures for
   404, redirect-to-HTML, malformed XML, and partial-run persistence.
2. Make `last_successful()` require a fully completed run and distinguish partial
   ingestion from fully successful freshness in alerts.
3. Require immutable image digests plus release records for commit, Compose/source
   hashes, migration revision, approval, and rollback target.
4. Supply the protected production env file to maintenance preflight and validate
   Compose in CI without exposing secrets.
5. Schedule an approved isolated encrypted-backup restore rehearsal.
6. Add privileged Nginx config-test/certificate-expiry checks to maintenance
   automation without weakening private-key permissions.
