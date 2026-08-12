"""Test cases for Ingestion module."""

from hermes.ingestion.rss_parser import RSSParser


def test_rss_parser_initialization():
    parser = RSSParser(sources=[])
    assert parser.fetch_all() == []
