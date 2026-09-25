# Task 06: Execute Analyst Agent Pipeline & Verify CTI Portal

## Role & Goal
You are a Cyber Threat Intelligence (CTI) analyst and full-stack integration engineer. Your objective is to run the `cti-analyst` Hermes agent profile against the populated ingestion data, verify that it submits threat intelligence proposals and report bundles via the authenticated Analyst API, and confirm that the CTI web portal dynamically displays the published reports, detections, hunts, and remediation.

---

## Current operator procedure

Do not hard-code a cron job ID from an old runbook. Resolve it immediately before
use, check doctor/status, then inspect durable execution state after launch:

```bash
hermes --profile cti-analyst cron list
hermes --profile cti-analyst cron doctor
hermes --profile cti-analyst cron status
# Use the current ID printed by cron list:
hermes --profile cti-analyst cron run <current_job_id>
hermes --profile cti-analyst cron runs <current_job_id> --limit 5
```

A launcher exit or `running` row is not completion evidence. Wait for `completed`
or `failed`, then inspect the execution response/transcript and read back ledger
and publication effects independently. Never remove an execution lock unless the
supported recovery process establishes that it is stale and owned by this job.

### Authentication and health

The runtime credential path is supplied by
`HERMES_ANALYST_SERVICE_TOKEN_FILE`; do not copy or print its contents. The
profile's supported health command reads the configured token file without
exposing it:

```bash
hermes-cti analyst health \
  --api-url "https://matrix-1.taild27e3c.ts.net:9443" \
  --token-file "$HERMES_ANALYST_SERVICE_TOKEN_FILE" \
  --cron-dir "$HOME/.hermes/profiles/cti-analyst/cron"
```

`/api/v1/analyst/*` deliberately returns HTTP 404 for missing or invalid
`X-Analyst-Token` credentials. Treat an unauthenticated 404 as fail-closed auth,
not proof that the route is absent; verify with the supported authenticated
health command. Do not weaken that behavior. Public projections do not require
the analyst token.

### Collection, candidates, and publication are separate stages

Collection success means sources were attempted and the ingestion run completed;
it does not mean a report was reviewed or published. Read the completed run and
its evidence through the analyst API before analysis. Record each qualifying
event as a CandidateRecord via `PUT /api/v1/analyst/candidates/{candidate_id}`
*before* report validation/submission, persist each lifecycle transition and
exact block reason, and query `GET /api/v1/analyst/candidates?run_id=<run_id>`
to reconcile terminal counts. Process candidates independently (maximum six per
execution); a blocked candidate must not block a valid sibling. Do not publish
through an ad-hoc script or claim a ledger transition that the API did not confirm.

For each candidate, run local bundle validation, authenticated API validation,
then publication only after validation passes; persist report identifiers and
published state in the ledger afterward. Repeating a submission must remain
idempotent. Verify public report IDs using `/api/v1/public/reports`, and verify
the portal detail page using the report slug. Treat ingestion freshness and
publication freshness as different signals.

### Verification and rollback boundaries

- Read current job ID with `cron list`; poll `cron runs <current_job_id> --limit 5`
  until a durable terminal state.
- Check candidate API summary and read public feed/detail independently; do not
  infer either from a successful HTTP submission alone.
- Use the service's `HERMES_ANALYST_SERVICE_TOKEN_FILE` path; never place token
  content in shell history, logs, artifacts, or reports.
- Do not write directly to PostgreSQL from analyst workflows. Do not rewrite a
  published version; corrections require a new validated version using the
  supported supersedes workflow.
- Profile prompt changes must be made in the repository template and reconciled
  with `scripts/install-hermes-profiles.sh`; review its dry-run output first.
  Reconciliation backs up changed managed files and preserves protected runtime
  state. Roll back only the changed managed file from that backup, then verify
  prompt/template parity. Never restore secrets, sessions, or logs from staging.
- Application deployment, if needed, is through `./scripts/update-app.sh` only;
  do not bypass a collection lock or active scheduler.
