"""Hermes Autonomous Threat Intelligence Agent Entrypoint."""

import logging
import sys
from rich.console import Console

from hermes.ingestion import RSSParser
from hermes.analysis import IOCExtractor
from hermes.publisher import SiteBuilder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("hermes")
console = Console()


def main():
    console.print(
        "[bold cyan]⚡ HERMES // Autonomous Threat Intelligence Engine[/bold cyan]"
    )
    logger.info("Initializing Hermes Threat Intelligence pipeline...")

    # Step 1: Ingestion
    rss_parser = RSSParser(sources=[])
    articles = rss_parser.fetch_all()
    logger.info(f"Ingested {len(articles)} articles.")

    # Step 2: Analysis & IOC Extraction
    extractor = IOCExtractor()
    sample_iocs = extractor.extract_from_text("Sample telemetry 192.168.1.1")
    logger.info(f"Extracted IOCs: {sample_iocs}")

    # Step 3: Web Portal Sync
    builder = SiteBuilder()
    builder.build_portal()

    console.print(
        "[bold green]✔ Hermes execution turn finished successfully.[/bold green]"
    )


if __name__ == "__main__":
    main()
