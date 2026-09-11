# cti-maintainer durable memory

Stable operational facts only. Do not copy analyst MEMORY.md or intelligence
history here. Store intelligence history in PostgreSQL and operational facts
in approved runbooks and audit records.

- Repository default branch is `main`; changes use focused branches and draft
  pull requests.
- `config/sources.json` is authoritative; do not silently replace feeds.
- Production environment is a home lab running on the matrix host.
- Application updates and deployments are managed via `./scripts/update-app.sh`.
- Do not require corporate approval references, approval identities, or prior deployment receipts.
