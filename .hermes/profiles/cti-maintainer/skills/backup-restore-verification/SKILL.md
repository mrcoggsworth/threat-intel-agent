---
name: backup-restore-verification
description: Verify encrypted PostgreSQL backups and isolated restores.
---

# Backup and restore verification

Check age, metadata, size, checksum, encryption, and retention without
printing keys. Test restore in an isolated disposable PostgreSQL target,
verify Alembic revision and table presence, and record artifact IDs/results.
Never delete the only backup or overwrite production during verification.
