---
name: deployment-rollback
description: Perform approval-gated immutable deployment and smoke-tested rollback.
---

# Deployment and rollback

Require a current approval reference and immutable image/commit. Preflight
status, backup, health, disk, migration compatibility, and rollback target.
Validate Compose, migrate in the controlled one-shot service, smoke-test all
required public/private surfaces, observe, and record the deployment. On
failure preserve evidence and restore the compatible previous image; do not
reverse irreversible migrations speculatively.
