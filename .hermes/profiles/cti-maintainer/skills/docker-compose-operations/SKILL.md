---
name: docker-compose-operations
description: Validate and operate Compose services and application updates.
---

# Docker Compose operations

Use the production Compose file (`deploy/docker-compose.yml`). Run config
validation before changes; inspect service health, networks, volumes, logs,
restart history, and secret references. For stack updates and deployments,
use `./scripts/update-app.sh`. Do not expose the Docker socket to the
analyst, delete persistent volumes, or broadly prune state.
