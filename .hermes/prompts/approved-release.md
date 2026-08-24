Use only after the user explicitly approves a release and identifies the immutable image.
Run the preflight, fresh backup, migration compatibility review, controlled migration,
start, smoke tests, and observation window described in deploy/README.md. If approved
smoke tests fail, preserve evidence and use the documented automatic rollback. Do not
reverse an irreversible migration without approval.
