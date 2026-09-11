Use to update and deploy the CTI-Hermes application stack in the home lab.

Project root: /home/$USER/code/threat-intel-agent/
Approved repository: mrcoggsworth/threat-intel-agent
Private service base URL: https://hermes.cti.scogin.dev
Compose file: deploy/docker-compose.yml
Production environment file: /opt/cti-hermes/env/production.env

To deploy application updates, run from the repository root:
    ./scripts/update-app.sh

This script automatically handles:
- Tailwind CSS compilation (if needed)
- Building the local container image
- Applying any pending database migrations
- Recreating the application services
- Polling service health (/health/live, /health/ready, /reports)

Verify service health, check the scheduler and worker containers, and report
the update status back to the user. Do not block on approval tokens, immutable
registry digests, or prior deployment receipts.
