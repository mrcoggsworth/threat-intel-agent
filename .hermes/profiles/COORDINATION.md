# Profile coordination contract

The analyst may detect a product defect or persistent feed failure and submit a
structured maintenance request/service event containing event ID, source/run
IDs, evidence IDs, reproduction details, likely component, severity, and next
action. The analyst does not edit code or deployment state.

The maintainer reads the event, reproduces with saved artifacts or fixtures,
creates an issue or focused branch, adds tests, implements the smallest fix,
and creates a draft pull request. A human reviews and approves. Only then may
the maintainer run the approved deployment; smoke failure preserves evidence
and triggers the documented compatible rollback. The deployment record closes
the maintenance request.

Audit records must contain profile, job/session ID, action, commit or service
run ID, tool result, approval reference, deployment record, and error/rollback
result. Never store secrets in the event or audit trail. PostgreSQL is the
source of truth for intelligence history; profile memories are not a message
bus.
