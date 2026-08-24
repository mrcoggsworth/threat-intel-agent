# cti-maintainer durable memory

Stable operational facts only. Do not copy analyst MEMORY.md or intelligence
history here. Store intelligence history in PostgreSQL and operational facts
in approved runbooks and audit records.

- Repository default branch is `main`; changes use focused branches and draft
  pull requests.
- `config/sources.json` is authoritative; do not silently replace feeds.
- Production uses immutable images, external Docker secrets, explicit
  migrations, encrypted PostgreSQL backups, smoke tests, and rollback records.
- Deployment requires an approval reference and must preserve a compatible
  previous image.
