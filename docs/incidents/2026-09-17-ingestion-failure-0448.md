# Production ingestion incident: actionable partial failure, recovery suppressed (04:48Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T04:48:21Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the Compose-mounted fallback was read before diagnosis.
- **Monitor state:** `actionable_failure`
- **Evidence event:** `f2861362-322a-423c-ace7-1223fa439c6f`
- **Evidence observed at:** `2026-09-17T04:45:27.051441+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Evidence correlation ID:** `3c0d98bf-6a4c-4545-b965-b87e96136919`
- **Run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Signal:** `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.

The shared 1,800-second recovery cooldown and `/runtime` lock were evaluated before any recovery action. The gate returned `allowed=false` with reason `recovery cooldown is active`; it recorded a suppressed event at `2026-09-17T04:46:16.652670+00Z`. Read-back verified `/runtime/recovery.lock` is absent. No retry, restart, deployment, or other recovery action was authorized or performed.

## Impact and diagnosis

The latest persisted collection started `2026-09-17T02:00:00.087498+00Z` and completed `2026-09-17T02:00:54.951189+00Z`. It is terminal `failed` with 38 total sources, 37 successful, 1 failed, 29,841 new documents, and error summary `1 source(s) failed`. The previous run `ff79134f-5fbf-5469-ba5a-80b739ee58b9` at `2026-09-16T02:00:00Z` is the latest full-success run (38/38). The latest run remains usable for partial source coverage but is not full-success.

The failed source is **Krebs on Security** (`https://krebsonsecurity.com/feed/`), with `content_type_error`, detail `response content type did not match source policy`, no recorded HTTP status, and zero items. This is a provider response-policy mismatch, not a web, scheduler, database, capacity, certificate, or backup outage. Immediate cause confidence is **high**; whether the upstream variation is transient or needs a narrowly scoped parser-policy adjustment remains uncertain.

Successful source documents remain persisted through `2026-09-17T02:00:53.466767+00Z`. Reports, report versions, and publications remain unchanged since `2026-09-11T22:24:37.183379+00Z` (186 reports, 201 versions, 201 publications). Public CTI conclusions were not changed.

## Runtime, persistence, and external checks

- **Repository/release:** `git@github.com:mrcoggsworth/threat-intel-agent.git`, branch `main`, HEAD `5ac43baca3cd56cff54a2069ccff51cf4c709ad4`; working tree was clean before this incident record. Latest commit `2026-09-16T23:33:56-05:00` records the prior diagnostic.
- **Application/image:** application version `0.1.0`; running tag `cti-hermes:local`; image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`. Web, scheduler, monitor, PostgreSQL, and backup are running healthy with restart count 0 and `OOMKilled=false`.
- **Worker:** one-shot reserved worker exited 0 on `2026-09-15T20:53:57Z`, restart count 0, and reports unhealthy under its reserved healthcheck; it is not the scheduled collection execution path.
- **Health/readiness:** host web checks returned `health/live` HTTP 200 (`{"status":"ok"}`) and `health/ready` HTTP 200 (`configuration=ok`, `database=ok`). The host unauthenticated `/api/v1/ops/*` paths returned 404, while the monitor's internal run-status endpoint returned 200; this topology difference is not the ingestion cause.
- **Scheduler/monitor:** scheduler heartbeat was fresh at `2026-09-17T04:47:38Z`; scheduler logs report only `source collection failed`; monitor logs repeatedly report the actionable latest-attempt failure. No crash or restart was observed.
- **Database/migrations:** PostgreSQL 16.14 accepts connections; database size is 286,759,959 bytes, with 12 sessions and 0 waiting locks. Alembic revision is `0015_contradiction_lifecycle` (head observed in `alembic_version`); no pending or failed migration evidence was found.
- **Backups:** latest encrypted backup metadata is `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, 26,683,360 bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`; backup container is healthy. Restore verification was not attempted.
- **Capacity/file descriptors:** root filesystem 43% used with 277G available; host memory 62GiB total/51GiB available; swap nearly unused; open-file limit 4096. No capacity cause found.
- **Certificate:** `matrix-1.taild27e3c.ts.net` certificate subject matches host, issuer Let's Encrypt YE1, valid `2026-08-18` through `2026-11-16T14:30:36Z`; no certificate cause found.
- **Deployment/config:** containers were started/recreated on `2026-09-15T20:53:55Z`; protected production environment mtime is `2026-09-10T18:42:11-05:00`. No deployment or configuration mutation occurred during diagnosis.

## Actions, integrity, rollback, and prevention

- Read and recorded the required authoritative monitor identifiers before diagnosis.
- Evaluated the recovery gate with cooldown and lock; recorded the suppressed event and verified lock absence.
- Preserved failed source/run evidence and successful partial ingestion. No database, volume, backup, credential, publication, or CTI assessment mutation was made.
- Rollback is not applicable because production state was not mutated. A future focused parser/configuration fix must be validated and deployed only through `./scripts/update-app.sh`; revert that focused change and rerun the script if health checks fail.
- Prevention: add a mocked content-type mismatch regression fixture and review a narrowly scoped, provenance-preserving Krebs RSS policy adjustment. Keep retries gated until a safe fix is tested. Separately investigate the host/internal operations-route mismatch, reserved worker healthcheck semantics, and persistent source failures without bypassing source failure visibility.
