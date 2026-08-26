# Task 01: Fix Docker Scheduler Network Egress

## Role & Goal
You are an expert DevOps and Python infrastructure engineer. Your objective is to enable external internet egress for the CTI-Hermes `scheduler` container in [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml) so that the automated ingestion pipeline can reach external threat feeds (CISA KEV, RSS, vendor blogs) and populate PostgreSQL.

---

## Background & Diagnosis
The `scheduler` service in [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml#L62-L83) runs [`DailyPipeline`](file:///home/cptcoggsworth/code/threat-intel-agent/src/hermes_cti/db/pipeline.py#L35-L130), which attempts to download 14 threat intelligence feeds configured in [`config/sources.json`](file:///home/cptcoggsworth/code/threat-intel-agent/config/sources.json).

Currently, `scheduler` is attached ONLY to the `backend` network:
```yaml
  scheduler:
    image: ${HERMES_IMAGE:?HERMES_IMAGE must be an immutable application image}
    ...
    networks:
      - backend
```
In the same compose file:
```yaml
networks:
  edge:
  backend:
    internal: true
```
Because `backend` has `internal: true`, the container has no default gateway or internet egress. In the scheduler logs:
```text
docker logs cti-hermes-scheduler-1
# Output: "source collection failed"
```
Direct python inspection in the container confirms:
```text
urllib.error.URLError: <urlopen error [Errno -3] Temporary failure in name resolution>
```

---

## Instructions

1. **Edit [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml):**
   Update the `scheduler` service definition so it joins both the `edge` network (which provides public egress) and the `backend` network (which provides PostgreSQL access).
   
   Locate lines 75–77:
   ```yaml
       networks:
         - backend
   ```
   Change to:
   ```yaml
       networks:
         - edge
         - backend
   ```

2. **Verify Configuration Integrity:**
   Validate that [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml) passes YAML and Docker Compose parsing without errors:
   ```bash
   docker compose -f deploy/docker-compose.yml config --quiet
   ```

---

## Verification Steps & Expected Outputs

1. Run a Compose configuration check using the production environment file:
   ```bash
   HERMES_IMAGE=cti-hermes:local \
   HERMES_SECRET_DIR=/home/cptcoggsworth/.local/state/cti-hermes/secrets \
   docker compose -f deploy/docker-compose.yml config --services
   ```
   **Expected Output:** Lists all services (`runtime-init`, `web`, `worker`, `scheduler`, `postgres`, `backup`, `monitor`, `migrate`, `smoke`).

2. Check network assignments for `scheduler`:
   ```bash
   HERMES_IMAGE=cti-hermes:local \
   HERMES_SECRET_DIR=/home/cptcoggsworth/.local/state/cti-hermes/secrets \
   docker compose -f deploy/docker-compose.yml config | grep -A 10 "scheduler:" | grep -A 3 "networks:"
   ```
   **Expected Output:**
   ```yaml
       networks:
         backend: null
         edge: null
   ```

---

## Acceptance Criteria
- [ ] [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml) assigns both `edge` and `backend` networks to `scheduler`.
- [ ] `docker compose config` succeeds without schema or reference errors.
