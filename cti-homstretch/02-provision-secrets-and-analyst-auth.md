# Task 02: Provision Secrets & Configure Analyst API Authentication

## Role & Goal
You are a security and backend engineer. Your objective is to generate the required `analyst-token`, mount it properly into the `web` container in [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml), provision the credential into the `cti-analyst` profile, and ensure authenticated calls to `/api/v1/analyst/*` succeed.

---

## Background & Diagnosis
1. In [`src/hermes_cti/api/dependencies.py:require_analyst_token`](file:///home/cptcoggsworth/code/threat-intel-agent/src/hermes_cti/api/dependencies.py#L58-L71), the application inspects `request.app.state.settings.analyst_token`. If that setting is `None` or does not match the `X-Analyst-Token` header, it returns `404 Not Found`.
2. In the running environment:
   - Secret directory `/home/cptcoggsworth/.local/state/cti-hermes/secrets/` contains `admin-token`, `database-url`, `postgres-password`, `backup-key`, and `application-secret`, but **NO `analyst-token`**.
   - The `web` container in [`deploy/docker-compose.yml`](file:///home/cptcoggsworth/code/threat-intel-agent/deploy/docker-compose.yml#L29) lists `hermes_analyst_token`, but because the file was missing during startup, `HERMES_ANALYST_TOKEN_FILE` is not active in the running container.
   - The Hermes profile `cti-analyst` specifies `HERMES_ANALYST_SERVICE_TOKEN_FILE=/etc/hermes/cti-analyst/service-token` in [`~/.hermes/profiles/cti-analyst/.env`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/.env), but this path does not exist.
   - A curl test with `X-Analyst-Token` currently returns `404 Not Found`.

---

## Instructions

1. **Generate the Analyst Token in the Docker Secret Directory:**
   ```bash
   SECRET_DIR="/home/cptcoggsworth/.local/state/cti-hermes/secrets"
   mkdir -p "$SECRET_DIR"
   if [ ! -s "$SECRET_DIR/analyst-token" ]; then
       openssl rand -hex 32 > "$SECRET_DIR/analyst-token"
       chmod 644 "$SECRET_DIR/analyst-token"
   fi
   ```

2. **Provision the Token for the `cti-analyst` Profile:**
   Store the secret inside the profile's dedicated credentials directory:
   ```bash
   CRED_DIR="/home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials"
   mkdir -p "$CRED_DIR"
   chmod 700 "$CRED_DIR"
   cp "$SECRET_DIR/analyst-token" "$CRED_DIR/service-token"
   chmod 600 "$CRED_DIR/service-token"
   ```

3. **Update Profile Configuration:**
   - In [`~/.hermes/profiles/cti-analyst/.env`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/.env), verify or set:
     ```dotenv
     HERMES_ANALYST_SERVICE_TOKEN_FILE=/home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials/service-token
     ```
   - In [`~/.hermes/profiles/cti-analyst/config.yaml`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/config.yaml), verify or set under `permissions.credentials`:
     ```yaml
     permissions:
       credentials:
         service_token_file: /home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials/service-token
     ```

4. **Verify [`scripts/setup-docker-secrets.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/setup-docker-secrets.sh):**
   Ensure [`scripts/setup-docker-secrets.sh`](file:///home/cptcoggsworth/code/threat-intel-agent/scripts/setup-docker-secrets.sh) generates and installs `analyst-token` on fresh setups without errors.

---

## Verification Steps & Expected Outputs

1. Verify token file permissions and non-empty status:
   ```bash
   ls -la /home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token
   ls -la /home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials/service-token
   ```
   **Expected Output:** Both files exist, are non-empty (64 hex characters + newline), and have restricted permissions (`0644` in secret dir, `0600` in profile).

2. Verify both token files have matching SHA-256 hashes:
   ```bash
   sha256sum /home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token /home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials/service-token
   ```
   **Expected Output:** Identical SHA-256 checksums for both files.

---

## Acceptance Criteria
- [ ] `/home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token` exists and is populated.
- [ ] `/home/cptcoggsworth/.hermes/profiles/cti-analyst/credentials/service-token` exists with mode `0600`.
- [ ] `~/.hermes/profiles/cti-analyst/.env` and `config.yaml` reference the local user credentials directory.
