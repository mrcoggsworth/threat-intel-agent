# Task 05: Restart Docker Stack & Run Initial CTI Ingestion

## Role & Goal
You are a site reliability and operations engineer. Your objective is to recreate the CTI Docker Compose stack with the updated network definitions and secrets, run an initial end-to-end ingestion and extraction pipeline into PostgreSQL, and verify that the monitoring watchdog recovers to a healthy state.

---

## Background & Diagnosis
- In previous steps:
  - Task 01 enabled egress networking (`edge` network) for the `scheduler` service in [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml).
  - Task 02 provisioned `/home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token`.
- Now, the running containers must be recreated to pick up the new network interfaces and file-backed secret mounts.
- Once running with egress, triggering `hermes-cti db run-daily` will ingest documents from [`config/sources.json`](file:///home/cptcoggsworth/code/threat-intel-agent/config/sources.json), extract IOCs and CVEs, write them into PostgreSQL, and establish a valid `last_successful_completed_at` timestamp.

---

## Instructions

1. **Recreate and Start the Compose Stack:**
   From the repository root, start the stack with the production environment and secrets:
   ```bash
   export HERMES_IMAGE=cti-hermes:local
   export HERMES_SECRET_DIR=/home/cptcoggsworth/.local/state/cti-hermes/secrets
   export HERMES_ENVIRONMENT=production
   
   docker compose -f deploy/docker-compose.yml up -d --force-recreate
   ```

2. **Verify Container Health:**
   Wait for services to complete healthchecks:
   ```bash
   docker ps --filter "name=cti-hermes"
   ```
   Ensure `postgres`, `web`, `scheduler`, and `backup` report `healthy`.

3. **Verify/Run Database Migrations:**
   Ensure all Alembic migrations are applied:
   ```bash
   docker exec cti-hermes-web-1 hermes-cti db migrate
   ```

4. **Trigger Initial Daily Collection & Persistence:**
   Execute a daily run within the application container:
   ```bash
   docker exec cti-hermes-web-1 hermes-cti db run-daily
   ```

5. **Verify Scheduler Logs:**
   Inspect the scheduler container to confirm it is actively scheduling without network errors:
   ```bash
   docker logs --tail 50 cti-hermes-scheduler-1
   ```

---

## Verification Steps & Expected Outputs

1. Check Database Ingestion and Entity Row Counts:
   ```bash
   docker exec cti-hermes-postgres-1 psql -U hermes -d hermes -c "
   SELECT 'ingestion_run' AS table_name, count(*) FROM ingestion_run
   UNION ALL SELECT 'source_document', count(*) FROM source_document
   UNION ALL SELECT 'raw_artifact', count(*) FROM raw_artifact
   UNION ALL SELECT 'indicator', count(*) FROM indicator
   UNION ALL SELECT 'indicator_observation', count(*) FROM indicator_observation
   UNION ALL SELECT 'evidence_claim', count(*) FROM evidence_claim;
   "
   ```
   **Expected Output:** All listed tables must have row counts > 0 (e.g., `source_document` > 10, `indicator` > 50).

2. Verify Last Success Endpoint:
   ```bash
   ADMIN_TOKEN=$(cat /home/cptcoggsworth/.local/state/cti-hermes/secrets/admin-token)
   curl -s -H "X-Admin-Token: $ADMIN_TOKEN" -H "Host: ops.cti-hermes.home.arpa" http://127.0.0.1:18000/api/v1/ops/last-success
   ```
   **Expected Output:**
   ```json
   {"scope": "private", "last_success": "2026-08-26T..."}
   ```
   *(A valid ISO timestamp rather than `null`).*

3. Verify Monitor Container Status:
   ```bash
   docker logs --tail 20 cti-hermes-monitor-1
   docker ps --filter "name=cti-hermes-monitor"
   ```
   **Expected Output:** The monitor container runs without emitting `last successful run stale` failures and remains in `Up` status.

4. Test Authenticated Analyst Status API:
   ```bash
   ANALYST_TOKEN=$(cat /home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token)
   curl -s -H "X-Analyst-Token: $ANALYST_TOKEN" http://127.0.0.1:18000/api/v1/analyst/status
   ```
   **Expected Output:**
   ```json
   {"status":"ready","application_version":"0.1.0","database":"ok","latest_completed_run_id":"..."}
   ```

---

## Acceptance Criteria
- [ ] `scheduler` container resolves DNS and successfully pulls feeds.
- [ ] PostgreSQL tables (`source_document`, `raw_artifact`, `indicator`, `evidence_claim`) are populated with non-zero records.
- [ ] `/api/v1/ops/last-success` returns a valid timestamp.
- [ ] `cti-hermes-monitor-1` stops crashing and stays healthy.
- [ ] `/api/v1/analyst/status` responds with HTTP 200 and `"status": "ready"`.
