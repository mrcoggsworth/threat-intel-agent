# Profile coordination contract

The analyst may detect a product defect or persistent feed failure and submit a
structured maintenance request/service event containing event ID, source/run
IDs, evidence IDs, reproduction details, likely component, severity, and next
action. The analyst does not edit code or deployment state.

The maintainer reads the event, reproduces with saved artifacts or fixtures,
creates a focused branch or fix, adds tests, implements the fix,
and runs `./scripts/update-app.sh` to update the application stack.
The analyst can then inspect and verify the resulting intelligence pipeline.

Audit records must contain profile, job/session ID, action, commit or service
run ID, tool result, approval reference, deployment record, and error/rollback
result. Never store secrets in the event or audit trail. PostgreSQL is the
source of truth for intelligence history; profile memories are not a message
bus.
