---
name: docker-compose-operations
description: Validate and operate Compose only within approved boundaries.
---

# Docker Compose operations

Use the pinned production Compose file and immutable image. Run config
validation before changes; inspect service health, networks, volumes, logs,
restart history, and secret references. Do not expose the Docker socket to the
analyst, delete volumes, broadly prune state, or deploy without approval.
