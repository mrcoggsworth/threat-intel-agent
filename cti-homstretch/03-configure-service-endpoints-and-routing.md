# Task 03: Configure Service Endpoints & Network Routing

## Role & Goal
You are a networking and API systems engineer. Your objective is to configure the service endpoint URLs in the Hermes agent profiles and host environment so that both the `cti-analyst` and `cti-maintainer` profiles can reliably communicate with the CTI FastAPI service through the local Caddy container and loopback.

---

## Background & Diagnosis
1. The local Caddy container is bound to Tailscale IP `100.68.61.10` with two dedicated ports:
   - **Port 9443 (`https://matrix-1.taild27e3c.ts.net:9443`)**: Analyst & Public Portal surface. It exposes `/api/v1/analyst/*` and `/reports` while explicitly returning 404 for ops/admin endpoints.
   - **Port 9444 (`https://matrix-1.taild27e3c.ts.net:9444`)**: Private Operations & Admin surface. Caddy routes this surface to the loopback Hermes web port and exposes `/health/ready`, `/version`, `/api/v1/ops/*`, and `/api/v1/admin/*`.
   - **Loopback (`http://127.0.0.1:18000`)**: Direct unproxied container port mapped from `cti-hermes-web-1`.

2. The existing profile `.env` and prompt files configure:
   ```dotenv
   PRIVATE_SERVICE_URL=https://hermes.cti.scogin.dev
   HERMES_PRIVATE_SERVICE_URL=https://hermes.cti.scogin.dev
   ```
   The internal DNS record is managed by Pi-hole. Do not add a local
   `/etc/hosts` mapping; use the Tailscale URL above when off the LAN.

---

## Instructions

1. **Use the internal DNS name or Tailscale alternative:**
   On the internal network, use `https://hermes.cti.scogin.dev`. From a remote
   Tailscale client, use `https://matrix-1.taild27e3c.ts.net:9444`.
   Do not add a `.home.arpa` host mapping; the internal DNS record is managed
   by Pi-hole.

2. **Validate and reload the Caddy container:**
   ```bash
   docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
   docker compose --file ~/caddy/docker-compose.yml up --detach caddy
   ```

3. **Update Analyst Profile Environment (`~/.hermes/profiles/cti-analyst/.env`):**
   Update [`~/.hermes/profiles/cti-analyst/.env`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/.env) with the accessible service endpoints:
   ```dotenv
   HERMES_ANALYST_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9443
   PRIVATE_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9444
   HERMES_PRIVATE_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9444
   ```
   *(For offline/local testing without Tailscale TLS verification, `http://127.0.0.1:18000` can be used directly).*

4. **Update Maintainer Profile Environment (`~/.hermes/profiles/cti-maintainer/.env`):**
   Update [`~/.hermes/profiles/cti-maintainer/.env`](file:///home/cptcoggsworth/.hermes/profiles/cti-maintainer/.env):
   ```dotenv
   PRIVATE_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9444
   HERMES_PRIVATE_SERVICE_URL=https://matrix-1.taild27e3c.ts.net:9444
   HERMES_PUBLIC_BASE_URL=https://matrix-1.taild27e3c.ts.net:9443
   ```

5. **Update Staging Prompts (Repository & Profiles):**
   Review prompt markdown files in:
   - `~/.hermes/profiles/cti-analyst/prompts/`
   - `~/.hermes/profiles/cti-maintainer/prompts/`
   - `.hermes/profiles/cti-analyst/prompts/`
   - `.hermes/profiles/cti-maintainer/prompts/`
   Ensure the `Private service base URL:` and `Analyst service base URL:` fields reflect the reachable endpoints.

---

## Verification Steps & Expected Outputs

1. Test Public Liveness via Analyst Port (9443):
   ```bash
   curl -sk https://matrix-1.taild27e3c.ts.net:9443/health/live
   ```
   **Expected Output:** `{"status":"ok"}`

2. Test Private Readiness via Operations Port (9444):
   ```bash
   ADMIN_TOKEN=$(cat /home/cptcoggsworth/.local/state/cti-hermes/secrets/admin-token)
   curl -sk -H "X-Admin-Token: $ADMIN_TOKEN" https://matrix-1.taild27e3c.ts.net:9444/health/ready
   ```
   **Expected Output:** `{"status":"ok","checks":{"configuration":"ok","database":"ok"}}`

3. Test Ops Last Success via Operations Port (9444):
   ```bash
   ADMIN_TOKEN=$(cat /home/cptcoggsworth/.local/state/cti-hermes/secrets/admin-token)
   curl -sk -H "X-Admin-Token: $ADMIN_TOKEN" https://matrix-1.taild27e3c.ts.net:9444/api/v1/ops/last-success
   ```
   **Expected Output:** `{"scope":"private","last_success":...}` (HTTP 200)

4. Test Direct Loopback Access (Port 18000):
   ```bash
   curl -s http://127.0.0.1:18000/health/live
   ```
   **Expected Output:** `{"status":"ok"}`

---

## Acceptance Criteria
- [ ] Both ports 9443 and 9444 respond over HTTPS with valid responses for their respective route policies.
- [ ] No DNS resolution errors (`Errno -2`) occur when executing curl commands against the configured URLs.
- [ ] Profile `.env` files have been updated with verified, reachable URLs.
