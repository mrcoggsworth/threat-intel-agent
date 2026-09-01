"""Transport-mocked unit tests for RSS 2.0, Atom, Web Scraper, and Deduplicator."""

from __future__ import annotations

import datetime
from datetime import UTC

import httpx
import pytest

from hermes_cti.ingestion.normalization import NormalizationError
from hermes_cti.ingestion.rss_parser import (
    FeedDeduplicator,
    FeedItem,
    fetch_and_parse_feed,
    parse_feed_xml,
    parse_published_date,
)
from hermes_cti.ingestion.web_scraper import (
    clean_html_content,
    extract_pdf_text_fallback,
    fetch_article_text,
)

RSS_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>CERT Threat Advisories</title>
    <link>https://cert.example.org/advisories</link>
    <description>Daily threat intelligence feed</description>
    <language>en-US</language>
    <item>
      <title>Advisory 2026-001: Critical Flaw in Widget Server &amp; Service</title>
      <link>https://cert.example.org/advisories/2026-001</link>
      <guid isPermaLink="true">https://cert.example.org/advisories/2026-001</guid>
      <pubDate>Mon, 22 Aug 2026 08:00:00 GMT</pubDate>
      <dc:creator>Jane Doe</dc:creator>
      <category>Vulnerabilities</category>
      <category>Critical</category>
      <description><![CDATA[<p>A critical buffer overflow was found in Widget
      Server.</p>]]></description>
      <content:encoded><![CDATA[<p>Full advisory details explaining remote code
      execution mechanics.</p>]]></content:encoded>
    </item>
  </channel>
</rss>"""

ATOM_SAMPLE = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Security Research Blog</title>
  <link href="https://blog.example.com"/>
  <updated>2026-08-22T10:00:00Z</updated>
  <entry>
    <id>urn:uuid:12345678-1234-5678-1234-567812345678</id>
    <title>Analysis of Novel Ransomware Campaign</title>
    <link rel="alternate" href="https://blog.example.com/posts/ransomware-2026"/>
    <updated>2026-08-22T09:30:00Z</updated>
    <author>
      <name>Alice Smith</name>
    </author>
    <category term="Ransomware"/>
    <summary type="html">&lt;p&gt;Overview of attacker TTPs.&lt;/p&gt;</summary>
    <content type="html">&lt;p&gt;Full breakdown of ransomware
    decryption &amp;amp; IOCs.&lt;/p&gt;</content>
  </entry>
</feed>"""


def test_rss2_feed_parsing() -> None:
    items = parse_feed_xml(RSS_SAMPLE, base_url="https://cert.example.org")
    assert len(items) == 1
    item = items[0]
    assert "Critical Flaw in Widget Server & Service" in item.title
    assert item.link == "https://cert.example.org/advisories/2026-001"
    assert item.guid == "https://cert.example.org/advisories/2026-001"
    assert item.author == "Jane Doe"
    assert set(item.categories) == {"Vulnerabilities", "Critical"}
    assert item.published == datetime.datetime(2026, 8, 22, 8, 0, tzinfo=UTC)
    assert "buffer overflow" in item.summary
    assert "Full advisory details" in item.content


def test_atom_feed_parsing() -> None:
    items = parse_feed_xml(ATOM_SAMPLE, base_url="https://blog.example.com")
    assert len(items) == 1
    item = items[0]
    assert item.title == "Analysis of Novel Ransomware Campaign"
    assert item.guid == "urn:uuid:12345678-1234-5678-1234-567812345678"
    assert item.link == "https://blog.example.com/posts/ransomware-2026"
    assert item.author == "Alice Smith"
    assert "Ransomware" in item.categories
    assert item.published == datetime.datetime(2026, 8, 22, 9, 30, tzinfo=UTC)
    assert "attacker TTPs" in item.summary
    assert "Full breakdown of ransomware" in item.content


def test_parse_published_date_formats() -> None:
    # RFC 2822
    d1 = parse_published_date("Mon, 22 Aug 2026 08:00:00 GMT")
    assert d1 == datetime.datetime(2026, 8, 22, 8, 0, tzinfo=UTC)

    # ISO 8601
    d2 = parse_published_date("2026-08-22T08:00:00Z")
    assert d2 == datetime.datetime(2026, 8, 22, 8, 0, tzinfo=UTC)

    # Date only
    d3 = parse_published_date("2026-08-22")
    assert d3 == datetime.datetime(2026, 8, 22, 0, 0, tzinfo=UTC)

    # Invalid / empty
    assert parse_published_date(None) is None
    assert parse_published_date("") is None
    assert parse_published_date("invalid-date-format") is None


def test_feed_deduplication() -> None:
    dedup = FeedDeduplicator()
    item1 = FeedItem(
        guid="guid-1",
        title="Title 1",
        link="https://example.com/1",
        published=datetime.datetime.now(UTC),
        summary="Summary 1",
        content="Content 1",
    )
    item2 = FeedItem(
        guid="guid-2",
        title="Title 2",
        link="https://example.com/2",
        published=datetime.datetime.now(UTC),
        summary="Summary 2",
        content="Content 2",
    )
    # Duplicate GUID
    item1_dup = FeedItem(
        guid="guid-1",
        title="Title 1 alt",
        link="https://example.com/1-alt",
        published=datetime.datetime.now(UTC),
        summary="Summary 1",
    )

    filtered = dedup.filter_new([item1, item2])
    assert len(filtered) == 2
    assert dedup.is_duplicate(item1)
    assert dedup.is_duplicate(item2)
    assert dedup.is_duplicate(item1_dup)

    # Second pass should return empty
    second_pass = dedup.filter_new([item1, item1_dup])
    assert len(second_pass) == 0

    # Clear should reset
    dedup.clear()
    assert not dedup.is_duplicate(item1)


def test_html_article_cleaning() -> None:
    html = """
    <!DOCTYPE html>
    <html>
      <head><title>Threat Report</title><style>.hidden { display: none; }</style></head>
      <body>
        <nav><a href="/">Home</a> | <a href="/about">About</a></nav>
        <header><h1>Site Header Banner</h1></header>
        <main>
          <article>
            <h1>Security Alert: APT41 Campaign</h1>
            <p>APT41 has targeted critical infrastructure sectors.</p>
            <script>alert("tracking");</script>
            <noscript>JavaScript is required</noscript>
            <div>
              <p>Key IOCs include IP <code>198.51.100.1</code> and domain
              <code>c2.example.com</code>.</p>
            </div>
          </article>
        </main>
        <footer><p>&copy; 2026 Threat Intel Corp</p></footer>
      </body>
    </html>
    """
    cleaned = clean_html_content(html)
    assert "Site Header Banner" not in cleaned  # Stripped header
    assert "Home | About" not in cleaned  # Stripped nav
    assert "tracking" not in cleaned  # Stripped script
    assert "JavaScript is required" not in cleaned  # Stripped noscript
    assert "&copy;" not in cleaned
    assert "Security Alert: APT41 Campaign" in cleaned
    assert "APT41 has targeted critical infrastructure sectors." in cleaned
    assert "198.51.100.1" in cleaned


def test_malformed_feed_handling() -> None:
    with pytest.raises(NormalizationError) as exc_info:
        parse_feed_xml(b"")
    assert exc_info.value.classification == "empty_feed"

    with pytest.raises(NormalizationError) as exc_info2:
        parse_feed_xml(b"<html><body>Not XML feed</body></html>")
    assert exc_info2.value.classification == "schema_error"

    with pytest.raises(NormalizationError) as exc_info3:
        parse_feed_xml(b"<rss><broken>")
    assert exc_info3.value.classification == "malformed_xml"


def test_pdf_extraction_fallback() -> None:
    # Construct a minimal synthetic PDF byte stream with text object
    synthetic_pdf = (
        b"%PDF-1.4\n1 0 obj\n<< /Length 50 >>\nstream\nBT\n/F1 12 Tf\n"
        b"(CISA Advisory PDF Content) Tj\nET\nendstream\nendobj\n%%EOF"
    )
    extracted = extract_pdf_text_fallback(synthetic_pdf)
    assert "CISA Advisory PDF Content" in extracted

    # Empty payload
    assert extract_pdf_text_fallback(b"") == ""


@pytest.mark.asyncio
async def test_fetch_and_parse_feed_mocked() -> None:
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, content=RSS_SAMPLE, headers={"content-type": "application/rss+xml"}
        )
    )
    from hermes_cti.ingestion.http_client import AsyncHTTPClient, HTTPClientConfig

    client = AsyncHTTPClient(HTTPClientConfig(), transport=transport)
    try:
        items = await fetch_and_parse_feed(
            "https://cert.example.org/feed.xml", client=client
        )
        assert len(items) == 1
        assert "Widget Server" in items[0].title
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_fetch_article_text_mocked() -> None:
    html = (
        "<html><body><article><p>High severity advisory content</p>"
        "</article></body></html>"
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, text=html, headers={"content-type": "text/html; charset=utf-8"}
        )
    )
    from hermes_cti.ingestion.http_client import AsyncHTTPClient, HTTPClientConfig

    client = AsyncHTTPClient(HTTPClientConfig(), transport=transport)
    try:
        text = await fetch_article_text("https://example.com/advisory-1", client=client)
        assert "High severity advisory content" in text
    finally:
        await client.aclose()
