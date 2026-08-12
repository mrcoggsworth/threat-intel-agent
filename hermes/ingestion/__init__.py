"""Ingestion module for fetching RSS feeds, news blogs, and security advisories."""

from .rss_parser import RSSParser
from .web_scraper import WebScraper

__all__ = ["RSSParser", "WebScraper"]
