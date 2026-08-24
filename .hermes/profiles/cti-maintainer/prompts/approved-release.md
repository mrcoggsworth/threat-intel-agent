Use only when the current request explicitly approves deployment and identifies
an immutable commit or image.

Project root: /home/$USER/code/threat-intel-agent/
Approved repository: mrcoggsworth/threat-intel-agent
Private service base URL: https://ops.cti-hermes.local
Approved release/image: __REQUIRED_APPROVED_RELEASE__
Compose file: deploy/docker-compose.yml
Production environment file: /opt/cti-hermes/env/production.env

Verify approval reference, exact immutable commit or digest, repository status,
current version, rollback image, PostgreSQL health, disk capacity, backup
destination, and recent backup. Create and verify a fresh backup. Review
migration compatibility and stop if an irreversible migration lacks explicit
approval.

Pull/build only the exact immutable artifact, validate Compose, run controlled
migrations, start services, and verify liveness, readiness, private version,
migration state, reports, one canonical report, hunt, remediation, detection,
worker, scheduler, monitor, backup, and proxy. Observe the defined window.

If a required smoke test fails, preserve evidence and restore the previous
compatible image using the documented rollback. Reverse migrations only when
documented safe; prefer forward repair for irreversible changes. Create a
maintenance issue. Return release/digest, migration revision, backup ID,
smoke results, rollback state, deployment record, and follow-up items.
