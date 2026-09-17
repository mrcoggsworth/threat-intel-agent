# CTI-Hermes production ingestion recovery diagnostic (05:16Z)

## Monitor evidence and recovery gate

- **Diagnosis time:** `2026-09-17T05:22:18Z`
- **Authoritative evidence:** `/runtime/monitor-evidence.json` inside `cti-hermes-monitor-1`; `HERMES_MONITOR_EVIDENCE_FILE` was not exported by the cron shell, so the configured container fallback was read before model work.
- **Initial monitor state:** `actionable_failure`
- **Initial event ID:** `9d0671dc-a2cc-44a0-80a4-35c0610a1188`
- **Initial observed at:** `2026-09-17T05:15:29.167805+00:00`
- **Initial endpoint/status:** `http://web:8000/api/v1/ops/run-status`, HTTP `200`
- **Initial correlation ID:** `f77255d0-5542-43fd-8f15-390b0400ad19`
- **Initial run ID:** `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6`
- **Initial failure:** latest ingestion attempt failed because `1 source(s) failed`.

The recovery gate was evaluated with the configured 1,800-second cooldown and shared `/runtime` lock. It returned `allowed=true` at `2026-09-17T05:16:07.405621Z`; the attempted event was recorded without secrets. A single authenticated manual collection was queued and completed. The gate was completed with outcome `completed` at `2026-09-17T05:21:59.855647Z`, and `/runtime/recovery.lock` was verified absent.

## Repository and release identity

- Repository: `git@github.com:mrcoggsworth/threat-intel-agent.git`
- Branch/HEAD: `main` / `ab434216dfd295fcdd3c21c4a648da5475099f3c`; repository was seven commits ahead of `origin/main`; no working-tree changes were present before this incident record.
- Running application image: mutable `cti-hermes:local`, image ID `sha256:5abf84107d230e0c3c66bd61e95172382dd9c97ecb8379fa6819cf983d40d4cd`, created `2026-09-15T20:53:44Z`; application containers started around `2026-09-15T20:53:55Z`.
- Application version: `0.1.0`.
- Database revision: `0015_contradiction_lifecycle`; no pending migration was evidenced. PostgreSQL is `16.14`.
- The checked-out source registry has the Krebs RSS URL without a special content-type override. The running database source configuration had `max_response_bytes=10485760`.
- Compose config validation from the cron shell remains unavailable because protected `HERMES_SECRET_DIR` and `HERMES_IMAGE` variables are not exported there. No deployment or configuration mutation was made.

## Diagnosis and impact

The scheduled run `7fbdf1bb-6c5f-5187-b6c9-51c949a211a6` completed `37/38` sources successfully at `2026-09-17T02:00:54.951189Z`, with `29,841` new documents and one failed source. The failed source was enabled `krebs-on-security` (Krebs on Security), with `error_classification=content_type_error` and detail `response content type did not match source policy`; it had no HTTP status or items. Its last successful retrieval was `2026-09-16T02:00:49.445479Z`, and its consecutive failure count was `1`.

Cause confidence is **high** for an upstream/source-policy mismatch isolated to the Krebs RSS response. The response was reachable and returned HTTP `200` during recovery; the recovery collection completed all `38/38` sources successfully. This is a partial source-coverage failure, not a web, proxy, scheduler, database, disk, certificate, backup, or migration outage.

During the recovery collection, the monitor briefly wrote `unknown` because its three internal checks timed out while the web process was busy. Final evidence returned `healthy` with event `941cda41-c8f2-4289-9fe1-8636a4ba1160`, observed `2026-09-17T05:21:44.521757Z`, correlation `c8ebe385-31ff-4b77-9c58-e21bc9dfba88`, and successful run ID `a4ac0da7-972e-5b32-8337-f014fc200a48`.

## Actions and verification

- Submitted one authenticated `POST /api/v1/ops/collection`; API returned `202 Accepted`, trigger `e2746fab-c22c-49d0-a8ac-18d0167d5d99`, run `a4ac0da7-972e-5b32-8337-f014fc200a48`.
- Read back the trigger: `completed`, `38/38` successful, `0` failed, completed `2026-09-17T05:19:54.463209Z`.
- Read back persistence: the run is present with application version `0.1.0`, configuration hash `a3da6c931e7fff92640e4e882f7dd0fd31c4d94fe2fd0465b1669fe78943176f`, `28,970` new documents, and no failed `source_run` rows.
- Web health/readiness returned HTTP `200`; PostgreSQL `pg_isready` and read-only queries succeeded. Web, monitor, scheduler, backup, and PostgreSQL containers were healthy with restart count `0` and no OOM evidence.
- Host capacity was healthy: root filesystem `43%` used with `277 GB` available, `51 GiB` memory available, open-file limit `4096`.
- Latest encrypted backup metadata identified `/backups/hermes-20260916T205359Z.dump.enc`, completed `2026-09-16T20:54:01Z`, `26,683,360` bytes, SHA-256 `57a583ad7b07c587ff2f09fbaa894744dfd5e1bbf85065ce4035374d04b58191`. Restore verification was not attempted.
- No application restart, deployment, migration, credential change, volume/data deletion, backup deletion, or publication mutation was performed.

## Service and data-integrity state

Service is currently healthy and ingestion recovered. Persisted totals after recovery are `50,950` source documents, `186` reports, `201` publications, `378` detections, `201` hunts, `201` remediations, and `11` relationships. Reports/publications and analyst artifacts remain older than ingestion (`2026-09-11T22:24:37Z`), which is an existing downstream freshness gap rather than a recovery regression.

**Data integrity:** preserved. Failed evidence and the original partial run remain visible; the successful recovery run is a separate persisted record. No production data, migration history, backups, or public CTI conclusions were altered.

**Rollback:** not applicable to the recovery action; no code or image changed. If a source-policy fix is later authorized, deploy only through `./scripts/update-app.sh` and roll back to the prior verified image or revert the focused change.

## Prevention and follow-up

Under explicit maintenance/deployment authorization, inspect Krebs response headers/body against the source policy, add an offline content-type regression fixture, and implement the smallest compatible provider-specific normalization. Deploy only with `./scripts/update-app.sh`, then verify failed-source status, full-success/usable-run projections, monitor evidence, and report/publication freshness. Reconcile missing cron exports for `HERMES_MONITOR_EVIDENCE_FILE`, `HERMES_SECRET_DIR`, and `HERMES_IMAGE`. Investigate the monitor's transient internal-check timeout during collection and separately verify encrypted-backup restoreability and certificate state.
