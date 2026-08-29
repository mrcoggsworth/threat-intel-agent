# CTI-Hermes production diagnostic

**Capture:** 2026-08-28 16:03 CDT (2026-08-28 21:03Z)
**Target:** `https://matrix-1.taild27e3c.ts.net:9444`
**Incident summary supplied:** `__INCIDENT_SUMMARY__` (literal placeholder; diagnosis based on live state).

## Impact

The web/API, private readiness surface, scheduler, PostgreSQL, monitor, and backup service are available. Ingestion freshness is degraded: all five persisted ingestion runs are `failed`; the latest run processed 12/14 sources and created 1,840 new documents. Successful-source output and failed-source provenance remain retained. There is no evidence of data corruption or an empty database.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`.
- Branch: `incident/2026-08-28-1448-production-diagnostic`; working tree clean at capture.
- HEAD: `a84a20340aad85bcb1777928dc2f7270468eec17`, merge of PR #41 (`feat: date-from filtering`).
- Application version: `hermes-cti 0.1.0`.
- Running application image: mutable tag `cti-hermes:local`; web, scheduler, and monitor image ID/digest `sha256:605e713b2e5087260e9a85985f7d07ea54c4e6d18832a0cf58e3796fb4d9efc1`. No approved immutable rollback target was identified.
- PostgreSQL image digest: `sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb`; backup image digest: `sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5`.
- Application containers started around `2026-08-28T16:56:14Z`; PostgreSQL has run since `2026-08-26T23:20:36Z`. Repository deployment commit is dated `2026-08-28 11:54:51 -0500`. `deploy/docker-compose.yml` mtime is `2026-08-26 20:14:30 -0500`; protected production env mtime is `2026-08-25 17:20:29 -0500`. No later config-file change was evidenced.
- A fresh local Compose config validation was attempted but could not complete because this shell did not supply the required `HERMES_SECRET_DIR`; this is a preflight/provenance gap, not evidence of a running-stack failure.

## Service, restart, and resource state

- `cti-hermes-web-1`, `scheduler-1`, `postgres-1`, `backup-1`, and `monitor-1` are running and Docker-healthcheck `healthy`.
- `worker-1` is the intentional reserved one-shot service: exited 0 with restart policy `no`; runtime-init also exited 0 as designed. Restart counts: web 0, scheduler 0, PostgreSQL 0, backup 0, monitor 3 during startup-check churn, worker 0. Checked services report `OOMKilled=false`.
- Scheduler heartbeat is current: `/runtime/scheduler.heartbeat` mtime `2026-08-28T21:03:16Z`, content matching that timestamp. Recent scheduler logs contain only `source collection failed`.
- Nginx is active, `NRestarts=0`, and listens on `100.68.61.10:9443` and `:9444`; the app is loopback-bound on `127.0.0.1:18000`.
- Host capacity is normal: root filesystem 504G total / 175G used / 308G available (37%); 62GiB RAM with about 57GiB available; swap unused; file table 3,232 allocated against an effectively unlimited maximum; host `ulimit -n` 4096. Container memory is low (web 81.9MiB, scheduler 83.1MiB, PostgreSQL 149.4MiB). No disk, memory, or FD pressure is indicated.
- Docker event observations show healthcheck/exec activity only; no application crash-loop or current lifecycle churn.

## Health, proxy, and certificate

- Loopback `/health/live`: HTTP 200 `{"status":"ok"}`.
- Loopback `/health/ready`: HTTP 200 with `configuration=ok` and `database=ok`.
- Private TLS `:9444/health/ready`: HTTP 200; `/version`: HTTP 200, `0.1.0`.
- TLS verification succeeds for `CN=matrix-1.taild27e3c.ts.net`, issuer Let's Encrypt `YE1`, valid `2026-08-18T14:30:37Z` through `2026-11-16T14:30:36Z`, SHA-256 fingerprint `DB:1F:E8:15:D0:6C:F5:03:79:EE:52:84:9B:28:B6:84:66:4C:44:31:0D:8B:29:88:AA:2E:BD:4B:9B:B4:12:1A`.
- Private root and unrecognized paths returning 404 are expected Nginx route isolation. Monitor startup logs recorded three generic failures during recreation, then the monitor became healthy; current liveness/readiness probes pass.

## Database, migration, backup, and integrity

- PostgreSQL `16.14` accepts connections (`pg_isready`: accepting connections); the database is populated.
- Current Alembic revision: `0013_op_retention`; repository head: `0013_op_retention`. No pending or failed migration was evidenced; no migration was run.
- Latest run `43b7881e-965a-56c5-9bdd-eb0cdb207ed7`: started `2026-08-28T16:56:16.219818Z`, completed `2026-08-28T16:56:18.054359Z`, status `failed`, 14 total / 12 successful / 2 failed / 1,840 new documents. All five runs are failed; last fully successful run: **none**.
- Latest failed sources: Google Threat Analysis Group (`HTTP 404`) and Microsoft Security Response Center (`malformed_xml`, XML could not be parsed). The other 12 sources completed HTTP 200.
- Current database counts: 1,885 source documents, 61 raw artifacts, 1,908 evidence claims, 3,494 indicators, 453 reports, and 454 publications. Inspected entity-evidence and relationship-evidence orphan counts are both zero.
- Latest encrypted backup: `/backups/hermes-20260828T165615Z.dump.enc`, 3,507,536 bytes, mode 600. Recomputed dump SHA-256: `b2c175aa85135a5af6aee2e0fcbf902eefd77d7e072b00fbc000fe86a4563737`. Backup metadata exists, mode 600, and backup container is healthy. No restore was attempted.

## Failure evidence and cause assessment

- Live probe of configured Google TAG URL `https://blog.google/threat-analysis-group/rss/` returns HTTP 404 with HTML.
- Live probe of configured MSRC URL `https://msrc.microsoft.com/blog/feed` follows to `https://www.microsoft.com/en-us/msrc/blog` and returns HTTP 200 HTML, not RSS/XML.
- **High confidence, causal:** two enabled upstream source endpoints no longer satisfy the RSS/XML adapter contract, deterministically failing each run while preserving partial output and failure provenance.
- **High confidence, contributing:** the application `db status` output and prior authenticated operations behavior label the latest failed partial run as `last_successful`; this can falsely signal freshness and suppress alerting. A direct unauthenticated loopback probe returns 404, as expected for the protected operations route.
- **Low/not causal:** web, proxy, scheduler heartbeat, PostgreSQL, migrations, disk, memory, file descriptors, certificate, backup creation, and current container crash-loop state.
- **Medium operational risk, not proven causal:** mutable production image tag, absent release approval metadata, and incomplete operator-side Compose validation reduce rollback and release defensibility.

## Actions, integrity, rollback, and approvals

- **Action taken:** read-only preflight covering repository/release, Compose validation attempt, container state/restarts/OOM, health/readiness, logs/events, host/container resources, database/migration state, source probes, backup metadata/hash, TLS, and referential-integrity checks; this local incident record was created.
- **No operational mutation:** no restart, migration, rollback, restore, credential operation, source disablement, configuration edit, Nginx reload, Docker prune, volume deletion, or publication/data mutation was performed.
- **Smallest reversible action:** no operational action. Restart cannot repair deterministic upstream endpoint failures and could obscure evidence.
- **Service state:** available but degraded for ingestion freshness and monitoring correctness.
- **Data-integrity state:** preserved; partial successful-source results and failed-source provenance remain in PostgreSQL, and inspected FK integrity is clean.
- **Rollback:** not attempted. No reviewed compatible immutable target or approval reference is documented.
- **Approvals required:** source/configuration repair, adapter or code/image change, restart, migration, restore, credential operation, proxy change, or deployment. Destructive recovery remains unauthorized and unnecessary.

## Prevention and follow-up

1. Review and approve replacement URLs/adapters for Google TAG and MSRC; add mocked 404, redirect-to-HTML, and malformed-feed fixtures while retaining failed source-run evidence.
2. Correct last-success semantics to require `status=completed` for a fully successful run, and add authenticated route/monitor regression tests distinguishing partial from total failure.
3. Alert distinctly on partial-source failures versus total pipeline failure; preserve safe response classification and failure provenance.
4. Use immutable image digests and record commit, Compose/config hash, migration revision, approval, and compatible rollback target for every release; document the protected env path for operator-side Compose validation.
5. Run an approved isolated encrypted-backup restore rehearsal; never target production.

**Incident record:** this file. No external GitHub issue or PR was created because the scheduled request supplied no issue target or approval reference.
