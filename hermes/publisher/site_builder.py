"""Static site builder for Hermes CTI Web Portal."""

import logging

logger = logging.getLogger(__name__)


class SiteBuilder:
    """Builds static web portal hosting threat reports, IOC search, and playbooks."""

    def __init__(self, output_dir: str = "./portal"):
        self.output_dir = output_dir

    def build_portal(self) -> None:
        """Renders HTML site from threat dataset."""
        logger.info(f"Building threat intel web portal at {self.output_dir}")
