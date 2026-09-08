Diagnose the reported CTI-Hermes incident. Read the latest monitor evidence and
proceed only for actionable_failure or operator_required evidence with its
event, timestamps, endpoint/status, correlation ID, and run ID. A heartbeat
alone cannot trigger recovery, and healthy/unknown/stale evidence must return
SILENT without model or recovery work. Acquire the cooldown/lock gate and
record suppressed, attempted, and completed events.

Record safe health, version, image, migration, run, backup, disk, certificate,
and container evidence. Choose the smallest reversible action. Do not
initialize a new database, delete volumes, prune Docker state, rotate
credentials, or deploy without explicit approval. Approved releases are
manual and must use scripts/deploy-approved.sh with an immutable image and
receipt. Verify every recovery action and create an incident or maintenance
issue.
