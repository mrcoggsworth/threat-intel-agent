# Production ingestion incident: actionable partial failure, recovery suppressed (04:31Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T04:32:26Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` in `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was unset in the cron shell, so the Compose-mounted fallback was used.
- **Monitor state:** `actionable_failure`
- **Evidence event:** `c3f0a537-471a-4a74-bb42-135b0aaaf012`
- **Evidence observed at:** `2026-09-17T04:30:25.966904+00:00`
- **Endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Evidence correlation ID:** `d7663600-f406-4d75-9af8-47f84cfaf354`
- **Run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Signal:** `latest_ingestion_attempt=actionable_failure`, detail `1 source(s) failed`.
- **Post-gate evidence refresh:** event `33154787-4cd5-4cba-bdc1-819f5fb3f0c1`, observed `2026-09-17T04:32:26.095230+00:00`, correlation `5b164636-a7b1-4316-87d8-a880489956bf`, same actionable state and run.

The shared 1,800-second recovery cooldown and `/runtime` lock were evaluated before any recovery action. The gate acquired attempted event `72f04fe9-2083-4b0a-a9e5-0cf0a75a588b` at `2026-09-17T04:31:30.976624+00:00` with gate correlation `f70dc340-0d9f-4214-b477-680304444b7b`; it was completed with outcome `suppressed` because this scheduled request authorizes diagnosis only. Audit read-back verified both records and `/runtime/recovery.lock` absent.

## Impact and diagnosis

The latest persisted collection started `2026-09-17T02:00:00.087498+00:00` and completed `2026-09-17T02:00:54.951189+00:00`. It is terminal `failed` with 38 total sources, 37 successful, 1 failed, and error summary `1 source(s) failed`. Successful source documents remain persisted, but full-success freshness is represented by the previous successful run `ff79134f-5fbf-5469-ba5a-80b739ee58b9` from `2026-09-16T02:00:00Z`.

The failed source is **Krebs on Security** (`https://krebsonsecurity.com/feed/`), with `content_type_error`, detail `response content type did not match source policy`, no recorded HTTP status, and zero items. This is a source/provider response-policy mismatch, not a database or service outage. Cause confidence is **high** for the immediate failure; whether the upstream response variation is transient or requires a narrowly scoped parser-policy change remains uncertain. A separate persistent ACSC source failure remains outside this run's failed-source record.

Operational impact is partial ingestion: 37/38 sources completed and source-document persistence advanced to `2026-09-17T02:00:53.466767Z`; reports, report versions, publications, detections, hunts, and remediation have not advanced since `2026-09-11T22:24:37.163555Z` (186 reports, 201 report versions, 201 publications). The latest run remains usable for partial source coverage but is not a full-success run.

## Runtime, persistence, and external checks

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`; branch `main`; HEAD `90bc266e1c8d1397dac025c1f59970c31e976323`; working tree was clean before this incident record.
- Application version: `0.1.0`; running image tag `cti-hermes:local`; image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`.
- Web, scheduler, monitor, backup, and PostgreSQL containers are running healthy with restart count 0 and `OOMKilled=false`. The worker is intentionally one-shot (`restart: no`) and exited 0 but reports unhealthy under its reserved healthcheck; it is not the collection execution path.
- Application liveness and readiness returned HTTP 200; readiness reported configuration and database `ok`. Scheduler logs contain only `source collection failed`; monitor logs repeatedly report the actionable latest-attempt failure. No crash/restart was observed. Docker events in the window were diagnostic health-check/exec events only.
- PostgreSQL is accepting connections: PostgreSQL 16.14, database size 286,759,959 bytes, 4 sessions, 0 waiting locks. Database revision query reports `0015_contradiction_lifecycle` (head). `alembic current` from the web container failed because its configured database target resolves to localhost inside the container; this is a CLI configuration defect, not evidence of pending migration or database unavailability. `hermes-cti db status` reported last successful run `ff79134f-5fbf-5469-ba5a-80b739ee58b9` and no stale run IDs.
- Latest encrypted backup metadata: `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, 26,683,360 bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`. Backup container is healthy; restore verification was not attempted.
- Host capacity is normal: root filesystem 43% used with 277G available, 62GiB RAM with about 51GiB available, swap nearly unused, open-file limit 4096, load average 0.39/0.41/0.37.
- TLS inspection for `matrix-1.taild27e3c.ts.net:9444` succeeded; certificate subject matches host, issuer Let's Encrypt YE1, valid through `2026-11-16T14:30:36Z`. No certificate cause found.
- Containers were recreated/started on `2026-09-15T20:53:55Z`; protected production environment file mtime is `2026-09-10T18:42:11-05:00`. No deployment or configuration mutation was performed during diagnosis.

## Actions, integrity, rollback, and prevention

- Read authoritative monitor evidence before model work and recorded the required state, event, observation time, endpoint/status, correlation, and run identifiers.
- Evaluated the recovery gate with cooldown and lock; recorded attempted and completed-suppressed events; verified the lock was released.
- No retry, restart, deployment, migration, source/configuration edit, credential change, publication mutation, restore, volume/data deletion, backup deletion, or destructive recovery was performed.
- **Data integrity:** preserved. Failed source/run evidence and successful partial ingestion remain intact; no public CTI conclusions were changed.
- **Rollback:** not applicable because production state was not mutated. Any future parser/configuration fix must be deployed through `./scripts/update-app.sh` and rolled back by reverting that focused change and rerunning the same script if validation fails.
- **Prevention:** add a mocked content-type mismatch regression fixture and review a narrowly scoped, provenance-preserving Krebs RSS policy adjustment; separately investigate the container migration-target configuration and persistent ACSC failure. Keep recovery retries gated until a safe, tested fix is available.
