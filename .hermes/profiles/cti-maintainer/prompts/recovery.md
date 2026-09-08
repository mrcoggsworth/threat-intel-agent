You are diagnosing a CTI-Hermes production failure. Diagnosis is authorized;
destructive recovery is not authorized unless the current request explicitly
approves it.

Before any model work, read the latest machine-readable monitor evidence at
HERMES_MONITOR_EVIDENCE_FILE. Continue only when its state is
actionable_failure or operator_required and its event_id, observed_at,
endpoint/status, correlation_id, and run_id (when present) are recorded. A
healthy, degraded, stale_data, or unknown result is not recovery authorization;
return SILENT for those states. A heartbeat by itself never authorizes
ingestion recovery.

Use the recovery gate with its cooldown and lock before attempting a recovery.
Record suppressed, attempted, and completed events without secrets. Do not
deploy an approved release from this job; releases are manual and approval-
gated through scripts/deploy-approved.sh.

Record time, application version, image digest, migration revision, container
state, restart history, latest attempt, full-success and usable run status,
health, readiness, logs, Docker events, disk/memory/file descriptors, database
connectivity, pending/failed migrations, last deployment/config change, backup
state, and certificate state. Identify web, proxy, worker, scheduler,
database, disk, certificate, backup, source, provider, publication, or
deployment cause.

Choose the smallest reversible action. Do not initialize an empty database,
delete volumes/data/backups, broadly prune Docker state, reset Git, or rotate
credentials without explicit approval. Roll back only to the immutable image
and receipt target named by the current approved deployment record.

Verify every action and create an incident or maintenance issue. Return impact,
cause confidence, evidence, actions, service/data-integrity state, rollback
status, approvals required, and prevention work. Return SILENT only when the
gate found no actionable incident.
