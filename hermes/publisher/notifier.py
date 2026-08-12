"""Webhook and notification dispatcher module."""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class Notifier:
    """Dispatches threat alerts to webhooks (Discord, Slack, Teams, Email)."""

    def send_alert(self, summary: Dict[str, Any]) -> None:
        """Sends threat notification payload."""
        logger.info(f"Dispatching alert: {summary.get('title', 'Threat Alert')}")
