# CTI-Hermes production diagnostic

**Capture:** 2026-08-29 08:49 UTC (2026-08-29 03:49 CDT)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder).

## Impact

The service is not a total outage. Private readiness and the public portal are reachable, but scheduled ingestion is degraded: the latest run failed for 2 of 14 enabled sources, and the database contains six failed runs with zero `completed` runs. Twelve source results and partial documents remain retained. Analyst report publication/write attempts also returned HTTP 500 during the capture window because of a duplicate report slug. The supplied private port intentionally exposes readiness/operations rather than public liveness; liveness is available on 9443, so a single-port health checker can report a false failure.

## Repository and release identity

- Remote: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; HEAD `a84a20340aad85bcb1777928dc2f7270468eec17` (also `main`/`origin/main`), merge of PR #41 on 2026-08-28 11:54:51 -0500.
- Working tree contains only the pre-existing incident records and untracked `introspect_temp.py`; no application, migration, Compose, or source edits overlap this diagnosis.
- `/version` reports `{"name":"hermes-cti","version":"0.1.0"}`.
- Running web/scheduler/worker image is mutable `cti-hermes:local`, image ID `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`; Compose label digest observed previously is `sha256:b34c83eb6f79d75665d7f70ae31012877aef18c3d6b094afb119141109cbcd47`. No immutable release record or approval reference was found.
- Web, scheduler, PostgreSQL, backup, and monitor were started/replaced at 2026-08-28 16:56:14Z (PostgreSQL at 2026-08-26 23:20:36Z). Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, worker 0, monitor 3. Worker exited code 0 at 16:56:16Z under its documented reserved-entrypoint design; it is not evidence of a crash.

## Service, proxy, certificate, and resource evidence

- On 9443: `/health/live` HTTP 200. On 9444: `/health/live` HTTP 404, `/health/ready` HTTP 200 with configuration/database `ok`, and `/version` HTTP 200 with version `0.1.0`. Nginx is active with `NRestarts=0` since 2026-08-26 18:20:33 CDT. The checked-in split route policy explains the complementary 404s; this is an ingress-contract/monitoring issue, not web liveness failure.
- Container health: web, scheduler, PostgreSQL, backup, and monitor healthy. Scheduler heartbeat is current (`2026-08-29T08:48:21Z`) and the monitor one-shot check exited 0. All inspected CTI containers report `OOMKilled=false`.
- Host is healthy: load `0.08, 0.05, 0.07`; root filesystem 37% used with 308G available; 57GiB available of 62GiB memory; swap unused; `/proc/sys/fs/file-nr` `2656 0 9223372036854775807`; shell descriptor limit 4096. No resource exhaustion is indicated.
- TLS verification succeeded. Certificate subject `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt YE1, valid 2026-08-18 14:30:37Z through 2026-11-16 14:30:36Z, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.

## Database, migration, backup, and integrity evidence

- PostgreSQL 16.14 accepts connections; readiness reports database `ok`. Live Alembic revision is `0013_op_retention`, matching repository migration head `0013_op_retention`; no migration was run and no pending/failed migration is evidenced.
- Latest run `4f8db05e-c29a-5c80-bfe0-464edad4a18e` started 2026-08-29 02:00:00.091Z and completed 02:00:01.945Z: `failed`, 14 total, 12 successful, 2 failed, 110 new documents. The six-run history is `failed=6`, `completed=0`; the last fully successful run is `NONE`.
- Persisted latest failures are `google-threat-analysis-group` (`http_error`, HTTP 404) and `microsoft-security-response-center` (`malformed_xml`). The other 12 sources returned HTTP 200/304.
- Corrected referential-integrity checks found zero non-null `entity_evidence.source_document_id` orphans, zero invalid evidence rows, zero orphan current report versions, and zero duplicate active report slugs. Partial-run data/provenance remains retained; no corruption signal is present.
- PostgreSQL logs show a burst of duplicate `report.slug` violations at 2026-08-29 08:05:56–08:05:58Z for slug `train-triage-repeat-the-ai-agent-changing-how-we-fight-phishing`, followed by repeated analyst `POST /api/v1/analyst/reports` HTTP 500 responses. These are failed transactions and did not create duplicate rows, but report authoring/publication writes are degraded for that slug.
- Latest encrypted backup is `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, completed 2026-08-28T16:56:16Z, mode 600. Read-only SHA-256 matches metadata: `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`. It predates the latest ingestion run; isolated restore rehearsal remains outstanding.

## Cause assessment

- **High confidence causal for ingestion:** authoritative `config/sources.json` contains stale/incompatible RSS contracts: Google TAG `https://blog.google/threat-analysis-group/rss/` currently returns HTTP 404 HTML; MSRC `https://msrc.microsoft.com/blog/feed` returns HTTP 301 to `https://www.microsoft.com/en-us/msrc/blog`, then HTTP 200 HTML rather than RSS/XML. This exactly matches the persisted `http_error` and `malformed_xml` classifications.
- **High confidence separate publication defect:** report creation/update attempts collide with the existing unique `uq_report_slug` constraint and surface HTTP 500 rather than a safe validation/conflict response. This affects analyst report writes, not existing published rows or database integrity.
- **High confidence contributing:** six consecutive failed partial runs and zero completed runs create source freshness risk while successful partial data is preserved.
- **Medium confidence operational/security:** 9443/9444 route policy is not a single-port health contract; `/opt/cti-hermes/env/production.env` mode 600 (mtime 2026-08-25 17:20:29 -0500) omits required `HERMES_SECRET_DIR`, so Compose validation fails without explicitly supplying it, although validation succeeds when supplied. `analyst-token` is mode 644 while `admin-token` is mode 600. The running image is mutable and lacks release traceability. These do not explain the upstream source failures.
- **Low/no evidence as causes:** web process, scheduler heartbeat, PostgreSQL connectivity, migration state, disk, memory, file descriptors, TLS, backup checksum, and referential corruption.

## Actions and approvals

- Completed read-only checks of repository/release identity, Compose validation, container state/restarts, Docker events, health/readiness, application and database logs, proxy/listeners, resources, database connectivity/revision/run state, source responses, heartbeat, backup metadata/checksum, certificate, and protected-file metadata.
- Compose syntax validation succeeded with explicit `HERMES_SECRET_DIR=/opt/cti-hermes/secrets` and `HERMES_IMAGE=cti-hermes:local`; it fails using only the protected env file because the required directory variable is absent.
- **No restart, migration, rollback, restore, proxy reload, source edit/disablement, credential operation, Docker prune, volume operation, or data/publication mutation was performed.** The smallest reversible action is no runtime action: restart cannot repair stale upstream contracts or the report-slug conflict and would discard useful evidence.
- This repository incident record was created. No external issue tracker destination was supplied, so no external issue or PR was created.

## Service/data-integrity/rollback state

- **Service:** core web/private readiness, public liveness on 9443, database, scheduler, backup, monitor, and TLS are operational. Ingestion is degraded for 2/14 sources. Analyst report writes are degraded for a conflicting slug. 9444 liveness 404 is expected under the split proxy policy but is an operational contract mismatch.
- **Data integrity:** no confirmed corruption; successful partial data and provenance retained; corrected orphan checks pass; failed duplicate-slug transactions did not violate uniqueness. Backup checksum passes but backup is stale to the latest run and restore rehearsal is outstanding.
- **Rollback:** not performed and not indicated. No documented approved immutable compatible rollback target was identified. Destructive recovery remains unauthorized.
- **Approvals required:** approved source/config or code release, protected environment correction, secret-mode correction, report-conflict handling change, proxy change/reload, deployment, migration, restart, restore rehearsal, or rollback.

## Prevention/follow-up

1. Approve replacement/adapted Google TAG and MSRC source contracts with 404, redirect-to-HTML, malformed-XML, and partial-run fixtures; retain partial-failure semantics and verify the next run.
2. Change report create/update conflict handling to return a typed safe conflict/validation response and add a regression test for an existing slug; preserve audit/provenance.
3. Align proxy route policy and monitor/health expectations, or explicitly document the two-port contract in operational checks.
4. Add `HERMES_SECRET_DIR` to the protected environment through approved maintenance, require immutable image digests and release records, and correct the world-readable analyst token mode.
5. Verify the next encrypted backup and perform an approval-gated isolated restore rehearsal without touching production data.
