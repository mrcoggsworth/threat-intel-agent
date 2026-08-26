# Task 06: Execute Analyst Agent Pipeline & Verify CTI Portal

## Role & Goal
You are a Cyber Threat Intelligence (CTI) analyst and full-stack integration engineer. Your objective is to run the `cti-analyst` Hermes agent profile against the populated ingestion data, verify that it submits threat intelligence proposals and report bundles via the authenticated Analyst API, and confirm that the CTI web portal dynamically displays the published reports, detections, hunts, and remediation.

---

## Background & Diagnosis
- In Task 05, the CTI database was populated with raw source documents, extracted indicators, and evidence claims.
- The `cti-analyst` profile ([`~/.hermes/profiles/cti-analyst/`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst)) is designed to:
  1. Call `GET /api/v1/analyst/status` and `GET /api/v1/analyst/evidence`.
  2. Perform threat analysis, MITRE ATT&CK mapping, and historical correlation using its equipped skills ([`cti-analysis`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/skills/cti-analysis), [`sigma-rule-generator`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/skills/sigma-rule-generator), [`yara-author`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/skills/yara-author), [`threat-hunting`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/skills/threat-hunting), [`remediation`](file:///home/cptcoggsworth/.hermes/profiles/cti-analyst/skills/remediation)).
  3. Submit relationship proposals to `POST /api/v1/analyst/proposals`.
  4. Submit and publish structured report bundles to `POST /api/v1/analyst/reports`.
- Once published, the web application ([`hermes_cti.portal`](file:///home/cptcoggsworth/code/threat-intel-agent/src/hermes_cti/portal/routes.py)) renders the reports at `/reports`, `/reports/{slug}`, and `/api/v1/public/reports`.

---

## Instructions

1. **Verify Evidence Availability on Analyst API:**
   ```bash
   ANALYST_TOKEN=$(cat /home/cptcoggsworth/.local/state/cti-hermes/secrets/analyst-token)
   curl -s -H "X-Analyst-Token: $ANALYST_TOKEN" http://127.0.0.1:18000/api/v1/analyst/evidence | jq '{ingestion_run_id, doc_count: (.documents | length), indicator_count: (.indicators | length)}'
   ```
   Confirm that documents and indicators are present in the response payload.

2. **Trigger the `cti-analyst` Daily Analysis Job:**
   Trigger the job `eb74b402c90d` (`cti-analyst-daily-analysis`):
   ```bash
   hermes --profile cti-analyst cron run eb74b402c90d
   ```
   Or trigger a single cron evaluation pass:
   ```bash
   hermes --profile cti-analyst cron tick
   ```

3. **Monitor the Agent Run:**
   Follow the agent execution log:
   ```bash
   tail -f ~/.hermes/profiles/cti-analyst/logs/agent.log
   ```
   Confirm that the agent reads evidence, maps techniques, generates detections, and posts to `/api/v1/analyst/reports`.

4. **Verify Database Records:**
   Query PostgreSQL to ensure published reports, report versions, and detections are written:
   ```bash
   docker exec cti-hermes-postgres-1 psql -U hermes -d hermes -c "
   SELECT 'report' AS table_name, count(*) FROM report
   UNION ALL SELECT 'report_version', count(*) FROM report_version
   UNION ALL SELECT 'publication', count(*) FROM publication
   UNION ALL SELECT 'detection', count(*) FROM detection
   UNION ALL SELECT 'hunt', count(*) FROM hunt
   UNION ALL SELECT 'remediation', count(*) FROM remediation;
   "
   ```

---

## Verification Steps & Expected Outputs

1. Verify Public Reports JSON Endpoint:
   ```bash
   curl -s http://127.0.0.1:18000/api/v1/public/reports | jq .
   ```
   **Expected Output:** JSON object containing `items` with at least one published report bundle, summaries, confidence scores, and severities.

2. Verify HTML Portal Page:
   ```bash
   curl -s http://127.0.0.1:18000/reports | grep -i "report"
   ```
   **Expected Output:** HTML content containing formatted report cards.

3. Verify Host Nginx HTTPS Analyst Endpoint (Port 9443):
   ```bash
   curl -sk https://matrix-1.taild27e3c.ts.net:9443/reports | grep -i "report"
   curl -sk https://matrix-1.taild27e3c.ts.net:9443/api/v1/public/reports | jq .
   ```
   **Expected Output:** Same published report content served securely over HTTPS.

4. Inspect Report Details & Detection Rules:
   Fetch the slug of a published report and query its detections and hunt guidance:
   ```bash
   SLUG=$(curl -s http://127.0.0.1:18000/api/v1/public/reports | jq -r '.items[0].slug')
   curl -s "http://127.0.0.1:18000/api/v1/public/reports/$SLUG" | jq '{title: .title, state: .state, detections: (.detections | length)}'
   ```
   **Expected Output:** `{"title": "...", "state": "published", "detections": >0}`

---

## Acceptance Criteria
- [ ] `cti-analyst` executes its workflow without authentication or endpoint errors.
- [ ] PostgreSQL contains rows in `report`, `report_version`, `publication`, and `detection`.
- [ ] Public API endpoint `/api/v1/public/reports` returns published reports.
- [ ] Portal UI (`/reports`) renders published threat reports and detection rules.
