"""Threat Hunting Playbook Generator."""

from typing import Dict, Any


class HuntPlaybookGenerator:
    """Creates structured hunting and remediation guides for incident responders."""

    def create_playbook(self, threat_name: str, details: Dict[str, Any]) -> str:
        """Builds Markdown threat hunting playbook."""
        return f"# Threat Hunt Playbook: {threat_name}\n\n## Containment & Remediation\n"
